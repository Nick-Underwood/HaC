#!/usr/bin/env python3
"""
Omada Controller -> NetBox sync via the Omada Open API (OAuth2 client_credentials).

Omada controller 6.2.x has NO usable v2 session API for devices/sites
(returns -1600 "Unsupported request path" on every endpoint). The supported
automation path is the Open API:

  POST /openapi/authorize/token?grant_type=client_credentials
       body: {"omadacId": ..., "client_id": ..., "client_secret": ...}
  -> result: {"accessToken": ..., "refreshToken": ..., "expiresIn": ...}
  Auth header on all calls: Authorization: AccessToken=<accessToken>
  GET /openapi/v1/<omadacId>/sites
  GET /openapi/v1/<omadacId>/sites/<siteId>/devices   (APs + switches + gateways)

NetBox writes go through nb_rest (requests-only) — no pynetbox, survives
container recreates. Credentials come from Docker secrets via secret_env():
  OMADA_OPENAPI_CLIENT_ID / OMADA_OPENAPI_CLIENT_SECRET (custom fields on the
  "netbox omada login" vault item), omadacId from /api/info (or OMADA_ID env).
"""

import os
import sys
import time
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from nb_rest import secret_env, NetBox

OMADA_URL = os.getenv("OMADA_URL", "https://<REDACTED_HOST>").rstrip("/")
OMADA_CLIENT_ID = secret_env("OMADA_OPENAPI_CLIENT_ID")
OMADA_CLIENT_SECRET = secret_env("OMADA_OPENAPI_CLIENT_SECRET")
OMADA_ID = os.getenv("OMADA_ID", "")
VERIFY_SSL = os.getenv("VERIFY_SSL", "false").lower() == "true"
SITE = os.getenv("NETBOX_SITE", "homelab")


class OmadaOpenAPI:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.omadac_id = OMADA_ID
        self.token_expires_at = 0

    # ---- auth ----
    def get_omadac_id(self):
        """Fetch omadacId from /api/info if not provided."""
        if self.omadac_id:
            return True
        try:
            r = requests.get(f"{OMADA_URL}/api/info", verify=VERIFY_SSL, timeout=15)
            r.raise_for_status()
            d = r.json()
            if d.get("errorCode") == 0 and d.get("result", {}).get("omadacId"):
                self.omadac_id = d["result"]["omadacId"]
                print(f"✓ omadacId: {self.omadac_id}")
                return True
            print(f"✗ /api/info: {d.get('msg', 'unknown')}")
        except Exception as e:
            print(f"✗ Error fetching omadacId: {e}")
        return False

    def get_token(self):
        """POST /openapi/authorize/token?grant_type=client_credentials."""
        url = f"{OMADA_URL}/openapi/authorize/token"
        params = {"grant_type": "client_credentials"}
        body = {"omadacId": self.omadac_id,
                "client_id": OMADA_CLIENT_ID,
                "client_secret": OMADA_CLIENT_SECRET}
        try:
            r = self.session.post(url, params=params, json=body, verify=VERIFY_SSL, timeout=20)
            r.raise_for_status()
            d = r.json()
            if d.get("errorCode") != 0:
                print(f"✗ Token error: {d.get('msg', d)}")
                return False
            res = d["result"]
            self.access_token = res["accessToken"]
            self.token_expires_at = time.time() + int(res.get("expiresIn", 7200))
            self.session.headers.update({"Authorization": f"AccessToken={self.access_token}"})
            print("✓ OpenAPI token acquired")
            return True
        except Exception as e:
            print(f"✗ Error getting token: {e}")
            return False

    def ensure_token(self):
        if not self.access_token or time.time() >= self.token_expires_at - 300:
            return self.get_token()
        return True

    # ---- data ----
    def api_get(self, path, params=None):
        if not self.ensure_token():
            return None
        try:
            r = self.session.get(f"{OMADA_URL}{path}", params=params or {},
                                 verify=VERIFY_SSL, timeout=30)
            r.raise_for_status()
            d = r.json()
            if d.get("errorCode") == 0:
                return d.get("result")
            print(f"✗ API error {path}: {d.get('msg', d)}")
        except Exception as e:
            print(f"✗ Error fetching {path}: {e}")
        return None

    def get_sites(self):
        # pageSize/page are REQUIRED on Omada 6.2.x — without them the
        # endpoint returns HTTP 400 (Bad Request).
        res = self.api_get(f"/openapi/v1/{self.omadac_id}/sites",
                           {"pageSize": 100, "page": 1})
        return (res or {}).get("data", []) if isinstance(res, dict) else (res or [])

    def get_devices(self, site_id):
        res = self.api_get(f"/openapi/v1/{self.omadac_id}/sites/{site_id}/devices",
                           {"pageSize": 100, "page": 1})
        return (res or {}).get("data", []) if isinstance(res, dict) else (res or [])

    def get_uplinks(self, site_id, device_macs):
        """POST uplink-info: which device uplinks to which switch port."""
        if not device_macs:
            return []
        try:
            r = self.session.post(
                f"{OMADA_URL}/openapi/v1/{self.omadac_id}/sites/{site_id}/devices/uplink-info",
                json={"deviceMacs": device_macs}, verify=VERIFY_SSL, timeout=30)
            r.raise_for_status()
            d = r.json()
            if d.get("errorCode") == 0:
                return d.get("result") or []
            print(f"✗ uplink-info error: {d.get('msg', d)}")
        except Exception as e:
            print(f"✗ uplink-info failed: {e}")
        return []

    def get_ssids(self, site_id):
        """GET wireless-network/ssids?type=3 — list of {wlanId, wlanName,
        ssidList: [{ssidId, ssidName}]}."""
        try:
            r = self.session.get(
                f"{OMADA_URL}/openapi/v1/{self.omadac_id}/sites/{site_id}/wireless-network/ssids",
                params={"pageSize": 100, "page": 1, "type": 3},
                verify=VERIFY_SSL, timeout=30)
            r.raise_for_status()
            d = r.json()
            if d.get("errorCode") == 0:
                return d.get("result") or []
            print(f"✗ ssids error: {d.get('msg', d)}")
        except Exception as e:
            print(f"✗ ssids failed: {e}")
        return []


