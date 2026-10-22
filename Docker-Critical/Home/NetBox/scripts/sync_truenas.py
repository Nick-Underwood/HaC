#!/usr/bin/env python3
"""
TrueNAS Scale to NetBox Sync Script
Syncs storage pools, network interfaces, and VMs from TrueNAS to NetBox.

pynetbox-free (requests-only via nb_rest) so it runs in the stock NetBox
image and survives container recreates (SHTF-safe).
"""

import requests
import os
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings if using self-signed certs
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from nb_rest import secret_env, NetBox

# Configuration
TRUENAS_URL = os.getenv('TRUENAS_URL', 'https://truenas01.u-acres.com').rstrip('/')
TRUENAS_API_KEY = secret_env('TRUENAS_API_KEY')
VERIFY_SSL = os.getenv('VERIFY_SSL', 'false').lower() == 'true'


class TrueNASSync:
    def __init__(self):
        self.truenas = requests.Session()
        self.truenas.headers.update({
            'Authorization': f'Bearer {TRUENAS_API_KEY}',
            'Content-Type': 'application/json'
        })
        self.nb = NetBox()

    def get_truenas_data(self, endpoint):
        """Fetch data from TrueNAS API"""
        url = f"{TRUENAS_URL}/api/v2.0/{endpoint}"
        try:
            response = self.truenas.get(url, verify=VERIFY_SSL)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching {endpoint}: {e}")
            return []

    def ensure_device_exists(self, name, role='storage', site='homelab'):
        """Ensure TrueNAS device exists in NetBox"""
        # Get or create manufacturer
        manufacturer, _ = self.nb.get_or_create(
            "dcim", "manufacturers", {"name": "iXsystems"},
            {"name": "iXsystems", "slug": "ixsystems"})

        # Get or create device type
        device_type, _ = self.nb.get_or_create(
            "dcim", "device-types", {"model": "TrueNAS-SCALE"},
            {"manufacturer": manufacturer["id"], "model": "TrueNAS-SCALE",
             "slug": "truenas-scale"})

        # Get or create site
        nb_site, _ = self.nb.get_or_create(
            "dcim", "sites", {"name": site}, {"name": site, "slug": site})

        # Get or create device role
        nb_role, _ = self.nb.get_or_create(
            "dcim", "device-roles", {"name": role},
            {"name": role, "slug": role, "color": "4caf50"})

        # Get or create device
        device, created = self.nb.get_or_create(
            "dcim", "devices", {"name": name},
            {"name": name, "device_type": device_type["id"],
             "role": nb_role["id"], "site": nb_site["id"], "status": "active"})
        if created:
            print(f"  Created device: {name}")
        return device

    def sync_storage_pools(self, device):
        """Sync TrueNAS storage pools as device comments (no custom-field dependency)"""
        pools = self.get_truenas_data('pool')

        pool_lines = []
        for pool in pools:
            name = pool.get('name')
            status = pool.get('status')
            pool_lines.append(f"{name}: {status}")
            print(f"  Pool: {name} - {status}")

        if not pool_lines:
            return

        pool_section = "=== TrueNAS Pools ===\n" + "\n".join(pool_lines)
        self.nb.update("dcim", "devices", device["id"], {"comments": pool_section})

    def sync_network_interfaces(self, device):
        """Sync TrueNAS network interfaces to NetBox"""
        interfaces = self.get_truenas_data('interface')

        for iface in interfaces:
            name = iface.get('name')
            if not name:
                continue
            mac = iface.get('state', {}).get('link_address', '')
            mtu = iface.get('mtu', 1500)
            enabled = iface.get('state', {}).get('active', False)

            # Get or create interface
            nb_iface, created = self.nb.get_or_create(
                "dcim", "interfaces", {"device_id": device["id"], "name": name},
                {"device": device["id"], "name": name, "type": "1000base-t",
                 "mac_address": mac if mac else None, "mtu": mtu, "enabled": enabled})
            if created:
                print(f"  Created interface: {name}")
            else:
                self.nb.update("dcim", "interfaces", nb_iface["id"],
                               {"mac_address": mac if mac else None,
                                "mtu": mtu, "enabled": enabled})
                print(f"  Updated interface: {name}")

            # Sync IP addresses
            for alias in iface.get('state', {}).get('aliases', []):
                if alias.get('type') == 'INET':
                    address = alias.get('address')
                    netmask = alias.get('netmask')
                    if address and netmask:
                        cidr = f"{address}/{netmask}"
                        existing = self.nb.get("ipam", "ip-addresses", address=cidr)
                        if not existing:
                            self.nb.create("ipam", "ip-addresses",
                                           {"address": cidr,
                                            "assigned_object_type": "dcim.interface",
                                            "assigned_object_id": nb_iface["id"]})
                            print(f"    Added IP: {cidr}")

    def sync_vms(self, device):
        """Sync TrueNAS VMs to NetBox virtual machines"""
        vms = self.get_truenas_data('vm')
        if not vms:
            print("  No VMs (or API unavailable)")
            return

        # Get or create cluster type + cluster
        cluster_type, _ = self.nb.get_or_create(
            "virtualization", "cluster-types", {"name": "KVM"},
            {"name": "KVM", "slug": "kvm"})
        cluster, _ = self.nb.get_or_create(
            "virtualization", "clusters", {"name": "TrueNAS-VMs"},
            {"name": "TrueNAS-VMs", "type": cluster_type["id"]})

        for vm in vms:
            name = vm.get('name')
            if not name:
                continue
            vcpus = vm.get('vcpus', 1)
            memory = vm.get('memory', 1024)
            status = 'active' if vm.get('status', {}).get('state') == 'RUNNING' else 'offline'

            nb_vm, created = self.nb.get_or_create(
                "virtualization", "virtual-machines", {"name": name},
                {"name": name, "cluster": cluster["id"], "vcpus": vcpus,
                 "memory": memory, "status": status})
            if created:
                print(f"  Created VM: {name}")
            else:
                self.nb.update("virtualization", "virtual-machines", nb_vm["id"],
                               {"vcpus": vcpus, "memory": memory, "status": status})
                print(f"  Updated VM: {name}")

    def sync_disks(self, device):
        """Sync TrueNAS disks as NetBox inventory items (hardware CMDB)."""
        disks = self.get_truenas_data('disk')
        if not disks:
            print("  No disk data (or API unavailable)")
            return
        print(f"  Found {len(disks)} disks")
        # clean up stale inventory items first (disks get replaced)
        existing = self.nb.filter("dcim", "inventory-items", device_id=device["id"])
        for item in existing:
            if (item.get("name") or "").startswith("DISK-"):
                try:
                    self.nb.session.delete(
                        f"{self.nb.url}/api/dcim/inventory-items/{item['id']}/")
                except Exception:
                    pass
        for d in disks:
            name = d.get("name")
            if not name:
                continue
            model = d.get("model") or ""
            serial = d.get("serial") or ""
            size_b = d.get("size") or 0
            size_gb = round(size_b / (1024**3), 1) if size_b else 0
            dtype = d.get("type") or ""
            # create inventory item (get-or-create by name)
            item, created = self.nb.get_or_create(
                "dcim", "inventory-items", {"device_id": device["id"], "name": f"DISK-{name}"},
                {"device": device["id"], "name": f"DISK-{name}",
                 "manufacturer": None, "serial": serial,
                 "description": f"{model} ({dtype}) {size_gb} GB"})
            if created:
                print(f"  ✓ Created inventory item: {name} ({model}, {size_gb}GB)")
            else:
                self.nb.update("dcim", "inventory-items", item["id"],
                               {"serial": serial,
                                "description": f"{model} ({dtype}) {size_gb} GB"})
                print(f"  ✓ Updated inventory item: {name}")

    def sync_datasets(self, device):
        """Sync TrueNAS datasets + shares as structured device comments.

        NetBox 4.6 core has no dataset/share model, so the registry lives in
        the truenas01 device comments as a structured, queryable block.
        """
        datasets = self.get_truenas_data('pool/dataset')
        shares = []
        for ep in ['sharing/smb', 'sharing/nfs']:
            data = self.get_truenas_data(ep)
            if data:
                for s in data:
                    s["_kind"] = ep.split("/")[-1]
                shares.extend(data)
        if not datasets:
            print("  No dataset data (or API unavailable)")
            return
        lines = ["TrueNAS datasets/shares (synced):", ""]
        for d in datasets:
            name = d.get("name") or ""
            dtype = d.get("type") or ""
            lines.append(f"  dataset: {name} ({dtype})")
        if shares:
            lines.append("")
            for s in shares:
                if "path" in s:
                    kind = s.get("_kind", "share")
                    path = s.get("path", "")
                    enabled = s.get("enabled")
                    comment = s.get("comment") or ""
                    lines.append(f"  share({kind}): {path} enabled={enabled} {comment}".rstrip())
        block = "\n".join(lines)
        self.nb.update("dcim", "devices", device["id"], {"comments": block})
        print(f"  {len(datasets)} datasets + {len(shares)} shares in device comments")

    def run(self):
        """Execute full sync"""
        print("Starting TrueNAS to NetBox sync...")

        if not TRUENAS_API_KEY:
            print("ERROR: TRUENAS_API_KEY not set (vault item TRUENAS_API_KEY missing?)")
            return

        # Ensure device exists
        print("Ensuring TrueNAS device exists in NetBox...")
        device = self.ensure_device_exists('truenas01', role='storage', site='homelab')

        print("\nSyncing storage pools...")
        self.sync_storage_pools(device)

        print("\nSyncing network interfaces...")
        self.sync_network_interfaces(device)

        print("\nSyncing disks (inventory items)...")
        self.sync_disks(device)

        print("\nSyncing datasets/shares...")
        self.sync_datasets(device)

        print("\nSyncing VMs...")
        self.sync_vms(device)

        print("\n✅ TrueNAS sync complete!")


if __name__ == '__main__':
    sync = TrueNASSync()
    sync.run()
