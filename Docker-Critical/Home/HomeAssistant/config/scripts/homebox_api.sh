#!/bin/bash
# Homebox API helper for Home Assistant command_line sensors
# Usage: homebox_api.sh <endpoint> <url> <email> <password>
#   endpoint: "statistics" or "maintenance"
#   url: Homebox base URL (e.g. https://homebox.u-acres.com)
#   email: Homebox login email
#   password: Homebox login password

set -euo pipefail

ENDPOINT="${1:-}"
HOMEBOX_URL="${2:-}"
EMAIL="${3:-}"
PASSWORD="${4:-}"

if [ -z "$ENDPOINT" ] || [ -z "$HOMEBOX_URL" ] || [ -z "$EMAIL" ] || [ -z "$PASSWORD" ]; then
  echo '{"error": "missing arguments"}'
  exit 1
fi

# Authenticate and get bearer token
TOKEN_RESPONSE=$(curl -sf -X POST "${HOMEBOX_URL}/api/v1/users/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" 2>/dev/null) || {
  echo '{"error": "auth failed"}'
  exit 1
}

TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null) || {
  echo '{"error": "token parse failed"}'
  exit 1
}

if [ -z "$TOKEN" ]; then
  echo '{"error": "empty token"}'
  exit 1
fi

case "$ENDPOINT" in
  statistics)
    curl -sf -X GET "${HOMEBOX_URL}/api/v1/groups/statistics" \
      -H "Authorization: ${TOKEN}" 2>/dev/null || echo '{"error": "statistics fetch failed"}'
    ;;
  maintenance)
    RESULT=$(curl -sf -X GET "${HOMEBOX_URL}/api/v1/maintenance" \
      -H "Authorization: ${TOKEN}" 2>/dev/null) || { echo '{"error": "maintenance fetch failed"}'; exit 1; }
    echo "{\"entries\": ${RESULT}}"
    ;;
  *)
    echo '{"error": "unknown endpoint"}'
    exit 1
    ;;
esac
