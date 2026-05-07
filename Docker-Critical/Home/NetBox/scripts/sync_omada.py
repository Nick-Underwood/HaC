#!/usr/bin/env python3
"""
Omada Controller to NetBox Sync Script
Syncs access points, switches, and network topology from Omada SDN Controller to NetBox
"""

import requests
import pynetbox
import os
import json
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings if using self-signed certs
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Configuration
OMADA_URL = os.getenv('OMADA_URL', 'https://omada.example.com')
OMADA_USERNAME = os.getenv('OMADA_USERNAME', '')
OMADA_PASSWORD = os.getenv('OMADA_PASSWORD', '')
OMADA_SITE_NAME = os.getenv('OMADA_SITE_NAME', 'Default')
NETBOX_URL = os.getenv('NETBOX_URL', 'http://localhost:8080')
NETBOX_TOKEN = os.getenv('NETBOX_TOKEN', '')
VERIFY_SSL = os.getenv('VERIFY_SSL', 'false').lower() == 'true'

class OmadaSync:
    def __init__(self):
        self.session = requests.Session()
        self.nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)
        self.nb.http_session.verify = VERIFY_SSL
        self.omada_token = None
        self.controller_id = None
        self.site_id = None
        
    def login(self):
        """Login to Omada Controller and get auth token"""
        url = f"{OMADA_URL}/api/v2/login"
        payload = {
            "username": OMADA_USERNAME,
            "password": OMADA_PASSWORD
        }
        
        try:
            response = self.session.post(url, json=payload, verify=VERIFY_SSL)
            response.raise_for_status()
            data = response.json()
            
            if data.get('errorCode') == 0:
                self.omada_token = data['result']['token']
                self.session.headers.update({'Csrf-Token': self.omada_token})
                print("✓ Logged in to Omada Controller")
                return True
            else:
                print(f"✗ Login failed: {data.get('msg', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"✗ Error logging in to Omada: {e}")
            return False
    
    def get_controller_info(self):
        """Get Omada controller ID"""
        url = f"{OMADA_URL}/api/v2/controllers"
        try:
            response = self.session.get(url, verify=VERIFY_SSL)
            response.raise_for_status()
            data = response.json()
            
            if data.get('errorCode') == 0 and data['result']:
                self.controller_id = data['result'][0]['omadacId']
                print(f"✓ Found controller ID: {self.controller_id}")
                return True
        except Exception as e:
            print(f"✗ Error getting controller info: {e}")
        return False
    
    def get_site_id(self):
        """Get site ID by name"""
        url = f"{OMADA_URL}/api/v2/controllers/{self.controller_id}/sites"
        try:
            response = self.session.get(url, verify=VERIFY_SSL)
            response.raise_for_status()
            data = response.json()
            
            if data.get('errorCode') == 0:
                for site in data['result']:
                    if site['name'] == OMADA_SITE_NAME:
                        self.site_id = site['id']
                        print(f"✓ Found site '{OMADA_SITE_NAME}': {self.site_id}")
                        return True
                print(f"✗ Site '{OMADA_SITE_NAME}' not found")
        except Exception as e:
            print(f"✗ Error getting site info: {e}")
        return False
    
    def get_omada_data(self, endpoint):
        """Fetch data from Omada API"""
        url = f"{OMADA_URL}/api/v2/controllers/{self.controller_id}/sites/{self.site_id}/{endpoint}"
        try:
            response = self.session.get(url, verify=VERIFY_SSL)
            response.raise_for_status()
            data = response.json()
            
            if data.get('errorCode') == 0:
                return data.get('result', {})
            else:
                print(f"✗ API error for {endpoint}: {data.get('msg', 'Unknown error')}")
        except Exception as e:
            print(f"✗ Error fetching {endpoint}: {e}")
        return {}
    
    def ensure_manufacturer(self, name):
        """Ensure manufacturer exists in NetBox"""
        manufacturer = self.nb.dcim.manufacturers.get(name=name)
        if not manufacturer:
            manufacturer = self.nb.dcim.manufacturers.create(
                name=name,
                slug=name.lower().replace(' ', '-')
            )
        return manufacturer
    
    def ensure_site(self, name):
        """Ensure site exists in NetBox"""
        site = self.nb.dcim.sites.get(name=name)
        if not site:
            site = self.nb.dcim.sites.create(
                name=name,
                slug=name.lower().replace(' ', '-')
            )
        return site
    
    def ensure_device_role(self, name, color='2196f3'):
        """Ensure device role exists in NetBox"""
        role = self.nb.dcim.device_roles.get(name=name)
        if not role:
            role = self.nb.dcim.device_roles.create(
                name=name,
                slug=name.lower().replace(' ', '-'),
                color=color
            )
        return role
    
    def ensure_device_type(self, manufacturer, model):
        """Ensure device type exists in NetBox"""
        device_type = self.nb.dcim.device_types.get(model=model)
        if not device_type:
            device_type = self.nb.dcim.device_types.create(
                manufacturer=manufacturer.id,
                model=model,
                slug=model.lower().replace(' ', '-').replace('(', '').replace(')', '')
            )
        return device_type
    
    def sync_access_points(self):
        """Sync Omada access points to NetBox"""
        print("\n=== Syncing Access Points ===")
        aps_data = self.get_omada_data('eaps')
        
        if not aps_data or 'data' not in aps_data:
            print("  No access point data available")
            return
        
        site = self.ensure_site('homelab')
        role = self.ensure_device_role('access-point', color='4caf50')
        manufacturer = self.ensure_manufacturer('TP-Link')
        
        for ap in aps_data.get('data', []):
            name = ap.get('name', ap.get('mac', 'unknown'))
            model = ap.get('model', 'Unknown AP')
            mac = ap.get('mac', '')
            ip = ap.get('ip', '')
            status = ap.get('status', 0)
            uptime = ap.get('uptime', 0)
            clients = ap.get('clients', 0)
            
            # Create device type if needed
            device_type = self.ensure_device_type(manufacturer, model)
            
            # Get or create device
            device = self.nb.dcim.devices.get(name=name)
            if not device:
                device = self.nb.dcim.devices.create(
                    name=name,
                    device_type=device_type.id,
                    role=role.id,
                    site=site.id,
                    status='active' if status == 1 else 'offline',
                    comments=f"MAC: {mac}\nClients: {clients}\nUptime: {uptime}s"
                )
                print(f"  ✓ Created AP: {name}")
            else:
                # Update status
                device.status = 'active' if status == 1 else 'offline'
                device.comments = f"MAC: {mac}\nClients: {clients}\nUptime: {uptime}s"
                device.save()
                print(f"  ✓ Updated AP: {name}")
            
            # Sync management interface
            if ip and mac:
                self.sync_interface(device, 'Management', ip, mac)
    
    def sync_switches(self):
        """Sync Omada switches to NetBox"""
        print("\n=== Syncing Switches ===")
        switches_data = self.get_omada_data('switches')
        
        if not switches_data or 'data' not in switches_data:
            print("  No switch data available")
            return
        
        site = self.ensure_site('homelab')
        role = self.ensure_device_role('switch', color='ff9800')
        manufacturer = self.ensure_manufacturer('TP-Link')
        
        for switch in switches_data.get('data', []):
            name = switch.get('name', switch.get('mac', 'unknown'))
            model = switch.get('model', 'Unknown Switch')
            mac = switch.get('mac', '')
            ip = switch.get('ip', '')
            status = switch.get('status', 0)
            uptime = switch.get('uptime', 0)
            port_count = switch.get('portNum', 0)
            
            # Create device type if needed
            device_type = self.ensure_device_type(manufacturer, model)
            
            # Get or create device
            device = self.nb.dcim.devices.get(name=name)
            if not device:
                device = self.nb.dcim.devices.create(
                    name=name,
                    device_type=device_type.id,
                    role=role.id,
                    site=site.id,
                    status='active' if status == 1 else 'offline',
                    comments=f"MAC: {mac}\nPorts: {port_count}\nUptime: {uptime}s"
                )
                print(f"  ✓ Created Switch: {name}")
            else:
                # Update status
                device.status = 'active' if status == 1 else 'offline'
                device.comments = f"MAC: {mac}\nPorts: {port_count}\nUptime: {uptime}s"
                device.save()
                print(f"  ✓ Updated Switch: {name}")
            
            # Sync management interface
            if ip and mac:
                self.sync_interface(device, 'Management', ip, mac)
    
    def sync_gateways(self):
        """Sync Omada gateways to NetBox"""
        print("\n=== Syncing Gateways ===")
        gateways_data = self.get_omada_data('gateways')
        
        if not gateways_data or 'data' not in gateways_data:
            print("  No gateway data available")
            return
        
        site = self.ensure_site('homelab')
        role = self.ensure_device_role('router', color='f44336')
        manufacturer = self.ensure_manufacturer('TP-Link')
        
        for gateway in gateways_data.get('data', []):
            name = gateway.get('name', gateway.get('mac', 'unknown'))
            model = gateway.get('model', 'Unknown Gateway')
            mac = gateway.get('mac', '')
            ip = gateway.get('ip', '')
            status = gateway.get('status', 0)
            uptime = gateway.get('uptime', 0)
            
            # Create device type if needed
            device_type = self.ensure_device_type(manufacturer, model)
            
            # Get or create device
            device = self.nb.dcim.devices.get(name=name)
            if not device:
                device = self.nb.dcim.devices.create(
                    name=name,
                    device_type=device_type.id,
                    role=role.id,
                    site=site.id,
                    status='active' if status == 1 else 'offline',
                    comments=f"MAC: {mac}\nUptime: {uptime}s"
                )
                print(f"  ✓ Created Gateway: {name}")
            else:
                # Update status
                device.status = 'active' if status == 1 else 'offline'
                device.comments = f"MAC: {mac}\nUptime: {uptime}s"
                device.save()
                print(f"  ✓ Updated Gateway: {name}")
            
            # Sync management interface
            if ip and mac:
                self.sync_interface(device, 'Management', ip, mac)
    
    def sync_interface(self, device, name, ip_address, mac_address):
        """Create or update interface and IP address"""
        # Get or create interface
        interface = self.nb.dcim.interfaces.get(device_id=device.id, name=name)
        if not interface:
            interface = self.nb.dcim.interfaces.create(
                device=device.id,
                name=name,
                type='other',
                mac_address=mac_address if mac_address else None
            )
        else:
            if mac_address and interface.mac_address != mac_address:
                interface.mac_address = mac_address
                interface.save()
        
        # Create or update IP address
        if ip_address:
            ip_obj = self.nb.ipam.ip_addresses.get(address=f"{ip_address}/24")
            if not ip_obj:
                ip_obj = self.nb.ipam.ip_addresses.create(
                    address=f"{ip_address}/24",
                    status='active',
                    assigned_object_type='dcim.interface',
                    assigned_object_id=interface.id
                )
            else:
                ip_obj.assigned_object_type = 'dcim.interface'
                ip_obj.assigned_object_id = interface.id
                ip_obj.save()
    
    def run(self):
        """Main sync routine"""
        print("Starting Omada Controller sync...")
        
        if not self.login():
            return False
        
        if not self.get_controller_info():
            return False
        
        if not self.get_site_id():
            return False
        
        self.sync_access_points()
        self.sync_switches()
        self.sync_gateways()
        
        print("\n✓ Omada sync completed successfully!")
        return True

if __name__ == '__main__':
    sync = OmadaSync()
    success = sync.run()
    exit(0 if success else 1)
