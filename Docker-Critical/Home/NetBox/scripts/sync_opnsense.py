#!/usr/bin/env python3
"""OPNsense -> NetBox sync (requests-only; uses nb_rest helper).

Syncs: device, interfaces (+IPs), VLANs, routes from OPNsense to NetBox.
Run inside the NetBox container:
    docker exec -e NETBOX_URL=... -e NETBOX_TOKEN=... netbox \
        /opt/netbox/venv/bin/python /opt/netbox/netbox/scripts/sync_opnsense.py
"""
import os
import sys
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from nb_rest import secret_env
import nb_rest

OPNSENSE_URL = os.getenv("OPNSENSE_URL", "https://<REDACTED_HOST>").rstrip("/")
OPNSENSE_API_KEY = secret_env("OPNSENSE_API_KEY")
OPNSENSE_API_SECRET = secret_env("OPNSENSE_API_SECRET")
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() == "true"
SITE = os.getenv("NETBOX_SITE", "homelab")


def opnsense_get(endpoint):
    url = f"{OPNSENSE_URL}/api/{endpoint}"
    r = requests.get(url, auth=(OPNSENSE_API_KEY, OPNSENSE_API_SECRET), verify=VERIFY_SSL)
    r.raise_for_status()
    return r.json()


def ensure_device(nb, name, role="firewall"):
    manufacturer, _ = nb.get_or_create("dcim", "manufacturers", {"name": "Deciso"},
                                        {"name": "Deciso", "slug": "deciso"})
    device_type, _ = nb.get_or_create("dcim", "device-types", {"model": "OPNsense"},
                                       {"manufacturer": manufacturer["id"],
                                        "model": "OPNsense", "slug": "opnsense"})
    site, _ = nb.get_or_create("dcim", "sites", {"name": SITE}, {"name": SITE, "slug": SITE})
    dev_role, _ = nb.get_or_create("dcim", "device-roles", {"name": role},
                                    {"name": role, "slug": role, "color": "f44336"})
    device, created = nb.get_or_create("dcim", "devices", {"name": name},
                                       {"name": name, "device_type": device_type["id"],
                                        "role": dev_role["id"], "site": site["id"]})
    if created:
        print(f"  Created device: {name}")
    return device


def sync_interfaces(nb, device):
    data = opnsense_get("interfaces/overview/export")
    if isinstance(data, dict):
        rows = data.get("rows", [])
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    if not rows:
        print("  No interface data")
        return
    for iface in rows:
        cfg = iface.get("config", {}) or {}
        ident = iface.get("identifier") or ""
        name = cfg.get("descr") or ident
        if not name:
            continue  # skip unconfigured/blank interfaces
        mac = iface.get("macaddr") or None
        ip = cfg.get("ipaddr")
        if ip in (None, "", "dhcp", "None"):
            ip = None
        status = (iface.get("status") or "").lower()
        enabled = status == "up"
        nb_iface, created = nb.get_or_create(
            "dcim", "interfaces", {"device_id": device["id"], "name": name},
            {"device": device["id"], "name": name, "type": "1000base-t",
             "enabled": enabled, "description": ident})
        if not created:
            nb.update("dcim", "interfaces", nb_iface["id"],
                      {"mac_address": mac, "enabled": enabled,
                       "description": ident})
            print(f"  Updated interface: {name}")
        else:
            print(f"  Created interface: {name}")
        if ip:
            existing = nb.get("ipam", "ip-addresses", address=ip)
            if not existing:
                nb.create("ipam", "ip-addresses",
                          {"address": ip, "assigned_object_type": "dcim.interface",
                           "assigned_object_id": nb_iface["id"]})
                print(f"    Added IP: {ip}")


def sync_vlans(nb):
    data = opnsense_get("interfaces/vlan_settings/searchItem")
    rows = data.get("rows", []) if isinstance(data, dict) else []
    for vlan in rows:
        vid = vlan.get("tag")
        if not vid:
            continue
        name = vlan.get("descr") or f"VLAN{vid}"
        _, created = nb.get_or_create("ipam", "vlans", {"vid": vid},
                                      {"vid": vid, "name": name})
        print(f"  {'Created' if created else 'Exists'} VLAN: {vid} - {name}")


def sync_routes(nb):
    """Create IPAM prefixes from OPNsense interface subnet routes.

    The routes/routes/searchRoute endpoint returns 0 rows on this build, but
    interfaces/overview/export carries each interface's connected subnets in
    the per-interface 'routes' list (e.g. ['<REDACTED_IP>/24']). Use that as
    the prefix source so client IPs can be assigned correct prefix lengths.
    """
    import ipaddress
    data = opnsense_get("interfaces/overview/export")
    rows = data if isinstance(data, list) else (data.get("rows", []) if isinstance(data, dict) else [])
    seen = set()
    created = 0
    for iface in rows:
        for route in (iface.get("routes") or []):
            try:
                net = ipaddress.ip_network(route, strict=False)
            except Exception:
                continue
            if not net.prefixlen < 32:  # skip host routes
                continue
            if str(net) in seen:
                continue
            seen.add(str(net))
            _, made = nb.get_or_create("ipam", "prefixes", {"prefix": str(net)},
                                       {"prefix": str(net), "status": "active",
                                        "description": f"OPNsense connected subnet"})
            if made:
                created += 1
                print(f"  Created prefix: {net}")
    print(f"  Prefixes: {len(seen)} subnets ({created} new)")


def main():
    if not (OPNSENSE_API_KEY and OPNSENSE_API_SECRET):
        print("ERROR: OPNSENSE_API_KEY / OPNSENSE_API_SECRET not set")
        return
    nb = nb_rest.NetBox()
    print("Starting OPNsense -> NetBox sync...")
    device = ensure_device(nb, "opnsense")
    print("Syncing interfaces...")
    sync_interfaces(nb, device)
    print("Syncing VLANs...")
    sync_vlans(nb)
    print("Syncing routes...")
    sync_routes(nb)
    print("OPNsense sync complete.")


if __name__ == "__main__":
    main()
