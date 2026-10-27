#!/usr/bin/env bash
# populate-secrets-v2.sh — vaultwarden -> Docker-secret bridge, AUTO-DISCOVERING.
#
# v2 (2026-08-11): no hardcoded item/field assumptions. For each needed secret
# it searches the vault by keyword, picks the first matching item, and reads
# the value from the preferred field (falling back to login.password, then
# login.username, then any custom field). Prints a summary to the terminal —
# item name, field used, length — so the operator can verify WITHOUT the value
# ever appearing in logs, chat, or env.
#
# Requires: bw CLI, BW_SERVER set, BW_SESSION unlocked.
#   export PATH="/home/nicholas/.local/bin:$PATH"
#   export BW_SERVER="https://<REDACTED_HOST>"
#   export BW_SESSION="$(bw unlock --raw)"
#   bash /srv/netbox/scripts/populate-secrets-v2.sh
#
# Item-name expectations (override with env):
#   OPNSENSE_KEY_ITEM   (default: OPNSENSE_API_KEY)    -> value in login.password or login.username
#   OPNSENSE_SECRET_ITEM(default: OPNSENSE_API_SECRET) -> value in login.password or login.username
#   OMADA_ITEM          (default: netbox omada login)  -> username / password login fields
#   TRUENAS_ITEM        (default: TRUENAS_API_KEY)     -> value in login.password or login.username
#   OMADA_OPENAPI_ITEM  (default: netbox omada login)  -> optional custom fields client_id / client_secret
set -euo pipefail

SECRETS_DIR="${SECRETS_DIR:-/srv/netbox/secrets}"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

OPNSENSE_KEY_ITEM="${OPNSENSE_KEY_ITEM:-OPNSENSE_API_KEY}"
OPNSENSE_SECRET_ITEM="${OPNSENSE_SECRET_ITEM:-OPNSENSE_API_SECRET}"
OMADA_ITEM="${OMADA_ITEM:-netbox omada login}"
TRUENAS_ITEM="${TRUENAS_ITEM:-TRUENAS_API_KEY}"
OMADA_OPENAPI_ITEM="${OMADA_OPENAPI_ITEM:-netbox omada login}"

# find_value <search-term> <preference:username|password|custom:NAME>
# Prints the value to STDOUT only; prints a summary line to STDERR.
find_value() {
  local term="$1" pref="$2"
  bw list items --search "$term" 2>/dev/null | python3 -c "
import sys, json
term = sys.argv[1].lower()
pref = sys.argv[2]
try:
    items = json.load(sys.stdin)
except Exception:
    items = []
for it in items:
    name = (it.get('name') or '')
    if term.lower() not in name.lower():
        continue
    lg = it.get('login', {}) or {}
    fields = {f.get('name'): f.get('value') for f in it.get('fields', []) or []}
    val, src = None, None
    if pref == 'password':
        val, src = lg.get('password'), 'login.password'
    elif pref == 'username':
        val, src = lg.get('username'), 'login.username'
    elif pref.startswith('custom:'):
        fname = pref.split(':', 1)[1]
        if fname in fields and fields[fname]:
            val, src = fields[fname], f'field:{fname}'
    if not val and lg.get('password'):
        val, src = lg.get('password'), 'login.password (fallback)'
    if not val and lg.get('username'):
        val, src = lg.get('username'), 'login.username (fallback)'
    if not val:
        for fn, fv in fields.items():
            if fv:
                val, src = fv, f'field:{fn} (last resort)'
                break
    print(f'  [{term}] item={name!r} source={src} len={len(val) if val else 0}', file=sys.stderr)
    if val:
        print(val, end='')
    sys.exit(0)
print(f'  [{term}] NOT FOUND (no item matching {term!r})', file=sys.stderr)
sys.exit(1)
" "$term" "$pref" || true
}

write_secret() {  # filename  search-term  preference
  local f="$SECRETS_DIR/$1"
  local v
  v="$(find_value "$2" "$3" 2>>"$SECRETS_DIR/.populate.log")" || true
  if [ -z "$v" ]; then
    echo "  !!! $1 EMPTY (see $SECRETS_DIR/.populate.log)"
    return
  fi
  printf '%s' "$v" > "$f"
  chmod 600 "$f"
  chown root:root "$f" 2>/dev/null || true
  echo "  wrote $f ($(wc -c < "$f") bytes)"
}

echo "Populating Docker-secret files from vaultwarden (auto-discover v2)..."
echo "  (summary lines logged to $SECRETS_DIR/.populate.log)"

write_secret opnsense_api_key     "$OPNSENSE_KEY_ITEM"    password
write_secret opnsense_api_secret  "$OPNSENSE_SECRET_ITEM" password
write_secret omada_username       "$OMADA_ITEM"           username
write_secret omada_password       "$OMADA_ITEM"           password
write_secret omada_openapi_client_id     "$OMADA_OPENAPI_ITEM" "custom:client_id"
write_secret omada_openapi_client_secret "$OMADA_OPENAPI_ITEM" "custom:client_secret"
write_secret truenas_api_key      "$TRUENAS_ITEM"         password

echo "Done. Recreate the netbox container to pick them up:"
echo "  docker compose -f /srv/netbox/netbox.yml up -d netbox"