def _slugify(s):
    """NetBox slug: lowercase alnum + hyphens only. Strips model junk like
    'EAP610-Outdoor(US) v1.0' -> 'eap610-outdoor-us-v10'."""
    import re
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "device"


def ensure_device(nb, name, model, role_name, status, comments, site, manufacturer_name):
    manufacturer, _ = nb.get_or_create("dcim", "manufacturers",
                                       {"name": manufacturer_name},
                                       {"name": manufacturer_name,
                                        "slug": _slugify(manufacturer_name)})
    device_type, _ = nb.get_or_create("dcim", "device-types", {"model": model},
                                      {"manufacturer": manufacturer["id"],
                                       "model": model,
                                       "slug": _slugify(model)})
    dev_role, _ = nb.get_or_create("dcim", "device-roles", {"name": role_name},
                                   {"name": role_name, "slug": _slugify(role_name),
                                    "color": "2196f3"})
    device, created = nb.get_or_create("dcim", "devices", {"name": name},
                                       {"name": name, "device_type": device_type["id"],
                                        "role": dev_role["id"], "site": site["id"],
                                        "status": status, "comments": comments})
    if not created:
        # include role/device_type so pre-existing devices get corrected on re-run
        nb.update("dcim", "devices", device["id"],
                  {"device_type": device_type["id"], "role": dev_role["id"],
                   "status": status, "comments": comments})
    return device, created


def sync_interface(nb, device_id, name, ip, mac):
    iface, created = nb.get_or_create("dcim", "interfaces",
                                      {"device_id": device_id, "name": name},
                                      {"device": device_id, "name": name,
                                       "type": "other", "mac_address": mac or None})
    if not created and mac and iface.get("mac_address") != mac:
        nb.update("dcim", "interfaces", iface["id"], {"mac_address": mac})
    if ip:
        existing = nb.get("ipam", "ip-addresses", address=ip)
        if not existing:
            nb.create("ipam", "ip-addresses",
                      {"address": ip, "status": "active",
                       "assigned_object_type": "dcim.interface",
                       "assigned_object_id": iface["id"]})
        else:
            nb.update("ipam", "ip-addresses", existing["id"],
                      {"assigned_object_type": "dcim.interface",
                       "assigned_object_id": iface["id"]})


