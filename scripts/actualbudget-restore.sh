#!/bin/sh
# Actual Budget restore: extract a backup archive over /srv/actualbudget.
# Usage: actualbudget-restore.sh <backup-file>
# WARNING: This overwrites live data. Verify the backup file first.
set -eu

if [ $# -ne 1 ]; then
  echo "Usage: $0 <backup-file>" >&2
  exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "actualbudget-restore: ERROR file not found: $BACKUP_FILE" >&2
  exit 1
fi

# Verify archive integrity
gzip -t "$BACKUP_FILE"
echo "actualbudget-restore: archive integrity verified"

# Safety: create a pre-restore snapshot
TS=$(date +%Y%m%d-%H%M%S)
PRE_RESTORE="/srv/backups/actualbudget/pre-restore-$TS.tar.gz"
tar czf "$PRE_RESTORE" -C /srv actualbudget
echo "actualbudget-restore: pre-restore snapshot saved: $PRE_RESTORE"

# Stop the container to avoid file conflicts
echo "actualbudget-restore: stopping actualbudget container..."
docker stop actualbudget

# Extract backup over live data
echo "actualbudget-restore: extracting $BACKUP_FILE..."
tar xzf "$BACKUP_FILE" -C /srv

# Restart container
echo "actualbudget-restore: starting actualbudget container..."
docker start actualbudget

echo "actualbudget-restore: DONE. Container restarted with restored data."
echo "actualbudget-restore: verify at https://<REDACTED_HOST>/"
