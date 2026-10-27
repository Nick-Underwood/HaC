#!/usr/bin/env bash
# populate-secrets.sh — bridge vaultwarden -> Docker-secret files.
#
# Authoring store: your local vaultwarden (HAOS <REDACTED_HOST>, https://<REDACTED_HOST>).
# Runtime store: Docker secrets (./secrets/*.txt -> /run/secrets/*, mounted :ro,
# root-owned, never in plaintext env). The sync scripts NEVER talk to Bitwarden
# at runtime — this script runs once (on unlock / before deploy) to materialize
# the files.
#
# Requires: `bw` CLI on PATH, an API-key login, and a one-time `bw unlock`
# (master password — do NOT put it in this script or in chat).
#
# Usage:
#   export BW_SERVER="https://<REDACTED_HOST>"
#   export BW_CLIENTID="user.xxxx" BW_CLIENTSECRET="xxxx"   # from Bitwarden Web UI -> API Key
#   bw login --apikey
#   export BW_SESSION="$(bw unlock --raw)"                   # prompts for master pw
#   ./scripts/populate-secrets.sh
#
# Vault item expectations (custom field names):
#   "OPNsense"         -> api_key,  api_secret
#   "netbox omada login" -> username, password   (NOTE: NOT "Omada" — actual vault item name)
#   "TrueNAS"          -> api_key
# Override item names with env: OPNSENSE_ITEM / OMADA_ITEM / TRUENAS_ITEM.

set -euo pipefail

SECRETS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../secrets" && pwd)"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

bw_v() { bw get item "${1:-}" 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);f={x['name']:x['value'] for x in d.get('fields',[])};print(f.get('$2','') or d.get('login',{}).get('$2',''))" 2>/dev/null || true; }

OPNSENSE_ITEM="${OPNSENSE_ITEM:-OPNsense}"
OMADA_ITEM="${OMADA_ITEM:-netbox omada login}"
TRUENAS_ITEM="${TRUENAS_ITEM:-TrueNAS}"

write_secret() {  # name  value
  local f="$SECRETS_DIR/$1.txt"
  printf '%s' "$2" > "$f"
  chmod 600 "$f"
  chown root:root "$f" 2>/dev/null || true
  echo "  wrote $f"
}

echo "Populating Docker-secret files from vaultwarden..."

write_secret opnsense_api_key    "$(bw_v "$OPNSENSE_ITEM" api_key)"
write_secret opnsense_api_secret "$(bw_v "$OPNSENSE_ITEM" api_secret)"
write_secret omada_username      "$(bw_v "$OMADA_ITEM" username)"
write_secret omada_password      "$(bw_v "$OMADA_ITEM" password)"
write_secret truenas_api_key     "$(bw_v "$TRUENAS_ITEM" api_key)"

echo "Done. Files in $SECRETS_DIR are gitignored and root-owned."
echo "Recreate the netbox container to pick them up: docker compose up -d netbox"