def sync_clients(nb, om, site_id):
    """Sync Omada clients to NetBox IPAM as IP addresses.

    Each active client becomes an IP address with dns_name (hostname), MAC +
    AP/SSID context in comments, and the prefix length derived from the
    longest NetBox prefix that contains it (prefixes come from the OPNsense
    route sync). Clients are NOT created as devices — they're endpoints,
    tracked in IPAM only.
    """
    print("\n=== Syncing Clients (IPAM) ===")
    res = om.api_get(f"/openapi/v1/{om.omadac_id}/sites/{site_id}/clients",
                     {"pageSize": 1000, "page": 1})
    clients = (res or {}).get("data", []) if isinstance(res, dict) else (res or [])
    if not clients:
        print("  No clients (or API unavailable)")
        return

    # longest-prefix match helper: pre-fetch all NetBox prefixes once
    # (limit=1000 — NetBox caps MAX_PAGE_SIZE; 2000 raises and yields nothing)
    prefixes = []
    try:
        prefixes = nb.filter("ipam", "prefixes", limit=1000)
    except Exception as e:
        print(f"  (warning: prefix fetch failed: {e})")

    def netmask_for(ip):
        best = None
        for p in prefixes:
            pfx = p.get("prefix", "")
            _, _, plen = pfx.partition("/")
            if not plen:
                continue
            try:
                import ipaddress
                if ipaddress.ip_address(ip) in ipaddress.ip_network(pfx, strict=False):
                    if best is None or int(plen) > best[1]:
                        best = (pfx, int(plen))
            except Exception:
                continue
        if best:
            # return HOST address with mask, e.g. <REDACTED_IP>/24 — NOT the
            # network address (<REDACTED_IP>/24)
            return f"{ip}/{best[1]}"
        return f"{ip}/32"

    def find_existing(ip):
        """NetBox duplicate check is global by host — find ANY IP record with
        this host regardless of prefix (address__startswith)."""
        try:
            hits = nb.filter("ipam", "ip-addresses",
                             **{f"address__startswith": f"{ip}/"})
            return hits[0] if hits else None
        except Exception:
            return None

    seen = 0
    for c in clients:
        ip = c.get("ip")
        if not ip:
            continue
        host = c.get("hostName") or c.get("name") or ""
        mac = c.get("mac") or ""
        devtype = c.get("deviceType") or c.get("deviceCategory") or ""
        vendor = c.get("vendor") or ""
        ssid = c.get("ssid") or ""
        ap = c.get("apName") or ""
        wireless = c.get("wireless")
        active = c.get("active", True)
        osname = c.get("osName") or ""

        addr = netmask_for(ip)
        desc_parts = [x for x in [c.get("name"), devtype, vendor] if x]
        description = " / ".join(desc_parts)[:200]
        comments = f"MAC: {mac}"
        if wireless:
            comments += f"\nSSID: {ssid}\nAP: {ap}"
        if osname:
            comments += f"\nOS: {osname}"

        existing = find_existing(ip)
        # NOTE: never send "address" on update — changing the address of an
        # assigned IP (e.g. an OPNsense interface IP) violates NetBox's
        # unique/assigned constraints and 400s. Host is already correct; the
        # /32-vs-/24 mask on old records is cosmetic, not worth the conflict.
        if not existing:
            try:
                nb.create("ipam", "ip-addresses",
                          {"address": addr, "status": "active" if active else "offline",
                           "dns_name": host[:255] or None, "description": description,
                           "comments": comments})
                print(f"  ✓ Created IP: {addr} ({host or mac})")
            except RuntimeError as e:
                # race / duplicate under a different prefix — adopt it
                existing = find_existing(ip)
                if existing:
                    nb.update("ipam", "ip-addresses", existing["id"],
                              {"status": "active" if active else "offline",
                               "dns_name": host[:255] or None,
                               "description": description, "comments": comments})
                    print(f"  ✓ Adopted existing IP: {ip} ({host or mac})")
                else:
                    print(f"  ✗ Failed to create {ip}: {e}")
        else:
            nb.update("ipam", "ip-addresses", existing["id"],
                      {"status": "active" if active else "offline",
                       "dns_name": host[:255] or None, "description": description,
                       "comments": comments})
            print(f"  ✓ Updated IP: {addr} ({host or mac})")
        seen += 1
    print(f"  {seen} client IPs synced")


