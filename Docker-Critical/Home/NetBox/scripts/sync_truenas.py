#!/usr/bin/env python3
"""
TrueNAS Scale to NetBox Sync Script
Syncs storage pools, datasets, VMs, and network interfaces from TrueNAS to NetBox
"""

import requests
import pynetbox
import os
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings if using self-signed certs
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Configuration
TRUENAS_URL = os.getenv('TRUENAS_URL', 'https://truenas01.example.com')
TRUENAS_API_KEY = os.getenv('TRUENAS_API_KEY', '')
NETBOX_URL = os.getenv('NETBOX_URL', 'http://localhost:8080')
NETBOX_TOKEN = os.getenv('NETBOX_TOKEN', '')
VERIFY_SSL = os.getenv('VERIFY_SSL', 'false').lower() == 'true'

class TrueNASSync:
    def __init__(self):
        self.truenas = requests.Session()
        self.truenas.headers.update({
            'Authorization': f'Bearer {TRUENAS_API_KEY}',
            'Content-Type': 'application/json'
        })
        self.nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)
        self.nb.http_session.verify = VERIFY_SSL
        
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
        # Get or create device type
        device_type = self.nb.dcim.device_types.get(model='TrueNAS-SCALE')
        if not device_type:
            manufacturer = self.nb.dcim.manufacturers.get(name='iXsystems')
            if not manufacturer:
                manufacturer = self.nb.dcim.manufacturers.create(name='iXsystems', slug='ixsystems')
            device_type = self.nb.dcim.device_types.create(
                manufacturer=manufacturer.id,
                model='TrueNAS-SCALE',
                slug='truenas-scale'
            )
        
        # Get or create site
        nb_site = self.nb.dcim.sites.get(name=site)
        if not nb_site:
            nb_site = self.nb.dcim.sites.create(name=site, slug=site)
        
        # Get or create device role
        nb_role = self.nb.dcim.device_roles.get(name=role)
        if not nb_role:
            nb_role = self.nb.dcim.device_roles.create(
                name=role,
                slug=role,
                color='4caf50'
            )
        
        # Get or create device
        device = self.nb.dcim.devices.get(name=name)
        if not device:
            device = self.nb.dcim.devices.create(
                name=name,
                device_type=device_type.id,
                role=nb_role.id,
                site=nb_site.id
            )
        
        return device
    
    def sync_storage_pools(self, device):
        """Sync TrueNAS storage pools as custom fields"""
        pools = self.get_truenas_data('pool')
        
        pool_data = []
        for pool in pools:
            pool_info = {
                'name': pool.get('name'),
                'status': pool.get('status'),
                'size_bytes': pool.get('topology', {}).get('data', [{}])[0].get('stats', {}).get('size', 0),
                'allocated_bytes': pool.get('topology', {}).get('data', [{}])[0].get('stats', {}).get('allocated', 0),
                'free_bytes': pool.get('topology', {}).get('data', [{}])[0].get('stats', {}).get('free', 0),
            }
            pool_data.append(pool_info)
            print(f"  Pool: {pool_info['name']} - {pool_info['status']}")
        
        # Update device custom field (you'll need to create this custom field in NetBox)
        device.custom_fields['storage_pools'] = str(pool_data)
        device.save()
        
        return pool_data
    
    def sync_network_interfaces(self, device):
        """Sync TrueNAS network interfaces to NetBox"""
        interfaces = self.get_truenas_data('interface')
        
        for iface in interfaces:
            name = iface.get('name')
            mac = iface.get('state', {}).get('link_address', '')
            mtu = iface.get('mtu', 1500)
            enabled = iface.get('state', {}).get('active', False)
            
            # Get or create interface
            nb_iface = self.nb.dcim.interfaces.get(device_id=device.id, name=name)
            if not nb_iface:
                nb_iface = self.nb.dcim.interfaces.create(
                    device=device.id,
                    name=name,
                    type='1000base-t',
                    mac_address=mac if mac else None,
                    mtu=mtu,
                    enabled=enabled
                )
                print(f"  Created interface: {name}")
            else:
                # Update existing
                nb_iface.mac_address = mac if mac else None
                nb_iface.mtu = mtu
                nb_iface.enabled = enabled
                nb_iface.save()
                print(f"  Updated interface: {name}")
            
            # Sync IP addresses
            for alias in iface.get('state', {}).get('aliases', []):
                if alias.get('type') == 'INET':
                    address = alias.get('address')
                    netmask = alias.get('netmask')
                    if address and netmask:
                        cidr = f"{address}/{netmask}"
                        nb_ip = self.nb.ipam.ip_addresses.get(address=cidr)
                        if not nb_ip:
                            nb_ip = self.nb.ipam.ip_addresses.create(
                                address=cidr,
                                assigned_object_type='dcim.interface',
                                assigned_object_id=nb_iface.id
                            )
                            print(f"    Added IP: {cidr}")
    
    def sync_vms(self, device):
        """Sync TrueNAS VMs to NetBox virtual machines"""
        vms = self.get_truenas_data('vm')
        
        # Get or create cluster
        cluster = self.nb.virtualization.clusters.get(name='TrueNAS-VMs')
        if not cluster:
            cluster_type = self.nb.virtualization.cluster_types.get(name='KVM')
            if not cluster_type:
                cluster_type = self.nb.virtualization.cluster_types.create(
                    name='KVM',
                    slug='kvm'
                )
            cluster = self.nb.virtualization.clusters.create(
                name='TrueNAS-VMs',
                type=cluster_type.id
            )
        
        for vm in vms:
            name = vm.get('name')
            vcpus = vm.get('vcpus', 1)
            memory = vm.get('memory', 1024)
            status = 'active' if vm.get('status', {}).get('state') == 'RUNNING' else 'offline'
            
            # Get or create VM
            nb_vm = self.nb.virtualization.virtual_machines.get(name=name)
            if not nb_vm:
                nb_vm = self.nb.virtualization.virtual_machines.create(
                    name=name,
                    cluster=cluster.id,
                    vcpus=vcpus,
                    memory=memory,
                    status=status
                )
                print(f"  Created VM: {name}")
            else:
                nb_vm.vcpus = vcpus
                nb_vm.memory = memory
                nb_vm.status = status
                nb_vm.save()
                print(f"  Updated VM: {name}")
    
    def run(self):
        """Execute full sync"""
        print("Starting TrueNAS to NetBox sync...")
        
        if not TRUENAS_API_KEY or not NETBOX_TOKEN:
            print("ERROR: TRUENAS_API_KEY and NETBOX_TOKEN must be set")
            return
        
        # Ensure device exists
        print("Ensuring TrueNAS device exists in NetBox...")
        device = self.ensure_device_exists('truenas01', role='storage', site='homelab')
        
        print("\nSyncing storage pools...")
        self.sync_storage_pools(device)
        
        print("\nSyncing network interfaces...")
        self.sync_network_interfaces(device)
        
        print("\nSyncing VMs...")
        self.sync_vms(device)
        
        print("\n✅ TrueNAS sync complete!")

if __name__ == '__main__':
    sync = TrueNASSync()
    sync.run()
