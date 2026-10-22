#!/usr/bin/env python3
"""
Dockhand -> NetBox sync (fleet-wide container inventory).

Dockhand (Finsys) is the Docker management UI/agent fleet: one API aggregates
ALL environments (hosts running the hawser agent) — docker-critical (.51),
docker-noncritical (.52), and HAOS add-ons if registered. This script logs in
once and syncs every environment's containers into NetBox as VMs, plus one
container-host device per environment. HTTP-only (requests), runs in the
stock NetBox container — no docker SDK, no per-host cron needed.

Auth: POST /api/auth/login {username,password} -> dockhand_session cookie.
Data:
  GET /api/environments -> [{id, name, host, ...}]
  GET /api/containers?env=<id> -> [{id,name,image,state,status,networks,...}]
  GET /api/stacks?env=<id>     -> [{name, status, ...}]

Creds via secret_env: DOCKHAND_USERNAME / DOCKHAND_PASSWORD (vault item
"netbox dockhand login" -> populate-secrets-v3 writes dockhand_username.txt /
dockhand_password.txt). URL via DOCKHAND_URL env (compose).
"""

import os
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from nb_rest import secret_env, NetBox

DOCKHAND_URL = os.getenv("DOCKHAND_URL", "https://dockhand.u-acres.com").rstrip("/")
DOCKHAND_USERNAME = secret_env("DOCKHAND_USERNAME")
DOCKHAND_PASSWORD = secret_env("DOCKHAND_PASSWORD")
VERIFY_SSL = os.getenv("VERIFY_SSL", "false").lower() == "true"
SITE = os.getenv("NETBOX_SITE", "homelab")


class DockhandSync:
    def __init__(self):
        self.session = requests.Session()
        self.nb = NetBox()

    def login(self):
        """Authenticate to Dockhand. Auth is now ENABLED (2026-08-14) — the
        old 'Authentication is not enabled' fallback is dead code; keep the
        check only to give a clear error if it ever regresses."""
        if not (DOCKHAND_USERNAME and DOCKHAND_PASSWORD):
            print("✗ DOCKHAND_USERNAME / DOCKHAND_PASSWORD not set (vault item 'netbox dockhand login')")
            return False
        try:
            r = self.session.post(f"{DOCKHAND_URL}/api/auth/login",
                                  json={"username": DOCKHAND_USERNAME,
                                        "password": DOCKHAND_PASSWORD},
                                  verify=VERIFY_SSL, timeout=20)
            if r.status_code == 400 and "Authentication is not enabled" in r.text:
                print("✗ Dockhand auth is DISABLED — cannot continue (should be enabled via Authentik)")
                return False
            r.raise_for_status()
            print("✓ Logged in to Dockhand")
            return True
        except Exception as e:
            print(f"✗ Dockhand login failed: {e}")
            return False

    def get(self, path):
        try:
            r = self.session.get(f"{DOCKHAND_URL}{path}", verify=VERIFY_SSL, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"✗ Error fetching {path}: {e}")
            return []

    def ensure_host_device(self, env):
        """One container-host device per Dockhand environment."""
        name = env.get("name") or f"docker-{env.get('id')}"
        host = env.get("host", "")

        manufacturer, _ = self.nb.get_or_create(
            "dcim", "manufacturers", {"name": "Docker"},
            {"name": "Docker", "slug": "docker"})
        device_type, _ = self.nb.get_or_create(
            "dcim", "device-types", {"model": "Docker Host"},
            {"manufacturer": manufacturer["id"], "model": "Docker Host",
             "slug": "docker-host"})
        site, _ = self.nb.get_or_create(
            "dcim", "sites", {"name": SITE}, {"name": SITE, "slug": SITE})
        role, _ = self.nb.get_or_create(
            "dcim", "device-roles", {"name": "container-host"},
            {"name": "container-host", "slug": "container-host", "color": "9c27b0"})

        device, created = self.nb.get_or_create(
            "dcim", "devices", {"name": name},
            {"name": name, "device_type": device_type["id"],
             "role": role["id"], "site": site["id"], "status": "active",
             "comments": f"Dockhand environment {env.get('id')} (hawser@{host})"})
        if not created:
            self.nb.update("dcim", "devices", device["id"],
                           {"comments": f"Dockhand environment {env.get('id')} (hawser@{host})"})
        return device, created

    def ensure_cluster(self, env):
        cluster_type, _ = self.nb.get_or_create(
            "virtualization", "cluster-types", {"name": "Docker"},
            {"name": "Docker", "slug": "docker"})
        site, _ = self.nb.get_or_create(
            "dcim", "sites", {"name": SITE}, {"name": SITE, "slug": SITE})
        cluster, created = self.nb.get_or_create(
            "virtualization", "clusters", {"name": env.get("name") or f"docker-{env.get('id')}"},
            {"name": env.get("name") or f"docker-{env.get('id')}",
             "type": cluster_type["id"], "site": site["id"]})
        return cluster

    def sync_env_containers(self, env):
        env_id = env.get("id")
        env_name = env.get("name")
        containers = self.get(f"/api/containers?env={env_id}")
        if not containers:
            print(f"  No containers for {env_name}")
            return 0

        cluster = self.ensure_cluster(env)
        count = 0
        for c in containers:
            name = c.get("name")
            if not name:
                continue
            image = c.get("image", "unknown")
            state = c.get("state", "")
            status_map = {
                "running": "active", "exited": "offline", "paused": "staged",
                "restarting": "staged", "created": "staged", "dead": "offline",
            }
            nb_status = status_map.get(state, "offline")
            nets = c.get("networks", {}) or {}
            net_str = ", ".join(f"{k}({v.get('ipAddress','')})" for k, v in nets.items())
            comments = f"Image: {image}\nDockhand env: {env_name}\nNetworks: {net_str}"

            vm, created = self.nb.get_or_create(
                "virtualization", "virtual-machines", {"name": name},
                {"name": name, "cluster": cluster["id"], "status": nb_status,
                 "comments": comments})
            if not created:
                self.nb.update("virtualization", "virtual-machines", vm["id"],
                               {"status": nb_status, "comments": comments})
            count += 1
        return count

    def run(self):
        print("Starting Dockhand -> NetBox sync...")
        if not self.login():
            return False

        envs = self.get("/api/environments")
        if not envs:
            print("  No environments registered in Dockhand")
            return False
        print(f"  Environments: {[e.get('name') for e in envs]}")

        total = 0
        for env in envs:
            name = env.get("name") or f"docker-{env.get('id')}"
            print(f"\n=== Env: {name} ({env.get('host')}) ===")
            device, created = self.ensure_host_device(env)
            print(f"  {'✓ Created' if created else '✓ Updated'} host device: {name}")
            n = self.sync_env_containers(env)
            total += n
            print(f"  {n} containers synced")

        print(f"\n✓ Dockhand sync complete ({total} containers total).")
        return True


if __name__ == "__main__":
    sync = DockhandSync()
    ok = sync.run()
    exit(0 if ok else 1)