def sync_topology(nb, om, site_id, devices):
    """Create NetBox cables from Omada uplink-info.

    uplink-info returns [{mac, uplinkDeviceMac, uplinkDeviceName,
    uplinkDevicePort, linkSpeed}] — i.e. which switch port each AP/switch
    plugs into. Model as dcim/cables between the two devices' Management
    interfaces (we don't know the exact physical port numbers, so cables
    attach at the Management interface level).
    """
    macs = [d.get("mac") for d in devices if d.get("mac")]
    uplinks = om.get_uplinks(site_id, macs)
    if not uplinks:
        print("  No uplink info (or API unavailable)")
        return

    # exact-match cache: all existing cables (NetBox 6 a_terminations/
    # b_terminations are arrays of {object_type, object_id})
    cables = nb.filter("dcim", "cables", limit=500) or []

    # map mac -> device name (both directions: our devices and uplink devices)
    dev_by_mac = {d.get("mac"): d.get("name") for d in devices if d.get("mac")}
    for u in uplinks:
        child_mac = u.get("mac") or u.get("deviceMac")
        up_mac = u.get("uplinkDeviceMac")
        if not child_mac or not up_mac:
            continue
        child_name = dev_by_mac.get(child_mac) or u.get("deviceName") or child_mac
        up_name = dev_by_mac.get(up_mac) or u.get("uplinkDeviceName") or up_mac
        port = u.get("uplinkDevicePort") or "?"
        print(f"  Uplink: {child_name} -> {up_name} port {port}")

        # find both devices' Management interface ids
        child_dev = nb.get("dcim", "devices", name=child_name)
        up_dev = nb.get("dcim", "devices", name=up_name)
        if not (child_dev and up_dev):
            continue
        child_if = nb.get("dcim", "interfaces", device_id=child_dev["id"], name="Management")
        if not child_if:
            print(f"    (missing Management interface on {child_name})")
            continue

        # An interface terminates exactly ONE cable. If the child's Management
        # interface is already cabled (e.g. switch-to-switch Management link
        # from a prior run), skip — no duplicate.
        already_cabled = any(
            child_if["id"] in {t.get("object_id") for t in c.get("a_terminations", [])}
            or child_if["id"] in {t.get("object_id") for t in c.get("b_terminations", [])}
            for c in cables)
        if already_cabled:
            print(f"    = {child_name} Management already cabled (skip)")
            continue

        # The uplink (switch) side gets a PER-PORT interface — an interface can
        # terminate only ONE cable, so the shared "Management" interface can't
        # host multiple AP uplinks. Use "Port <N>" on the switch side.
        up_port_name = f"Port {port}" if port and port != "?" else "Uplink"
        up_if = nb.get("dcim", "interfaces", device_id=up_dev["id"], name=up_port_name)
        if not up_if:
            up_if, _ = nb.get_or_create(
                "dcim", "interfaces", {"device_id": up_dev["id"], "name": up_port_name},
                {"device": up_dev["id"], "name": up_port_name, "type": "1000base-t"})
        # idempotent: exact termination-pair match in Python (never icontains —
        # it substring-matches the JSON, id 1 matches "11"/"10")
        cable = None
        for c in cables:
            aids = {t.get("object_id") for t in c.get("a_terminations", [])}
            bids = {t.get("object_id") for t in c.get("b_terminations", [])}
            if (child_if["id"] in aids and up_if["id"] in bids) or \
               (child_if["id"] in bids and up_if["id"] in aids):
                cable = c
                break
        if not cable:
            try:
                nb.create("dcim", "cables",
                          {"a_terminations": [{"object_type": "dcim.interface",
                                               "object_id": child_if["id"]}],
                           "b_terminations": [{"object_type": "dcim.interface",
                                               "object_id": up_if["id"]}],
                           "label": f"Omada uplink (port {port})"})
                print(f"    ✓ Cable: {child_name} <-> {up_name} {up_port_name}")
            except RuntimeError as e:
                print(f"    ✗ Cable failed: {e}")
        else:
            print(f"    = Cable exists")


