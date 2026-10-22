#!/usr/bin/env python3
"""
Custom OPNsense -> Prometheus exporter.

No third-party image needed: authenticates to the OPNsense REST API with a
key/secret and serves interface traffic + gateway health as Prometheus metrics.

OPNsense API auth uses HTTP Basic with "key:secret" as the credentials
(base64 of "key:secret"), NOT the custom Key/X-API-Secret header scheme.

Env:
  OPN_URL          e.g. https://fw.u-acres.com  (default)
  OPN_API_KEY      API key (System -> Access -> Users -> <user> -> API keys)
  OPN_API_SECRET   API secret
  OPN_VERIFY_SSL   "true"/"false" (default true)
  OPN_WAN_IF       comma-separated interface names to tag as WAN (default: wan)
  REFRESH          background refresh seconds (default 15)
  PORT             listen port (default 9196)
"""
import os
import re
import time
import json
import base64
import threading
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
import http.server

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("opnsense_exporter")

OPN_URL = os.environ.get("OPN_URL", "https://fw.u-acres.com").rstrip("/")
OPN_KEY = os.environ.get("OPN_API_KEY", "")
OPN_SECRET = os.environ.get("OPN_API_SECRET", "")
if not OPN_KEY:
    f = os.environ.get("OPN_API_KEY_FILE")
    if f and os.path.exists(f):
        OPN_KEY = open(f).read().strip()
if not OPN_SECRET:
    f = os.environ.get("OPN_API_SECRET_FILE")
    if f and os.path.exists(f):
        OPN_SECRET = open(f).read().strip()
VERIFY = os.environ.get("OPN_VERIFY_SSL", "true").lower() != "false"
WAN_IFS = {i.strip().lower() for i in os.environ.get("OPN_WAN_IF", "wan").split(",") if i.strip()}
REFRESH = int(os.environ.get("REFRESH", "15"))
PORT = int(os.environ.get("PORT", "9196"))

RX_BYTES = Gauge("opnsense_interface_rx_bytes_total", "Cumulative RX bytes", ["interface", "is_wan"])
TX_BYTES = Gauge("opnsense_interface_tx_bytes_total", "Cumulative TX bytes", ["interface", "is_wan"])
RX_PKTS = Gauge("opnsense_interface_rx_packets_total", "Cumulative RX packets", ["interface", "is_wan"])
TX_PKTS = Gauge("opnsense_interface_tx_packets_total", "Cumulative TX packets", ["interface", "is_wan"])
GW_RTT = Gauge("opnsense_gateway_rtt_ms", "Gateway round-trip time (ms)", ["gateway", "name"])
GW_LOSS = Gauge("opnsense_gateway_loss_percent", "Gateway packet loss %", ["gateway", "name"])
GW_STATUS = Gauge("opnsense_gateway_status", "Gateway status (1=up)", ["gateway", "name"])
GW_UP = Gauge("opnsense_up", "1 if OPNsense API reachable")

CTX = None
if not VERIFY:
    import ssl
    CTX = ssl.create_default_context()
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE


def _get(path):
    url = f"{OPN_URL}{path}"
    # OPNsense REST API auth: HTTP Basic with "key:secret" as the username:password.
    creds = base64.b64encode(f"{OPN_KEY}:{OPN_SECRET}".encode()).decode()
    req = Request(url, headers={"Authorization": f"Basic {creds}"})
    kwargs = {"timeout": 10}
    if CTX:
        kwargs["context"] = CTX
    with urlopen(req, **kwargs) as r:
        return json.loads(r.read().decode())


def _to_float(s, default=0.0):
    # OPNsense returns values with unit suffixes, e.g. "20.6 ms", "0.0 %".
    # Extract the leading numeric token.
    try:
        m = re.search(r"-?\d+(?:\.\d+)?", str(s))
        return float(m.group()) if m else default
    except (TypeError, ValueError):
        return default


def refresh():
    while True:
        iface_ok = gw_ok = False
        try:
            stats = _get("/api/diagnostics/interface/getInterfaceStatistics")
            RX_BYTES.clear(); TX_BYTES.clear(); RX_PKTS.clear(); TX_PKTS.clear()
            rows = (stats or {}).get("statistics", {})
            # rows: display-name -> stats dict  (e.g. "[WAN] (igc0) / aa:bb:..")
            for display, row in rows.items() if isinstance(rows, dict) else []:
                name = (row.get("name") or "").lower()
                if not name:
                    continue
                is_wan = "true" if ("[WAN]" in display or name in WAN_IFS) else "false"
                try:
                    RX_BYTES.labels(name, is_wan).set(_to_float(row.get("received-bytes")))
                    TX_BYTES.labels(name, is_wan).set(_to_float(row.get("sent-bytes")))
                    RX_PKTS.labels(name, is_wan).set(_to_float(row.get("received-packets")))
                    TX_PKTS.labels(name, is_wan).set(_to_float(row.get("sent-packets")))
                except (TypeError, ValueError):
                    pass
            iface_ok = True
        except (URLError, HTTPError, TimeoutError, KeyError, ValueError) as exc:
            log.warning("opnsense interface refresh failed: %s", exc)
            RX_BYTES.clear(); TX_BYTES.clear(); RX_PKTS.clear(); TX_PKTS.clear()

        try:
            gw = _get("/api/routes/gateway/status")
            GW_RTT.clear(); GW_LOSS.clear(); GW_STATUS.clear()
            items = (gw or {}).get("items", [])
            for g in items if isinstance(items, list) else []:
                gname = g.get("name") or "unknown"
                GW_RTT.labels(gname, gname).set(_to_float(g.get("delay")))
                GW_LOSS.labels(gname, gname).set(_to_float(g.get("loss")))
                online = str(g.get("status_translated", "")).lower() == "online" or \
                         str(g.get("status", "")).lower() in ("none", "online", "forceup")
                GW_STATUS.labels(gname, gname).set(1 if online else 0)
            gw_ok = True
        except (URLError, HTTPError, TimeoutError, KeyError, ValueError) as exc:
            log.warning("opnsense gateway refresh failed: %s", exc)
            GW_RTT.clear(); GW_LOSS.clear(); GW_STATUS.clear()

        GW_UP.set(1 if (iface_ok and gw_ok) else 0)
        log.info("opnsense refresh ok=%s gateway_ok=%s", iface_ok, gw_ok)
        time.sleep(REFRESH)


if __name__ == "__main__":
    if not OPN_KEY or not OPN_SECRET:
        log.warning("OPN_API_KEY/OPN_API_SECRET not set - metrics will be empty until configured")
    threading.Thread(target=refresh, daemon=True).start()
    log.info("listening on :%d", PORT)

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/metrics", "/"):
                self.send_response(200)
                self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                self.end_headers()
                self.wfile.write(generate_latest(REGISTRY))
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *a):
            pass

    http.server.HTTPServer(("0.0.0.0", PORT), H).serve_forever()
