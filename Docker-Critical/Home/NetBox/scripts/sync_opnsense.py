#!/usr/bin/env python3
"""
OPNsense to NetBox Sync Script
Syncs interfaces, VLANs, firewall rules, and routing from OPNsense to NetBox
"""

import requests
import pynetbox
import os
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings if using self-signed certs
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Configuration
OPNSENSE_URL = os.getenv('OPNSENSE_URL', 'https://opnsense.example.com')
OPNSENSE_API_KEY = os.getenv('OPNSENSE_API_KEY', '')
OPNSENSE_API_SECRET = os.getenv('OPNSENSE_API_SECRET', '')
NETBOX_URL = os.getenv('NETBOX_URL', 'http://localhost:8080')
NETBOX_TOKEN = os.getenv('NETBOX_TOKEN', '')
VERIFY_SSL = os.getenv('VERIFY_SSL', 'false').lower() == 'true'

class OPNsenseSync:
    def __init__(self):
        self.opnsense_session = requests.Session()
        self.opnsense_session.auth = (OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
        self.nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)
        self.nb.http_session.verify = VERIFY_SSL
        
    def get_opnsense_data(self, endpoint):
        """Fetch data from OPNsense API"""
        url = f"{OPNSENSE_URL}/api/{endpoint}"
        try:
            response = self.opnsense_session.get(url, verify=VERIFY_SSL)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching {endpoint}: {e}")
            return {}
    
    def ensure_device_exists(self, name, role='firewall', site='homelab'):
        """Ensure OPNsense device exists in NetBox"""
        # Get or create device type
        device_type = self.nb.dcim.device_types.get(model='OPNsense')
        if not device_type:
            manufacturer = self.nb.dcim.manufacturers.get(name='Deciso')
            if not manufacturer:
                manufacturer = self.nb.dcim.manufacturers.create(name='Deciso', slug='deciso')
            device_type = self.nb.dcim.device_types.create(
                manufacturer=manufacturer.id,
                model='OPNsense',
                slug='opnsense'
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
                color='f44336'
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
    
    def sync_interfaces(self, device):
        """Sync OPNsense interfaces to NetBox"""
        # Note: OPNsense API endpoints vary by version
        # This uses common endpoints - adjust as needed
        interfaces = self.get_opnsense_data('interfaces/overview/export')
        
        if not interfaces or 'rows' not in interfaces:
            print("  No interface data available")
            return
        
        for iface in interfaces.get('rows', []):
            name = iface.get('identifier', iface.get('descr', 'unknown'))
            mac = iface.get('macaddr', '')
            ip = iface.get('ipaddr', '')
            status = iface.get('status', '')
            enabled = status.lower() == 'up'
            
            # Get or create interface
            nb_iface = self.nb.dcim.interfaces.get(device_id=device.id, name=name)
            if not nb_iface:
                nb_iface = self.nb.dcim.interfaces.create(
                    device=device.id,
                    name=name,
                    type='1000base-t',
                    mac_address=mac if mac else None,
                    enabled=enabled,
                    description=iface.get('descr', '')
                )
                print(f"  Created interface: {name}")
            else:
                nb_iface.mac_address = mac if mac else None
                nb_iface.enabled = enabled
                nb_iface.description = iface.get('descr', '')
                nb_iface.save()
                print(f"  Updated interface: {name}")
            
            # Sync IP if present
            if ip and ip != 'None':
                nb_ip = self.nb.ipam.ip_addresses.get(address=ip)
                if not nb_ip:
                    nb_ip = self.nb.ipam.ip_addresses.create(
                        address=ip,
                        assigned_object_type='dcim.interface',
                        assigned_object_id=nb_iface.id
                    )
                    print(f"    Added IP: {ip}")
    
    def sync_vlans(self, device):
        """Sync OPNsense VLANs to NetBox"""
        vlans = self.get_opnsense_data('interfaces/vlan_settings/searchItem')
        
        if not vlans or 'rows' not in vlans:
            print("  No VLAN data available")
            return
        
        for vlan in vlans.get('rows', []):
            vid = vlan.get('tag')
            name = vlan.get('descr', f"VLAN{vid}")
            
            if not vid:
                continue
            
            # Get or create VLAN
            nb_vlan = self.nb.ipam.vlans.get(vid=vid)
            if not nb_vlan:
                nb_vlan = self.nb.ipam.vlans.create(
                    vid=vid,
                    name=name
                )
                print(f"  Created VLAN: {vid} - {name}")
            else:
                nb_vlan.name = name
                nb_vlan.save()
                print(f"  Updated VLAN: {vid} - {name}")
    
    def sync_firewall_rules(self, device):
        """Store firewall rules as device custom field (summary)"""
        rules = self.get_opnsense_data('firewall/filter/searchRule')
        
        if not rules or 'rows' not in rules:
            print("  No firewall rule data available")
            return
        
        rule_count = len(rules.get('rows', []))
        print(f"  Found {rule_count} firewall rules")
        
        # Store rule summary in custom field
        # (Full rule sync would require custom tables or using config contexts)
        device.custom_fields['firewall_rule_count'] = rule_count
        device.save()
    
    def sync_routes(self, device):
        """Sync static routes to NetBox prefixes"""
        routes = self.get_opnsense_data('routes/routes/searchRoute')
        
        if not routes or 'rows' not in routes:
            print("  No route data available")
            return
        
        for route in routes.get('rows', []):
            network = route.get('network')
            gateway = route.get('gateway')
            
            if network:
                # Get or create prefix
                nb_prefix = self.nb.ipam.prefixes.get(prefix=network)
                if not nb_prefix:
                    nb_prefix = self.nb.ipam.prefixes.create(
                        prefix=network,
                        description=f"Route via {gateway}"
                    )
                    print(f"  Created prefix: {network}")
    
    def run(self):
        """Execute full sync"""
        print("Starting OPNsense to NetBox sync...")
        
        if not OPNSENSE_API_KEY or not OPNSENSE_API_SECRET or not NETBOX_TOKEN:
            print("ERROR: OPNSENSE_API_KEY, OPNSENSE_API_SECRET, and NETBOX_TOKEN must be set")
            return
        
        # Ensure device exists
        print("Ensuring OPNsense device exists in NetBox...")
        device = self.ensure_device_exists('opnsense', role='firewall', site='homelab')
        
        print("\nSyncing interfaces...")
        self.sync_interfaces(device)
        
        print("\nSyncing VLANs...")
        self.sync_vlans(device)
        
        print("\nSyncing firewall rules...")
        self.sync_firewall_rules(device)
        
        print("\nSyncing routes...")
        self.sync_routes(device)
        
        print("\n✅ OPNsense sync complete!")

if __name__ == '__main__':
    sync = OPNsenseSync()
    sync.run()
