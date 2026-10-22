#!/bin/bash
# Scheduled sync runner for NetBox scripts
# Add this to cron or run manually.
#
# Credentials are supplied via Docker-secret *_FILE mounts (see netbox.yml) and
# promoted to env by the container entrypoint wrapper — they are NOT set here.
# NETBOX_TOKEN / OPNSENSE_* / OMADA_* / TRUENAS_API_KEY are read from
# <NAME>_FILE mounts by nb_rest.secret_env() (falling back to plain env for local runs).
#
# NOTE: sync_docker.py runs ON THE HOST (needs /var/run/docker.sock), not in the
# container — it has its own crontab line (see deploy docs / setup notes).

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

# Run Dockhand sync (fleet-wide container inventory via Dockhand API)
echo "Running Dockhand sync..."
python3 "$SCRIPT_DIR/sync_dockhand.py" 2>&1 | tee -a "$LOG_DIR/sync_dockhand.log"

echo "=== Sync complete - $(date) ==="
