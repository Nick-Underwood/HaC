#!/usr/bin/env python3
"""
Docker -> NetBox sync (host-side).
Syncs the Docker host's containers/networks/volumes into NetBox.

Runs ON the Docker host (needs /var/run/docker.sock + the docker python SDK),
NOT inside the NetBox container. NetBox writes go through nb_rest (requests-only,
imported from /srv/netbox/scripts via PYTHONPATH).

Run from the host:
  PYTHONPATH=/srv/netbox/scripts NETBOX_URL=https://<REDACTED_HOST> \
  NETBOX_TOKEN_FILE=/srv/netbox/secrets/netbox_api_token.txt \
  python3 /srv/netbox/scripts/sync_docker.py
"""

import os
import sys
import socket

# nb_rest lives in /srv/netbox/scripts on the host — add to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import docker
from nb_rest import secret_env, NetBox

# Configuration
NETBOX_TOKEN = secret_env('NETBOX_TOKEN')
# Docker host identity in NetBox: DOCKER_HOST env (set by compose) or hostname.
DOCKER_HOST = os.getenv('DOCKER_HOST') or socket.gethostname()
DOCKER_SITE = os.getenv('DOCKER_SITE', 'homelab')


class DockerSync:
    def __init__(self):
        # Connect to the LOCAL docker socket regardless of any bare-hostname
        # DOCKER_HOST env (compose sets DOCKER_HOST=<REDACTED_HOST> which is not
        # a valid SDK base_url — force the unix socket).
        env_host = os.getenv('DOCKER_HOST', '')
        if env_host and not env_host.startswith(('unix://', 'tcp://', 'ssh://', 'npipe://')):
            os.environ.pop('DOCKER_HOST', None)
        try:
            self.docker_client = docker.from_env()
            self.nb = NetBox()
        except Exception as e:
            print(f"✗ Error initializing Docker client: {e}")
            raise

    def ensure_manufacturer(self):
        return self.nb.get_or_create(
            "dcim", "manufacturers", {"name": "Docker"},
            {"name": "Docker", "slug": "docker"})[0]

    def ensure_site(self):
        return self.nb.get_or_create(
            "dcim", "sites", {"name": DOCKER_SITE},
            {"name": DOCKER_SITE, "slug": DOCKER_SITE.lower()})[0]

    def ensure_device_role(self, name, color='9c27b0'):
        return self.nb.get_or_create(
            "dcim", "device-roles", {"name": name},
            {"name": name, "slug": name.lower().replace(' ', '-'), "color": color})[0]

    def ensure_device_type(self, manufacturer, model):
        return self.nb.get_or_create(
            "dcim", "device-types", {"model": model},
            {"manufacturer": manufacturer["id"], "model": model,
             "slug": model.lower().replace(' ', '-')})[0]

    def ensure_host_device(self):
        site = self.ensure_site()
        role = self.ensure_device_role('container-host', color='9c27b0')
        manufacturer = self.ensure_manufacturer()
        device_type = self.ensure_device_type(manufacturer, 'Docker Host')

        device, created = self.nb.get_or_create(
            "dcim", "devices", {"name": DOCKER_HOST},
            {"name": DOCKER_HOST, "device_type": device_type["id"],
             "role": role["id"], "site": site["id"], "status": "active"})
        if created:
            print(f"  ✓ Created Docker host device: {DOCKER_HOST}")
        return device

    def sync_networks(self):
        print("\n=== Syncing Docker Networks ===")
        try:
            networks = self.docker_client.networks.list()
            vlan_group, _ = self.nb.get_or_create(
                "ipam", "vlan-groups", {"name": "Docker Networks"},
                {"name": "Docker Networks", "slug": "docker-networks"})

            for network in networks:
                name = network.name
                driver = network.attrs.get('Driver', 'unknown')
                scope = network.attrs.get('Scope', 'local')

                if name in ['bridge', 'host', 'none'] and not network.attrs.get('Containers'):
                    continue

                ipam_config = network.attrs.get('IPAM', {}).get('Config', [])
                print(f"  Network: {name} ({driver}, {scope})")

                for config in ipam_config:
                    subnet = config.get('Subnet')
                    if not subnet:
                        continue
                    prefix, created = self.nb.get_or_create(
                        "ipam", "prefixes", {"prefix": subnet},
                        {"prefix": subnet, "status": "active",
                         "description": f"Docker network: {name} ({driver})"})
                    if created:
                        print(f"    ✓ Created prefix: {subnet}")
                    else:
                        self.nb.update("ipam", "prefixes", prefix["id"],
                                       {"description": f"Docker network: {name} ({driver})"})
                        print(f"    ✓ Updated prefix: {subnet}")
        except Exception as e:
            print(f"  ✗ Error syncing networks: {e}")

    def sync_containers(self):
        print("\n=== Syncing Docker Containers ===")
        try:
            containers = self.docker_client.containers.list(all=True)
            site = self.ensure_site()

            cluster_type, _ = self.nb.get_or_create(
                "virtualization", "cluster-types", {"name": "Docker"},
                {"name": "Docker", "slug": "docker"})
            cluster, _ = self.nb.get_or_create(
                "virtualization", "clusters", {"name": DOCKER_HOST},
                {"name": DOCKER_HOST, "type": cluster_type["id"], "site": site["id"]})

            for container in containers:
                name = container.name
                container_id = container.short_id
                status_map = {
                    'running': 'active', 'exited': 'offline', 'paused': 'staged',
                    'restarting': 'staged', 'created': 'staged',
                }
                status = status_map.get(container.status, 'offline')

                image = container.image.tags[0] if container.image.tags else 'unknown'
                labels = container.labels
                networks = list(container.attrs['NetworkSettings']['Networks'].keys())

                memory_limit = container.attrs['HostConfig'].get('Memory', 0)
                cpu_quota = container.attrs['HostConfig'].get('CpuQuota', 0)
                vcpus = max(1, cpu_quota // 100000) if cpu_quota > 0 else 1
                memory_mb = memory_limit // (1024 * 1024) if memory_limit > 0 else 512

                comments = (f"Container ID: {container_id}\nImage: {image}\n"
                            f"Networks: {', '.join(networks)}")
                if labels:
                    comments += f"\nLabels: {len(labels)} labels"

                vm, created = self.nb.get_or_create(
                    "virtualization", "virtual-machines", {"name": name},
                    {"name": name, "cluster": cluster["id"], "status": status,
                     "vcpus": vcpus, "memory": memory_mb, "comments": comments})
                if created:
                    print(f"  ✓ Created container VM: {name} ({status})")
                else:
                    self.nb.update("virtualization", "virtual-machines", vm["id"],
                                   {"status": status, "vcpus": vcpus,
                                    "memory": memory_mb, "comments": comments})
                    print(f"  ✓ Updated container VM: {name} ({status})")

                self.sync_container_interfaces(vm, container)
        except Exception as e:
            print(f"  ✗ Error syncing containers: {e}")

    def sync_container_interfaces(self, vm, container):
        try:
            network_settings = container.attrs['NetworkSettings']['Networks']
            for net_name, net_config in network_settings.items():
                ip_address = net_config.get('IPAddress')
                mac_address = net_config.get('MacAddress')
                if not ip_address:
                    continue

                interface, created = self.nb.get_or_create(
                    "virtualization", "interfaces",
                    {"virtual_machine_id": vm["id"], "name": net_name},
                    {"virtual_machine": vm["id"], "name": net_name,
                     "mac_address": mac_address if mac_address else None})
                if not created and mac_address and interface.get('mac_address') != mac_address:
                    self.nb.update("virtualization", "interfaces", interface["id"],
                                   {"mac_address": mac_address})

                ip_with_prefix = f"{ip_address}/16"
                existing = self.nb.get("ipam", "ip-addresses", address=ip_with_prefix)
                if not existing:
                    self.nb.create("ipam", "ip-addresses",
                                   {"address": ip_with_prefix, "status": "active",
                                    "assigned_object_type": "virtualization.vminterface",
                                    "assigned_object_id": interface["id"],
                                    "description": f"Container: {container.name}"})
                else:
                    self.nb.update("ipam", "ip-addresses", existing["id"],
                                   {"assigned_object_type": "virtualization.vminterface",
                                    "assigned_object_id": interface["id"],
                                    "description": f"Container: {container.name}"})
        except Exception as e:
            print(f"    ✗ Error syncing interfaces for {container.name}: {e}")

    def sync_volumes(self):
        print("\n=== Syncing Docker Volumes ===")
        try:
            volumes = self.docker_client.volumes.list()
            volume_list = []
            for v in volumes:
                attrs = v.attrs or {}
                # Size is only present after a prune/docker system df — skip
                # if unknown; keep name/driver/mountpoint + labels count
                labels = attrs.get("Labels") or {}
                lbl = f" labels={len(labels)}" if labels else ""
                volume_list.append(
                    f"{v.name} ({attrs.get('Driver', 'local')}): "
                    f"{attrs.get('Mountpoint', '')}{lbl}")
            print(f"  Found {len(volume_list)} volumes")

            host_device = self.ensure_host_device()
            volume_section = "=== Docker Volumes ===\n" + "\n".join(volume_list[:60])

            existing = self.nb.get("dcim", "devices", name=DOCKER_HOST)
            comments = (existing or {}).get("comments", "")
            if "=== Docker Volumes ===" in comments:
                parts = comments.split("=== Docker Volumes ===")
                comments = parts[0].strip() + f"\n\n{volume_section}"
            elif comments:
                comments = f"{comments}\n\n{volume_section}"
            else:
                comments = volume_section
            self.nb.update("dcim", "devices", host_device["id"], {"comments": comments})
            print(f"  ✓ Updated volume info on {DOCKER_HOST}")
        except Exception as e:
            print(f"  ✗ Error syncing volumes: {e}")

    def run(self):
        print("Starting Docker sync...")
        try:
            info = self.docker_client.info()
            print(f"✓ Connected to Docker: {info['Name']}")
            print(f"  Containers: {info['Containers']} ({info['ContainersRunning']} running)")
            print(f"  Images: {info['Images']}")

            self.sync_networks()
            self.sync_containers()
            self.sync_volumes()

            print("\n✓ Docker sync completed successfully!")
            return True
        except Exception as e:
            print(f"\n✗ Docker sync failed: {e}")
            return False


if __name__ == '__main__':
    sync = DockerSync()
    success = sync.run()
    exit(0 if success else 1)
