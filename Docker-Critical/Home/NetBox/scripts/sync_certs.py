#!/usr/bin/env python3
"""
Traefik/Let's Encrypt cert registry -> NetBox device comments (host-side).

NetBox 4.6 core has no certificates model (no core/certificates, no plugins),
so the fleet cert registry is written as a structured block in each traefik
host device's comments: one line per cert with main domain, SANs, issuer,
expiry, and days-remaining.

Runs ON a docker host: reads acme.json via `docker cp traefik:/etc/traefik/
acme.json` (docker group, no root needed). Covers the LOCAL traefik; pass
REMOTE_HOSTS to also pull other hosts' traefik certs (runs ssh + docker cp
there). HTTP-only vs NetBox (nb_rest).

Env: NETBOX_URL, NETBOX_TOKEN_FILE (as sync_docker.py), REMOTE_HOSTS
(space-separated, e.g. "<REDACTED_IP>"), SSH_KEY path optional.
"""

import base64
import datetime
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile

sys.path.insert(0, "/srv/netbox/scripts")
from nb_rest import NetBox

ACME_PATHS = ["/etc/traefik/acme.json", "/etc/traefik/acme.json.bak"]
REMOTE_HOSTS = os.getenv("REMOTE_HOSTS", "").split()
HOST = os.getenv("DOCKER_HOST_NAME", "Docker-Critical")


def fetch_acme_local():
    """docker cp acme.json out of the local traefik container."""
    for i, path in enumerate(ACME_PATHS):
        dst = f"/tmp/acme_local{i}.json"
        r = subprocess.run(["docker", "cp", f"traefik:{path}", dst],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return dst
    return None


def fetch_acme_remote(host):
    """ssh + docker cp on a remote host."""
    dst = f"/tmp/acme_{host.replace('.', '_')}.json"
    cmd = (f"docker cp traefik:/etc/traefik/acme.json /tmp/acme_remote.json && "
           f"cat /tmp/acme_remote.json")
    ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
               "-o", "StrictHostKeyChecking=accept-new",
               f"nicholas@{host}", cmd]
    r = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    with open(dst, "w") as f:
        f.write(r.stdout)
    return dst


def parse_certs(acme_path):
    """Parse acme.json -> list of {main, sans, issuer, not_after, serial}."""
    try:
        with open(acme_path) as f:
            data = json.load(f)
    except Exception as e:
        print(f"  ✗ cannot read {acme_path}: {e}")
        return []
    certs = []
    for resolver, rdata in data.items():
        for c in (rdata.get("Certificates") or []):
            dom = c.get("domain") or {}
            main = dom.get("main") or ""
            sans = list(dom.get("sans") or [])
            if not main:
                continue
            pem_b64 = c.get("certificate")
            if not pem_b64:
                certs.append({"main": main, "sans": sans, "issuer": "?",
                              "not_after": "?", "serial": "?"})
                continue
            try:
                pem = base64.b64decode(pem_b64).decode("utf-8", "replace")
                with tempfile.NamedTemporaryFile("w", suffix=".pem",
                                                 delete=False) as f:
                    f.write(pem)
                    tmp = f.name
                issuer_cn = ""
                not_after = "?"
                serial = "?"
                try:
                    from cryptography import x509
                    from cryptography.hazmat.backends import default_backend
                    with open(tmp, "rb") as f:
                        cert = x509.load_pem_x509_certificate(
                            f.read(), default_backend())
                    issuer_cn = " ".join(
                        str(v.value) for v in cert.issuer
                        if v.oid._name == "commonName")
                    not_after = cert.not_valid_after.strftime("%b %d %H:%M:%S %Y %Z")
                    serial = str(cert.serial_number)
                except ImportError:
                    # fallback: private stdlib decode (works on CPython)
                    d = ssl._ssl._test_decode_cert(tmp)  # type: ignore[attr-defined]
                    for tup in d.get("issuer", ()):
                        # issuer is nested: ((('commonName','R11'),),) — walk
                        # down until we hit (key, value) pairs
                        flat = tup
                        while isinstance(flat, tuple) and flat and \
                                not (len(flat) == 2 and isinstance(flat[0], str)):
                            flat = flat[0]
                        if isinstance(flat, tuple) and len(flat) == 2 and \
                                flat[0] == "commonName":
                            issuer_cn = flat[1]
                    not_after = d.get("notAfter", "?")
                    serial = d.get("serialNumber", "?")
                os.unlink(tmp)
                certs.append({"main": main, "sans": sans, "issuer": issuer_cn,
                              "not_after": not_after, "serial": serial})
            except Exception as e:
                certs.append({"main": main, "sans": sans, "issuer": f"parse err {e}",
                              "not_after": "?", "serial": "?"})
    return certs


def build_block(certs, host_label):
    lines = [f"TLS certificates ({host_label}, synced):", ""]
    now = datetime.datetime.now(datetime.timezone.utc)
    for c in sorted(certs, key=lambda x: x["main"]):
        na = c["not_after"]
        days = ""
        if na != "?":
            try:
                exp = datetime.datetime.strptime(na, "%b %d %H:%M:%S %Y %Z")
                exp = exp.replace(tzinfo=datetime.timezone.utc)
                days = f" ({int((exp - now).days)}d left)"
            except Exception:
                pass
        sans = ", ".join(c["sans"][:5]) if c["sans"] else ""
        lines.append(f"  {c['main']}{days} | issuer={c['issuer']}"
                     f"{' | san=' + sans if sans else ''}")
    return "\n".join(lines)


def update_device_comments(nb, device_name, block):
    dev = nb.get("dcim", "devices", name=device_name)
    if not dev:
        print(f"  ✗ device {device_name} not found in NetBox")
        return
    existing = dev.get("comments") or ""
    pattern = re.compile(r"TLS certificates \([^\n]*synced\):.*?(?=\n\n|\Z)", re.S)
    if pattern.search(existing):
        # replace the previous synced block, keep the rest
        new_comments = pattern.sub(block.strip(), existing).strip()
    elif existing.strip():
        # no previous block — append
        new_comments = (existing.strip() + "\n\n" + block.strip())
    else:
        new_comments = block.strip()
    if new_comments != existing.strip():
        nb.update("dcim", "devices", dev["id"], {"comments": new_comments})
        print(f"  ✓ updated {device_name} comments")


def main():
    nb = NetBox()
    local = fetch_acme_local()
    sources = [(local, HOST)] if local else []
    for h in REMOTE_HOSTS:
        rp = fetch_acme_remote(h)
        if rp:
            sources.append((rp, f"docker-{h.split('.')[-1]}" if h.split('.')[-1].isdigit() else h))
    if not sources:
        print("✗ no acme.json reachable")
        return 1
    for path, host_label in sources:
        certs = parse_certs(path)
        print(f"  {host_label}: {len(certs)} certs")
        if not certs:
            continue
        # device name = host label (Docker-Critical / Docker-NonCritical);
        # DOCKER_HOST_NAME env overrides (legacy: <REDACTED_HOST>)
        update_device_comments(nb, host_label, build_block(certs, host_label))
    print("✓ cert registry synced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
