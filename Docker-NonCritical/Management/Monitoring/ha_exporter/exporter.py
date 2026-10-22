#!/usr/bin/env python3
"""
Minimal Home Assistant -> Prometheus exporter.

No HA-side configuration required: uses a long-lived access token against the
existing HA REST API (/api/states). A background thread refreshes entity state
every REFRESH seconds; the /metrics handler serves the cached snapshot so we
never hammer HA on every Prometheus scrape.

Only tracks NUMERIC entity states (temperatures, power, humidity, counters...).
Non-numeric states are skipped (e.g. "home"/"away" would need a relabel mapper).

Env:
  HA_URL        base URL, e.g. https://192.168.19.50:8123
  HA_TOKEN      long-lived token (Profile -> Long-lived access tokens)
  HA_ENTITIES   comma-separated entity_ids to track
  REFRESH       background refresh interval in seconds (default 15)
  PORT          listen port (default 9197)
"""
import os
import time
import threading
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ha_exporter")

HA_URL = os.environ.get("HA_URL", "https://192.168.19.50:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
if not HA_TOKEN:
    tok_file = os.environ.get("HA_TOKEN_FILE")
    if tok_file and os.path.exists(tok_file):
        HA_TOKEN = open(tok_file).read().strip()
HA_ENTITIES = [e.strip() for e in os.environ.get("HA_ENTITIES", "").split(",") if e.strip()]
REFRESH = int(os.environ.get("REFRESH", "15"))
PORT = int(os.environ.get("PORT", "9197"))

METRIC = Gauge(
    "ha_entity_state",
    "Latest numeric state of a Home Assistant entity",
    ["entity", "friendly_name", "unit"],
)
UP = Gauge("ha_up", "1 if the Home Assistant API is reachable")
LOCK = threading.Lock()
LAST_OK = {"ok": False}


def _fetch(path):
    req = Request(f"{HA_URL}{path}", headers={"Authorization": f"Bearer {HA_TOKEN}"})
    with urlopen(req, timeout=10) as r:
        import json
        return json.loads(r.read().decode())


def refresh():
    while True:
        try:
            # Fetch only the entities we care about, in one batched call each.
            states = _fetch("/api/states")
            by_id = {s["entity_id"]: s for s in states}
            wanted = HA_ENTITIES or list(by_id.keys())
            with LOCK:
                METRIC.clear()
                for eid in wanted:
                    s = by_id.get(eid)
                    if not s:
                        continue
                    raw = s.get("state", "")
                    try:
                        val = float(raw)
                    except (TypeError, ValueError):
                        continue  # non-numeric (e.g. 'home', 'off', 'unknown')
                    attrs = s.get("attributes", {})
                    fn = attrs.get("friendly_name", eid)
                    unit = attrs.get("unit_of_measurement", "") or ""
                    METRIC.labels(entity=eid, friendly_name=fn, unit=unit).set(val)
                UP.set(1)
                LAST_OK["ok"] = True
            log.info("refreshed %d entities", len(wanted))
        except (URLError, HTTPError, TimeoutError, KeyError, ValueError) as exc:
            log.warning("refresh failed: %s", exc)
            with LOCK:
                UP.set(0)
                LAST_OK["ok"] = False
        time.sleep(REFRESH)


if __name__ == "__main__":
    if not HA_TOKEN:
        log.warning("HA_TOKEN not set - exporter will report ha_up=0 until configured")
    threading.Thread(target=refresh, daemon=True).start()
    log.info("listening on :%d", PORT)
    # Keep the /metrics endpoint alive via prometheus_client's default handler.
    from prometheus_client import REGISTRY
    import http.server

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/metrics" or self.path == "/":
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
