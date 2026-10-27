#!/bin/sh
# Forgejo backup: Postgres logical dump + git/registry data tree.
# Installed as a root cron job on <REDACTED_HOST> <REDACTED_HOST>.
# Local-first: writes to local disk only, no cloud dependency.
# SHTF-critical: /srv/git holds ALL repos + container registry blobs (~27GB).
set -eu

DEST=/srv/backups/git
KEEP_DAYS=14
TS=$(date +%Y%m%d-%H%M%S)

mkdir -p "$DEST"

# --- Postgres (Forgejo metadata: users, repos, actions, package index) ------
# pg_dump inside the git-db container; --clean restores over an existing DB.
DB_TMP="$DEST/.git-db-$TS.sql.gz.part"
DB_OUT="$DEST/git-db-$TS.sql.gz"
if docker exec git-db pg_dump -U git -d git --clean --if-exists \
     | gzip -9 > "$DB_TMP"; then
  # Guard against a truncated/empty dump becoming the "latest good" backup.
  if [ "$(stat -c %s "$DB_TMP")" -lt 10000 ]; then
    echo "git-backup: ERROR dump suspiciously small, discarding" >&2
    rm -f "$DB_TMP"
    exit 1
  fi
  gzip -t "$DB_TMP"                     # verify archive integrity
  mv "$DB_TMP" "$DB_OUT"
else
  echo "git-backup: ERROR pg_dump failed" >&2
  rm -f "$DB_TMP"
  exit 1
fi

# --- Data tree (git repos + container registry blobs live on disk) ----------
# Excludes postgres dir (already dumped above) and tmp caches.
DATA_TMP="$DEST/.git-data-$TS.tar.gz.part"
DATA_OUT="$DEST/git-data-$TS.tar.gz"
if tar -czf "$DATA_TMP" \
    --exclude='postgres' \
    --exclude='postgres.backup' \
    --exclude='tmp' \
    -C /srv/git data 2>/dev/null; then
  gzip -t "$DATA_TMP"
  mv "$DATA_TMP" "$DATA_OUT"
else
  echo "git-backup: WARN data archive failed" >&2
  rm -f "$DATA_TMP"
fi

# --- Retention --------------------------------------------------------------
find "$DEST" -name 'git-db-*.sql.gz'   -mtime +$KEEP_DAYS -delete
find "$DEST" -name 'git-data-*.tar.gz' -mtime +$KEEP_DAYS -delete
find "$DEST" -name '.*.part'           -mtime +1          -delete

echo "git-backup: OK db=$(du -h "$DB_OUT" | cut -f1) data=$(du -h "$DATA_OUT" 2>/dev/null | cut -f1) dest=$DEST"
