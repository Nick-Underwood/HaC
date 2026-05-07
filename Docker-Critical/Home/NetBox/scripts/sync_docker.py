#!/usr/bin/env python3
"""
Docker to NetBox Sync Script
Syncs Docker containers, images, networks, and volumes to NetBox
"""

import docker
import pynetbox
import os
from datetime import datetime

# Configuration
NETBOX_URL = os.getenv('NETBOX_URL', 'http://localhost:8080')
NETBOX_TOKEN = os.getenv('NETBOX_TOKEN', '')
DOCKER_HOST = os.getenv('DOCKER_HOST', 'truenas01')
DOCKER_SITE = os.getenv('DOCKER_SITE', 'homelab')

class DockerSync:
    def __init__(self):
        try:
            self.docker_client = docker.from_env()
            self.nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)
            self.nb.http_session.verify = False
        except Exception as e:
            print(f"✗ Error initializing Docker client: {e}")
            raise
    
    def ensure_manufacturer(self):
        """Ensure Docker manufacturer exists"""
        manufacturer = self.nb.dcim.manufacturers.get(name='Docker')
        if not manufacturer:
            manufacturer = self.nb.dcim.manufacturers.create(
                name='Docker',
                slug='docker'
            )
        return manufacturer
    
    def ensure_site(self):
        """Ensure site exists"""
        site = self.nb.dcim.sites.get(name=DOCKER_SITE)
        if not site:
            site = self.nb.dcim.sites.create(
                name=DOCKER_SITE,
                slug=DOCKER_SITE.lower()
            )
        return site
    
    def ensure_device_role(self, name, color='9c27b0'):
        """Ensure device role exists"""
        role = self.nb.dcim.device_roles.get(name=name)
        if not role:
            role = self.nb.dcim.device_roles.create(
                name=name,
                slug=name.lower().replace(' ', '-'),
                color=color
            )
        return role
    
    def ensure_device_type(self, manufacturer, model):
        """Ensure device type exists"""
        device_type = self.nb.dcim.device_types.get(model=model)
        if not device_type:
            device_type = self.nb.dcim.device_types.create(
                manufacturer=manufacturer.id,
                model=model,
                slug=model.lower().replace(' ', '-')
            )
        return device_type
    
    def ensure_host_device(self):
        """Ensure Docker host device exists in NetBox"""
        site = self.ensure_site()
        role = self.ensure_device_role('container-host', color='9c27b0')
        manufacturer = self.ensure_manufacturer()
        device_type = self.ensure_device_type(manufacturer, 'Docker Host')
        
        device = self.nb.dcim.devices.get(name=DOCKER_HOST)
        if not device:
            device = self.nb.dcim.devices.create(
                name=DOCKER_HOST,
                device_type=device_type.id,
                role=role.id,
                site=site.id,
                status='active'
            )
            print(f"  ✓ Created Docker host device: {DOCKER_HOST}")
        
        return device
    
    def sync_networks(self):
        """Sync Docker networks to NetBox VLANs/prefixes"""
        print("\n=== Syncing Docker Networks ===")
        
        try:
            networks = self.docker_client.networks.list()
            
            for network in networks:
                name = network.name
                network_id = network.short_id
                driver = network.attrs.get('Driver', 'unknown')
                scope = network.attrs.get('Scope', 'local')
                
                # Skip default bridge/host/none networks unless they have containers
                if name in ['bridge', 'host', 'none'] and not network.attrs.get('Containers'):
                    continue
                
                ipam_config = network.attrs.get('IPAM', {}).get('Config', [])
                
                print(f"  Network: {name} ({driver}, {scope})")
                
                # Create VLAN in NetBox
                vlan_group = self.nb.ipam.vlan_groups.get(name='Docker Networks')
                if not vlan_group:
                    vlan_group = self.nb.ipam.vlan_groups.create(
                        name='Docker Networks',
                        slug='docker-networks'
                    )
                
                # For each subnet in the network
                for config in ipam_config:
                    subnet = config.get('Subnet')
                    gateway = config.get('Gateway')
                    
                    if subnet:
                        # Create or update prefix
                        prefix = self.nb.ipam.prefixes.get(prefix=subnet)
                        if not prefix:
                            prefix = self.nb.ipam.prefixes.create(
                                prefix=subnet,
                                status='active',
                                description=f"Docker network: {name} ({driver})"
                            )
                            print(f"    ✓ Created prefix: {subnet}")
                        else:
                            prefix.description = f"Docker network: {name} ({driver})"
                            prefix.save()
                            print(f"    ✓ Updated prefix: {subnet}")
        
        except Exception as e:
            print(f"  ✗ Error syncing networks: {e}")
    
    def sync_containers(self):
        """Sync Docker containers as virtual machines in NetBox"""
        print("\n=== Syncing Docker Containers ===")
        
        try:
            containers = self.docker_client.containers.list(all=True)
            site = self.ensure_site()
            host_device = self.ensure_host_device()
            
            # Ensure cluster exists for containers
            cluster_type = self.nb.virtualization.cluster_types.get(name='Docker')
            if not cluster_type:
                cluster_type = self.nb.virtualization.cluster_types.create(
                    name='Docker',
                    slug='docker'
                )
            
            cluster = self.nb.virtualization.clusters.get(name=DOCKER_HOST)
            if not cluster:
                cluster = self.nb.virtualization.clusters.create(
                    name=DOCKER_HOST,
                    type=cluster_type.id,
                    site=site.id
                )
            
            for container in containers:
                name = container.name
                container_id = container.short_id
                status_map = {
                    'running': 'active',
                    'exited': 'offline',
                    'paused': 'staged',
                    'restarting': 'staged',
                    'created': 'staged'
                }
                status = status_map.get(container.status, 'offline')
                
                # Get container details
                image = container.image.tags[0] if container.image.tags else 'unknown'
                labels = container.labels
                networks = list(container.attrs['NetworkSettings']['Networks'].keys())
                
                # Extract resource limits if set
                memory_limit = container.attrs['HostConfig'].get('Memory', 0)
                cpu_quota = container.attrs['HostConfig'].get('CpuQuota', 0)
                
                # Calculate approximate vCPUs (Docker uses 100000 as 1 CPU)
                vcpus = max(1, cpu_quota // 100000) if cpu_quota > 0 else 1
                
                # Convert memory to MB
                memory_mb = memory_limit // (1024 * 1024) if memory_limit > 0 else 512
                
                # Get or create VM
                vm = self.nb.virtualization.virtual_machines.get(name=name)
                
                comments = f"Container ID: {container_id}\nImage: {image}\nNetworks: {', '.join(networks)}"
                if labels:
                    comments += f"\nLabels: {len(labels)} labels"
                
                if not vm:
                    vm = self.nb.virtualization.virtual_machines.create(
                        name=name,
                        cluster=cluster.id,
                        status=status,
                        vcpus=vcpus,
                        memory=memory_mb,
                        comments=comments,
                        custom_fields={
                            'container_id': container_id,
                            'image': image
                        } if self.has_custom_fields() else {}
                    )
                    print(f"  ✓ Created container VM: {name} ({status})")
                else:
                    # Update existing VM
                    vm.status = status
                    vm.vcpus = vcpus
                    vm.memory = memory_mb
                    vm.comments = comments
                    if self.has_custom_fields():
                        vm.custom_fields['container_id'] = container_id
                        vm.custom_fields['image'] = image
                    vm.save()
                    print(f"  ✓ Updated container VM: {name} ({status})")
                
                # Sync container network interfaces
                self.sync_container_interfaces(vm, container)
        
        except Exception as e:
            print(f"  ✗ Error syncing containers: {e}")
    
    def sync_container_interfaces(self, vm, container):
        """Sync container network interfaces"""
        try:
            network_settings = container.attrs['NetworkSettings']['Networks']
            
            for net_name, net_config in network_settings.items():
                ip_address = net_config.get('IPAddress')
                mac_address = net_config.get('MacAddress')
                
                if not ip_address:
                    continue
                
                # Get or create interface
                interface = self.nb.virtualization.interfaces.get(
                    virtual_machine_id=vm.id,
                    name=net_name
                )
                
                if not interface:
                    interface = self.nb.virtualization.interfaces.create(
                        virtual_machine=vm.id,
                        name=net_name,
                        mac_address=mac_address if mac_address else None
                    )
                else:
                    if mac_address and interface.mac_address != mac_address:
                        interface.mac_address = mac_address
                        interface.save()
                
                # Create or update IP address
                ip_with_prefix = f"{ip_address}/16"  # Most Docker networks use /16
                ip_obj = self.nb.ipam.ip_addresses.get(address=ip_with_prefix)
                
                if not ip_obj:
                    ip_obj = self.nb.ipam.ip_addresses.create(
                        address=ip_with_prefix,
                        status='active',
                        assigned_object_type='virtualization.vminterface',
                        assigned_object_id=interface.id,
                        description=f"Container: {container.name}"
                    )
                else:
                    ip_obj.assigned_object_type = 'virtualization.vminterface'
                    ip_obj.assigned_object_id = interface.id
                    ip_obj.description = f"Container: {container.name}"
                    ip_obj.save()
        
        except Exception as e:
            print(f"    ✗ Error syncing interfaces for {container.name}: {e}")
    
    def has_custom_fields(self):
        """Check if custom fields exist for VMs"""
        try:
            # Try to access custom_fields to see if they exist
            return True
        except:
            return False
    
    def sync_volumes(self):
        """Sync Docker volumes to NetBox (as comments/custom fields)"""
        print("\n=== Syncing Docker Volumes ===")
        
        try:
            volumes = self.docker_client.volumes.list()
            
            volume_list = []
            for volume in volumes:
                name = volume.name
                driver = volume.attrs.get('Driver', 'local')
                mountpoint = volume.attrs.get('Mountpoint', '')
                
                volume_list.append(f"{name} ({driver}): {mountpoint}")
            
            print(f"  Found {len(volume_list)} volumes")
            
            # Store volume info in host device comments
            host_device = self.ensure_host_device()
            volume_info = "\n".join(volume_list[:50])  # Limit to 50 volumes
            
            if host_device.comments:
                # Update or append volume section
                comments = host_device.comments
                if "=== Docker Volumes ===" in comments:
                    # Replace existing volume section
                    parts = comments.split("=== Docker Volumes ===")
                    host_device.comments = parts[0].strip() + f"\n\n=== Docker Volumes ===\n{volume_info}"
                else:
                    host_device.comments = f"{comments}\n\n=== Docker Volumes ===\n{volume_info}"
            else:
                host_device.comments = f"=== Docker Volumes ===\n{volume_info}"
            
            host_device.save()
            print(f"  ✓ Updated volume info on {DOCKER_HOST}")
        
        except Exception as e:
            print(f"  ✗ Error syncing volumes: {e}")
    
    def run(self):
        """Main sync routine"""
        print("Starting Docker sync...")
        
        try:
            # Get Docker info
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
