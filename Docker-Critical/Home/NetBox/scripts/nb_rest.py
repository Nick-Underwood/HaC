#!/usr/bin/env python3
"""Minimal NetBox REST helper (requests-only; no pynetbox dependency).

Provides get-or-create semantics for the sync scripts so they can run inside
the NetBox container (which ships `requests` but not `pynetbox`).

Auth: NetBox v1 token via the `Authorization: Token <token>` header.
"""
import os
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def secret_env(name, default=""):
    """Read a secret: prefer <NAME>_FILE (Docker secret mount), else plain env.

    Matches the repo's Docker-secret convention (./secrets/*.txt -> /run/secrets/*,
    mounted read-only, root-owned, never in plaintext env). Falls back to a plain
    env var for local/dev use.
    """
    path = os.getenv(f"{name}_FILE")
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    return os.getenv(name, default)


NETBOX_URL = os.getenv("NETBOX_URL", "https://netbox.u-acres.com").rstrip("/")
if not NETBOX_URL.startswith(("http://", "https://")):
    NETBOX_URL = "https://" + NETBOX_URL
NETBOX_TOKEN = secret_env("NETBOX_TOKEN")
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() == "true"


class NetBox:
    def __init__(self, url=NETBOX_URL, token=NETBOX_TOKEN, verify=VERIFY_SSL):
        self.url = url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self.session.verify = verify

    def _path(self, app, endpoint):
        return f"{self.url}/api/{app}/{endpoint}/"

    def get(self, app, endpoint, **params):
        """Return first matching object dict or None."""
        r = self.session.get(self._path(app, endpoint), params=params)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", data if isinstance(data, list) else [])
        return results[0] if results else None

    def filter(self, app, endpoint, **params):
        r = self.session.get(self._path(app, endpoint), params=params)
        r.raise_for_status()
        data = r.json()
        return data.get("results", [])

    def create(self, app, endpoint, payload):
        r = self.session.post(self._path(app, endpoint), json=payload)
        if not r.ok:
            raise RuntimeError(f"POST {app}/{endpoint} {r.status_code}: {r.text[:300]}")
        return r.json()

    def update(self, app, endpoint, obj_id, payload):
        r = self.session.patch(self._path(app, endpoint) + f"{obj_id}/", json=payload)
        r.raise_for_status()
        return r.json()

    def get_or_create(self, app, endpoint, lookup, payload):
        """lookup: dict of params to find the existing object.
        payload: fields to set on create (and to merge on update if provided)."""
        existing = self.get(app, endpoint, **lookup)
        if existing:
            return existing, False
        return self.create(app, endpoint, payload), True


if __name__ == "__main__":
    nb = NetBox()
    status = nb.session.get(f"{nb.url}/api/status/").json()
    print("NetBox status:", status.get("django-version"), status.get("hostname"))
