#!/bin/bash
# Scheduled sync runner for NetBox scripts
# Add this to cron or run manually

# Set environment variables (these should be in your .env or set in the container)
export NETBOX_URL="${NETBOX_URL:-http://localhost:8080}"
export NETBOX_TOKEN="${NETBOX_TOKEN}"
export TRUENAS_URL="${TRUENAS_URL:-https://truenas01.example.com}"
export TRUENAS_API_KEY="${TRUENAS_API_KEY}"
export OPNSENSE_URL="${OPNSENSE_URL:-https://opnsense.example.com}"
export OPNSENSE_API_KEY="${OPNSENSE_API_KEY}"
export OPNSENSE_API_SECRET="${OPNSENSE_API_SECRET}"
export OMADA_URL="${OMADA_URL:-https://omada.example.com}"
export OMADA_USERNAME="${OMADA_USERNAME}"
export OMADA_PASSWORD="${OMADA_PASSWORD}"
export OMADA_SITE_NAME="${OMADA_SITE_NAME:-Default}"
export DOCKER_HOST="${DOCKER_HOST:-truenas01}"
export DOCKER_SITE="${DOCKER_SITE:-homelab}"
export VERIFY_SSL="${VERIFY_SSL:-false}"

SCRIPT_DIR="/opt/netbox/netbox/scripts"
LOG_DIR="/opt/netbox/logs"

mkdir -p "$LOG_DIR"

echo "=== NetBox Infrastructure Sync - $(date) ==="

# Run TrueNAS sync
echo "Running TrueNAS sync..."
python3 "$SCRIPT_DIR/sync_truenas.py" 2>&1 | tee -a "$LOG_DIR/sync_truenas.log"

# Run OPNsense sync
echo "Running OPNsense sync..."
python3 "$SCRIPT_DIR/sync_opnsense.py" 2>&1 | tee -a "$LOG_DIR/sync_opnsense.log"

# Run Omada sync
echo "Running Omada sync..."
python3 "$SCRIPT_DIR/sync_omada.py" 2>&1 | tee -a "$LOG_DIR/sync_omada.log"

# Run Docker sync
echo "Running Docker sync..."
python3 "$SCRIPT_DIR/sync_docker.py" 2>&1 | tee -a "$LOG_DIR/sync_docker.log"

echo "=== Sync complete - $(date) ==="