def sync_wlans(nb, om, site_id):
    """Sync Omada SSIDs to NetBox WirelessLANs (wireless/wireless-lans).

    The SSIDs endpoint returns {wlanId, wlanName, ssidList:[{ssidId,
    ssidName}]}. Each SSID becomes a WirelessLAN; the WLAN group maps to
    NetBox's WirelessLANGroup (optional, one per wlanName).
    """
    print("\n=== Syncing WLANs (SSIDs) ===")
    wlans = om.get_ssids(site_id)
    if not wlans:
        print("  No WLAN data (or API unavailable)")
        return
    seen = 0
    for w in wlans:
        wlan_name = w.get("wlanName") or "Default"
        for ss in (w.get("ssidList") or []):
            ssid = ss.get("ssidName")
            if not ssid:
                continue
            # map to NetBox wireless LAN (idempotent by ssid name)
            lan, created = nb.get_or_create(
                "wireless", "wireless-lans", {"ssid": ssid},
                {"ssid": ssid, "status": "active",
                 "description": f"Omada WLAN {wlan_name} (ssidId {ss.get('ssidId')})",
                 "comments": f"Omada ssidId: {ss.get('ssidId')}\nWLAN: {wlan_name}\nwlanId: {w.get('wlanId')}"})
            if created:
                print(f"  ✓ Created WirelessLAN: {ssid}")
            else:
                nb.update("wireless", "wireless-lans", lan["id"],
                          {"status": "active",
                           "description": f"Omada WLAN {wlan_name} (ssidId {ss.get('ssidId')})",
                           "comments": f"Omada ssidId: {ss.get('ssidId')}\nWLAN: {wlan_name}\nwlanId: {w.get('wlanId')}"})
            seen += 1
    print(f"  {seen} WLANs synced")


def main():
    if not (OMADA_CLIENT_ID and OMADA_CLIENT_SECRET):
        print("ERROR: OMADA_OPENAPI_CLIENT_ID / OMADA_OPENAPI_CLIENT_SECRET not set")
        print("       (add client_id/client_secret custom fields to the 'netbox omada login' vault item, then re-run populate-secrets-v3.sh)")
        return

    om = OmadaOpenAPI()
    print("Starting Omada (OpenAPI) sync...")
    if not om.get_omadac_id():
        return
    if not om.ensure_token():
        return

    sites = om.get_sites()
    if not sites:
        print("  No sites found")
        return
    print(f"  Sites: {[s.get('name') for s in sites]}")

    nb = NetBox()
    site_obj, _ = nb.get_or_create("dcim", "sites", {"name": SITE},
                                   {"name": SITE, "slug": SITE})

    for site in sites:
        site_id = site.get("siteId") or site.get("id")
        print(f"\n=== Site: {site.get('name')} ({site_id}) ===")
        devices = om.get_devices(site_id)
        if not devices:
            print("  No devices")
        for dev in devices:
            name = dev.get("name") or dev.get("mac") or "unknown"
            model = dev.get("model") or "Unknown"
            mac = dev.get("mac") or ""
            ip = dev.get("ip") or ""
            status = "active" if dev.get("status") == 1 else "offline"
            # map device type/category to a NetBox role (Omada uses "type":
            # ap | switch | gateway; "category" is null in the devices payload)
            typ = (dev.get("type") or dev.get("category") or "").lower()
            if "gateway" in typ or "router" in typ:
                role = "router"
            elif "switch" in typ:
                role = "switch"
            elif typ in ("ap", "eap") or "ap" in typ:
                role = "access-point"
            else:
                role = "device"
            comments = f"MAC: {mac}\nOmada type: {typ}"
            device, created = ensure_device(nb, name, model, role, status, comments,
                                            site_obj, "TP-Link")
            print(f"  {'✓ Created' if created else '✓ Updated'} {role}: {name} ({model})")
            if ip or mac:
                sync_interface(nb, device["id"], "Management", ip, mac)
        sync_topology(nb, om, site_id, devices)
        sync_clients(nb, om, site_id)
        sync_wlans(nb, om, site_id)

    print("\n✓ Omada sync complete.")


if __name__ == "__main__":
    main()
