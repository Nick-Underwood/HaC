#!/usr/bin/env python3
"""Create a least-privilege discovery service identity in NetBox.

- A permission group `discovery` scoped to only what the sync script needs
  (view/add/change site + device; view manufacturer for FK lookups).
- A non-superuser `netbox-discovery` account in that group.
- A v1 API token (write_enabled) with an expiry and an IP allowlist, so the
  discovery integration is NOT running as admin and NOT holding a permanent,
  network-unrestricted credential.

Run inside the netbox container:
    docker compose -f netbox.yml exec -T netbox python /opt/netbox/netbox/scripts/create_discovery_identity.py
The script prints the token ONCE (it cannot be retrieved later) -- capture it
and store it as the Forgejo repo SECRET `NETBOX_DISCOVERY_TOKEN`.
"""
import datetime
import os
import sys

# Ensure the Django project root is importable when run directly (not via
# manage.py). The script lives at <project>/netbox/scripts/, so the project
# root is two levels up.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- secret bootstrap -------------------------------------------------------
# NetBox 6.x only reads PLAIN env vars (SECRET_KEY, DB_PASSWORD, ...); it has
# no _FILE support. The container entrypoint wrapper (file-secrets-entrypoint.sh)
# promotes the mounted secret files to plain env vars for the running app, but a
# fresh `docker exec` shell does NOT inherit those. Bootstrap here so this
# script is self-sufficient regardless of how it is invoked.
for name, suffix in (("SECRET_KEY", "netbox_secret_key"),
                     ("DB_PASSWORD", "netbox_db_password"),
                     ("API_TOKEN_PEPPERS", "netbox_api_token_peppers")):
    if not os.environ.get(name):
        p = f"/run/secrets/{suffix}"
        try:
            with open(p) as fh:
                os.environ[name] = fh.read().strip()
        except OSError:
            pass

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netbox.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from users.models import ObjectPermission, Token, Group
from users.choices import TokenVersionChoices

U = get_user_model()

# --- permission group -------------------------------------------------------
group, _ = Group.objects.get_or_create(name="discovery")

ct_site = ContentType.objects.get(app_label="dcim", model="site")
ct_device = ContentType.objects.get(app_label="dcim", model="device")
ct_manuf = ContentType.objects.get(app_label="dcim", model="manufacturer")

needed = [
    (ct_site, ["view", "add", "change"]),
    (ct_device, ["view", "add", "change"]),
    (ct_manuf, ["view"]),
]
for ct, actions in needed:
    for action in actions:
        perm, _ = ObjectPermission.objects.get_or_create(
            name=f"discovery-{ct.model}-{action}",
            defaults={
                "enabled": True,
                "actions": [action],
                "constraints": {},
            },
        )
        perm.object_types.add(ct)
        perm.groups.add(group)
        perm.save()
print("permission group 'discovery' configured")

# --- service user -----------------------------------------------------------
user, created = U.objects.get_or_create(
    username="netbox-discovery",
    defaults={
        "email": "<REDACTED_EMAIL>",
        "is_active": True,
        "is_superuser": False,
    },
)
user.groups.add(group)
user.save()
print(f"user netbox-discovery ({'created' if created else 'exists'})")

# --- scoped token -----------------------------------------------------------
expires = datetime.date.today() + datetime.timedelta(days=365)
token = Token(
    user=user,
    version=TokenVersionChoices.V1,  # v2 is broken for ORM creation in 6.0.7
    write_enabled=True,
    expires=expires,
    allowed_ips=["<REDACTED_IP>/24"],  # only the LAN subnet running discovery
    description="OPNsense/Omada discovery integration (Hermes/Forgejo CI)",
)
token.save()
# NetBox 6.0.7 stores the actual secret in `token.token` (the `key` property
# returns a masked value for v1 tokens). Use `token.token` as the credential.
print("=== DISCOVERY TOKEN (store as Forgejo SECRET NETBOX_DISCOVERY_TOKEN) ===")
print(token.token)
print(f"=== expires {expires.isoformat()} | allowed_ips <REDACTED_IP>/24 ===")
