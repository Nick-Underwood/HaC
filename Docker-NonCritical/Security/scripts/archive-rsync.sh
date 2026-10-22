#!/usr/bin/env bash
#
# wazuh-archive-rsync.sh
# ----------------------
# Copy Wazuh's local archive store to the NFS share for long-term retention.
#
# WHY THIS EXISTS:
#   The original Wazuh manager died on 2026-04-24 because monitord's archive
#   rotation wrote DIRECTLY to a CIFS/NFS mount (/mnt/data/wazuh/archives) that
#   had a momentary I/O error. "Input/output error" on the archive target is
#   fatal to monitord and poisoned the whole manager.
#
#   Fix: Wazuh now writes archives to a LOCAL disk (/srv/wazuh/archives). This
#   script copies them to NFS *out of band* — so a flaky NFS mount can never
#   touch the manager. If NFS is down, we just skip and try again next run.
#
set -u

LOCAL="/srv/wazuh/archives"
NFS="/mnt/data/wazuh/archives"
LOG="/var/log/wazuh-archive-rsync.log"

mkdir -p "$LOCAL" "$(dirname "$LOG")"

# Is the NFS share actually mounted AND writable right now?
nfs_ok=0
if mountpoint -q "$(dirname "$NFS")" 2>/dev/null; then
  if touch "$NFS/.probe" 2>/dev/null; then
    rm -f "$NFS/.probe"
    nfs_ok=1
  fi
fi

if [ "$nfs_ok" -eq 1 ]; then
  if rsync -a --ignore-errors --partial "$LOCAL"/ "$NFS"/ 2>>"$LOG"; then
    echo "$(date -u) OK synced archives -> NFS ($(find "$LOCAL" -type f | wc -l) files local)" >>"$LOG"
  else
    echo "$(date -u) WARN rsync to NFS failed (non-fatal, will retry next run): $?" >>"$LOG"
  fi
else
  echo "$(date -u) SKIP NFS not mounted or not writable; archives retained locally" >>"$LOG"
fi
