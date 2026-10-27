#!/usr/bin/env python3
#
# wazuh-watchdog.py  —  host-side Wazuh sentinel for the HaC deployment
# ----------------------------------------------------------------------
# Runs on the <REDACTED_HOST> runner (the host, NOT inside a container).
# The host can reach both the indexer (<REDACTED_IP>:9200, security disabled)
# and ntfy (<REDACTED_IP>, Bearer token) so it is the correct place to:
#
#   1. SELF-HEAL  : if the wazuh-manager container is missing/unhealthy,
#                   bring it back up via the compose file.
#   2. ALERT FWD  : scrape high-severity alerts from the indexer and push
#                   them to ntfy (local, no cloud dependency).
#   3. DIGEST     : a once-daily health summary (agents, alert counts).
#
# Modes:  all | selfheal | alerts | digest
#   systemd timer  -> "all"   every 5 minutes
#   morning cron    -> "digest" once a day
#
import os
import sys
import json
import subprocess
import datetime
import urllib.request
import urllib.error

CFG = {
    "indexer":   "http://<REDACTED_IP>:9200",
    "ntfy_url":  "http://<REDACTED_IP>/wazuh",
    "token_file": "/srv/wazuh/.ntfy_token",
    "compose_file": "/srv/wazuh/security.yaml",
    # Fallback if the deploy workflow hasn't copied the compose yet (or when
    # running from a checkout). First existing path wins.
    "compose_file_candidates": [
        "/srv/wazuh/security.yaml",
        "/srv/wazuh/security/security.yaml",
        "/home/runner/HaC/Docker-NonCritical/Security/security.yaml",
    ],
    "state_dir": "/srv/wazuh/state",
    "alert_level": 12,
    "lookback_min": 6,
}

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_token():
    try:
        with open(CFG["token_file"]) as f:
            return f.read().strip()
    except Exception:
        return os.environ.get("WAZUH_NTFY_TOKEN", "")

def ntfy_post(title, message, priority="default", tags=None):
    token = load_token()
    if not token:
        sys.stderr.write("no ntfy token; skipping post\n")
        return
    req = urllib.request.Request(CFG["ntfy_url"], data=message.encode(), method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Title", title)
    req.add_header("Priority", priority)
    if tags:
        req.add_header("Tags", tags)
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        sys.stderr.write("ntfy post failed: %s\n" % e)

def docker_running(name):
    try:
        out = subprocess.run(["docker", "ps", "--filter", "name=%s" % name,
                              "--format", "{{.Names}}"],
                             capture_output=True, text=True, timeout=15)
        return name in out.stdout
    except Exception:
        return False

def manager_healthy():
    try:
        out = subprocess.run(
            ["docker", "exec", "wazuh-manager",
             "/var/ossec/bin/wazuh-control", "status"],
            capture_output=True, text=True, timeout=20)
        return "wazuh-analysisd is running" in out.stdout
    except Exception:
        return False

def compose_file():
    for p in CFG.get("compose_file_candidates", [CFG["compose_file"]]):
        if os.path.exists(p):
            return p
    return CFG["compose_file"]

def selfheal():
    if docker_running("wazuh-manager") and manager_healthy():
        return False
    ntfy_post("Wazuh manager missing",
              "Self-healing: restarting wazuh-manager container on %s" % now_iso(),
              "high", "warning")
    try:
        subprocess.run(["docker", "compose", "-p", "wazuh", "-f",
                        compose_file(), "up", "-d", "wazuh.manager"],
                       timeout=240, check=False)
        ntfy_post("Wazuh manager recovered",
                  "wazuh-manager brought back up at %s" % now_iso(),
                  "default", "white_check_mark")
    except Exception as e:
        ntfy_post("Wazuh self-heal FAILED", str(e), "urgent", "rotating_light")
    return True

def es_post(query):
    req = urllib.request.Request(
        CFG["indexer"] + "/wazuh-alerts-*/_search",
        data=json.dumps(query).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    raw = urllib.request.urlopen(req, timeout=20).read()
    return json.loads(raw)

def get_alerts():
    since = (datetime.datetime.now(datetime.timezone.utc) -
             datetime.timedelta(minutes=CFG["lookback_min"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = {
        "size": 100,
        "sort": [{"@timestamp": "asc"}],
        "query": {"bool": {"must": [
            {"range": {"rule.level": {"gte": CFG["alert_level"]}}},
            {"range": {"@timestamp": {"gte": since}}},
        ]}},
    }
    try:
        d = es_post(query)
        return [h["_source"] for h in d.get("hits", {}).get("hits", [])]
    except Exception as e:
        sys.stderr.write("alert query failed: %s\n" % e)
        return []

def state_path():
    os.makedirs(CFG["state_dir"], exist_ok=True)
    return os.path.join(CFG["state_dir"], "last_alert_ts")

def read_last_ts():
    try:
        with open(state_path()) as f:
            return f.read().strip()
    except Exception:
        return ""

def write_last_ts(ts):
    with open(state_path(), "w") as f:
        f.write(ts)

def forward_alerts():
    alerts = get_alerts()
    if not alerts:
        return
    last = read_last_ts()
    new = [a for a in alerts if a.get("@timestamp", "") > last]
    for a in new:
        lvl = a.get("rule", {}).get("level", "?")
        desc = a.get("rule", {}).get("description", "alert")
        agent = a.get("agent", {}).get("name", a.get("agent", {}).get("ip", "?"))
        title = "[L%s] %s" % (lvl, desc[:60])
        msg = "agent=%s\n%s" % (agent, desc)
        try:
            lvl_i = int(str(lvl))
        except Exception:
            lvl_i = 0
        pri = "urgent" if lvl_i >= 15 else "high"
        ntfy_post(title, msg, pri, "rotating_light")
    if new:
        write_last_ts(new[-1].get("@timestamp", ""))

def agent_status():
    try:
        out = subprocess.run(
            ["docker", "exec", "wazuh-manager",
             "/var/ossec/bin/agent_control", "-l"],
            capture_output=True, text=True, timeout=20).stdout
        active = out.count("Active")
        disconnected = out.count("Disconnected")
        return active, disconnected, out
    except Exception:
        return 0, 0, ""

def digest():
    since = (datetime.datetime.now(datetime.timezone.utc) -
             datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        q = {"size": 0, "query": {"range": {"@timestamp": {"gte": since}}},
             "aggs": {"by_level": {"range": {"field": "rule.level",
                       "ranges": [{"from": 12, "to": 15, "key": "12-14"},
                                  {"from": 15, "key": "15+"}]}}}}
        d = es_post(q)
        total = d.get("hits", {}).get("total", {})
        total = total.get("value", 0) if isinstance(total, dict) else total
        buckets = {b["key"]: b["doc_count"]
                   for b in d.get("aggregations", {}).get("by_level", {}).get("buckets", [])}
    except Exception as e:
        total, buckets = "?", {}
    active, disconnected, _ = agent_status()
    lines = [
        "Wazuh 24h digest (%s)" % now_iso(),
        "alerts total: %s" % total,
        "high-sev (L12-14): %s" % buckets.get("12-14", 0),
        "critical (L15+): %s" % buckets.get("15+", 0),
        "agents active: %s  disconnected: %s" % (active, disconnected),
    ]
    ntfy_post("Wazuh daily digest", "\n".join(lines), "default", "calendar")

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("selfheal", "all"):
        selfheal()
    if mode in ("alerts", "all"):
        forward_alerts()
    if mode == "digest":
        digest()

if __name__ == "__main__":
    main()
