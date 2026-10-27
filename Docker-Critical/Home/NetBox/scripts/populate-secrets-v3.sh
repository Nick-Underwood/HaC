#!/usr/bin/env bash
# populate-secrets-v3.sh — vaultwarden -> Docker-secret bridge, AUTO-DISCOVERING.
#
# v3 (2026-08-11): value flows DIRECTLY bw -> python3 -> file. No shell
# variable capture, no command substitution, no pipefail traps. Python opens
# the target file and writes the value itself. Only lengths/sources print.
#
# Requires: bw CLI, BW_SERVER set, BW_SESSION unlocked.
#   export PATH="/home/nicholas/.local/bin:$PATH"
#   export BW_SERVER="https://<REDACTED_HOST>"
#   export BW_SESSION="$(bw unlock --raw)"
#   bash /srv/netbox/scripts/populate-secrets-v3.sh
set -uo pipefail

SECRETS_DIR="${SECRETS_DIR:-/srv/netbox/secrets}"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

OPNSENSE_KEY_ITEM="${OPNSENSE_KEY_ITEM:-OPNSENSE_API_KEY}"
OPNSENSE_SECRET_ITEM="${OPNSENSE_SECRET_ITEM:-OPNSENSE_API_SECRET}"
OMADA_ITEM="${OMADA_ITEM:-netbox omada login}"
TRUENAS_ITEM="${TRUENAS_ITEM:-TRUENAS_API_KEY}"
OMADA_OPENAPI_ITEM="${OMADA_OPENAPI_ITEM:-netbox omada login}"
DOCKHAND_ITEM="${DOCKHAND_ITEM:-netbox dockhand login}"

write_secret() {  # out_file  search_term  preference
  local out="$SECRETS_DIR/$1.txt" term="$2" pref="$3"
  echo "--- $1 (search: $term, prefer: $pref)"
  bw list items --search "$term" 2>/dev/null | python3 -c '
import sys, json, os
term = sys.argv[1].lower()
pref = sys.argv[2]
out = sys.argv[3]
try:
    items = json.load(sys.stdin)
except Exception:
    items = []
for it in items:
    name = (it.get("name") or "")
    if term not in name.lower():
        continue
    lg = it.get("login", {}) or {}
    fields = {f.get("name"): f.get("value") for f in it.get("fields", []) or []}
    val, src = None, None
    if pref == "password":
        val, src = lg.get("password"), "login.password"
    elif pref == "username":
        val, src = lg.get("username"), "login.username"
    elif pref.startswith("custom:"):
        fname = pref.split(":", 1)[1]
        if fname in fields and fields[fname]:
            val, src = fields[fname], "field:" + fname
        # NOTE: no fallback for custom: prefs — a missing OpenAPI client_id
        # must stay EMPTY, never pick up login.password by accident.
    if not val and pref != "custom:client_id" and pref != "custom:client_secret":
        if lg.get("password"):
            val, src = lg.get("password"), "login.password (fallback)"
        if not val and lg.get("username"):
            val, src = lg.get("username"), "login.username (fallback)"
    if not val:
        for fn, fv in fields.items():
            if fv:
                val, src = fv, "field:" + fn + " (last resort)"
                break
    if val is not None:
        with open(out, "w") as fh:
            fh.write(val)
        os.chmod(out, 0o600)
        print(f"  wrote {out} ({len(val)} bytes) from item={name!r} source={src}")
    else:
        print(f"  !!! {out}: item {name!r} found but no value in {pref}")
    sys.exit(0)
print(f"  !!! {out}: NO item matching {term!r}")
sys.exit(1)
' "$term" "$pref" "$out"
}

echo "Populating Docker-secret files from vaultwarden (v3, direct-write)..."
bw sync >/dev/null 2>&1 || true   # refresh local cache first — web-UI edits are invisible without it
write_secret opnsense_api_key              "$OPNSENSE_KEY_ITEM"    username
write_secret opnsense_api_secret           "$OPNSENSE_KEY_ITEM"    password
write_secret omada_username                "$OMADA_ITEM"           username
write_secret omada_password                "$OMADA_ITEM"           password
write_secret omada_openapi_client_id       "$OMADA_OPENAPI_ITEM"   "custom:client_id"
write_secret omada_openapi_client_secret   "$OMADA_OPENAPI_ITEM"   "custom:client_secret"
write_secret dockhand_username             "$DOCKHAND_ITEM"        username
write_secret dockhand_password             "$DOCKHAND_ITEM"        password
write_secret truenas_api_key               "$TRUENAS_ITEM"         password
echo "Done. Recreate netbox: docker compose -f /srv/netbox/netbox.yml up -d netbox"
