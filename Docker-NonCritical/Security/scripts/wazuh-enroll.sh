#!/usr/bin/env bash
# wazuh-enroll.sh - generate a Wazuh agent key + print install steps for a host.
# Runs ON the runner (has docker + access to the manager container). Local-first, no cloud.
# Usage: ./wazuh-enroll.sh <agent_name> <agent_ip> [enroll_password]
#
# The agent key is produced out-of-band via manage_agents (docker exec into the
# manager), so this script never needs the manager API password. The optional
# enroll_password is only echoed into the agent install commands (used by the
# manager's authd at 1515 if <use_password>yes</use_password> is set in ossec.conf).
set -euo pipefail

NAME="${1:?agent name required (e.g. omv-01)}"
IP="${2:?agent IP required (e.g. <REDACTED_IP>)}"
ENROLL_PASSWORD="${3:-${WAZUH_ENROLL_PASSWORD:-}}"
MANAGER_CONTAINER="wazuh-manager"
MANAGER_IP="<REDACTED_IP>"
ENROLL_PORT="1514"

echo "=== generating key for $NAME ($IP) ==="

# Idempotent: don't re-add an agent that already exists (manage_agents -a errors on dup)
if docker exec "$MANAGER_CONTAINER" /var/ossec/bin/manage_agents -l 2>/dev/null | grep -qw "$NAME"; then
  echo "(agent '$NAME' already registered — reusing existing key)"
else
  if ! docker exec "$MANAGER_CONTAINER" /var/ossec/bin/manage_agents -a "$IP" -n "$NAME" >/dev/null 2>&1; then
    echo "FAILED to add agent. Re-run manually:" >&2
    docker exec -it "$MANAGER_CONTAINER" /var/ossec/bin/manage_agents
    exit 1
  fi
fi

# Extract the key non-interactively. manage_agents -e prints lines like:
#   Agent key information for 'NAME':
#   ID:001
#   Name:NAME
#   IP Address:1.2.3.4
#   Key:MDEwMD...
KEY=$(docker exec "$MANAGER_CONTAINER" /var/ossec/bin/manage_agents -e "$NAME" 2>/dev/null \
        | awk -F': ' '/^Key:/{print $2; exit}')

if [ -z "$KEY" ]; then
  echo "FAILED to extract key (manage_agents -e produced no Key: line). Re-run manually:" >&2
  docker exec -it "$MANAGER_CONTAINER" /var/ossec/bin/manage_agents
  exit 1
fi

echo "KEY: $KEY"
PW_ARG=""
[ -n "$ENROLL_PASSWORD" ] && PW_ARG=" WAZUH_REGISTRATION_PASSWORD='$ENROLL_PASSWORD'"

echo
echo "=== LINUX agent (run ON the target host, Debian/Ubuntu/RHEL) ==="
cat <<EOF
  curl -sO https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.14.3-1_amd64.deb
  sudo WAZUH_MANAGER='$MANAGER_IP'$PW_ARG WAZUH_AGENT_NAME='$NAME' dpkg -i ./wazuh-agent_4.14.3-1_amd64.deb
  # Inject the pre-generated key directly (bypasses authd enrollment):
  sudo /var/ossec/bin/manage_agents -i '$KEY'
  sudo systemctl daemon-reload && sudo systemctl enable --now wazuh-agent
EOF
echo
echo "=== WINDOWS agent (run in admin PowerShell ON the target host) ==="
cat <<EOF
  Invoke-WebRequest -Uri https://packages.wazuh.com/4.x/windows/wazuh-agent-4.14.3-1.msi -OutFile wazuh-agent.msi
  msiexec.exe /q /i wazuh-agent.msi NAMESERVER='$MANAGER_IP' SERVERPORT='$ENROLL_PORT' CONFIG_PROTOCOL='tcp' AUTHD_SERVER='$MANAGER_IP' AGENT_NAME='$NAME' REGISTRATION_PASSWORD='$ENROLL_PASSWORD'
  & "C:\\Program Files (x86)\\ossec-agent\\manage_agents.exe" -i '$KEY'
  & "C:\\Program Files (x86)\\ossec-agent\\win32ui.exe"   # or: net start wazuh-agent
EOF
echo
echo "=== VERIFY (from runner) ==="
echo "  docker exec $MANAGER_CONTAINER /var/ossec/bin/agent_control -l"
