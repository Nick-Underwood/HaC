#!/bin/sh
# Actual Budget backup: tar+gzip of /srv/actualbudget data directory.
# Installed as a cron job on <REDACTED_HOST> <REDACTED_HOST>.
# Local-first: writes to local disk, then copies off-host to <REDACTED_HOST>.
# Follows the same pattern as /home/nicholas/hac/scripts/git-backup.sh.
set -eu

DEST=/srv/backups/actualbudget
OFFHOST_DEST=/srv/backups/actualbudget
OFFHOST_USER=nicholas
OFFHOST=<REDACTED_IP>
KEEP_DAYS=14
TS=$(date +%Y%m%d-%H%M%S)

mkdir -p "$DEST"

# --- Local backup -----------------------------------------------------------
BACKUP_FILE="$DEST/actualbudget-$TS.tar.gz"
BACKUP_TMP="$DEST/.actualbudget-$TS.tar.gz.part"

tar czf "$BACKUP_TMP" -C /srv actualbudget

# Guard against truncated/empty backup
if [ "$(stat -c %s "$BACKUP_TMP")" -lt 1000 ]; then
  echo "actualbudget-backup: ERROR archive suspiciously small, discarding" >&2
  rm -f "$BACKUP_TMP"
  exit 1
fi

gzip -t "$BACKUP_TMP"
mv "$BACKUP_TMP" "$BACKUP_FILE"
echo "actualbudget-backup: local backup created: $BACKUP_FILE"

# --- Off-host copy to <REDACTED_HOST> ---------------------------------------------------
cat "$BACKUP_FILE" | ssh -i /home/nicholas/.ssh/id_ed25519_actualbudget_backup \
  ${OFFHOST_USER}@${OFFHOST} "cat > ${OFFHOST_DEST}/actualbudget-$TS.tar.gz"

# Verify off-host copy
if ssh -i /home/nicholas/.ssh/id_ed25519_actualbudget_backup ${OFFHOST_USER}@${OFFHOST} \
    "gzip -t ${OFFHOST_DEST}/actualbudget-$TS.tar.gz"; then
  echo "actualbudget-backup: off-host copy verified on <REDACTED_HOST>"
else
  echo "actualbudget-backup: ERROR off-host copy failed verification" >&2
  exit 1
fi

# --- Retention: remove backups older than KEEP_DAYS --------------------------
find "$DEST" -name "actualbudget-*.tar.gz" -mtime +$KEEP_DAYS -delete
echo "actualbudget-backup: retention cleaned (keeping $KEEP_DAYS days)"
