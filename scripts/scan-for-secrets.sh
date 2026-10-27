#!/bin/sh
# scan-for-secrets.sh — content gate for the HaC public mirror.
#
# Purpose
#   The mirror job (.forgejo/workflows/mirror-to-github.yml) strips files by
#   NAME only. That is not enough: a literal secret inside a kept file is
#   published verbatim (this is exactly how the stale Wazuh cluster key
#   escaped). This script scans the *content* of every file in the mirror
#   tree and exits non-zero when it finds a high-confidence secret pattern,
#   so the mirror job aborts before `git commit`.
#
# Usage
#   scripts/scan-for-secrets.sh [DIR]        # DIR defaults to "."
#
#   Exit codes: 0 = clean, 1 = secret pattern found (blocking),
#               2 = usage/environment error.
#
# Design notes
#   - Pure POSIX sh + grep/awk: no python, no network, no third-party deps,
#     so it runs on any runner (SHTF-safe).
#   - If a real `gitleaks` binary is on PATH it is run as well; its findings
#     are blocking too. gitleaks is NOT required.
#   - Env-var indirection (${VAR}, ${{ secrets.X }}, process.env.X, os.getenv)
#     and placeholder/example values never trip the scanner.

set -u

ROOT="${1:-.}"
if [ ! -d "$ROOT" ]; then
  echo "scan-for-secrets: not a directory: $ROOT" >&2
  exit 2
fi

HITS="$(mktemp 2>/dev/null || echo "${TMPDIR:-/tmp}/scan-hits.$$")"
: > "$HITS"
trap 'rm -f "$HITS"' EXIT INT TERM

# --- high-confidence secret shapes (one ERE alternation) ----------------------
# Provider-specific formats first, then a conservative literal-value rule.
# The key/value rule requires a QUOTED value (>=16 chars) so that bare
# variable references (password: DOCKHAND_PASSWORD) are NOT flagged.
SECRET_RE='AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|gh[ousr]_[A-Za-z0-9]{36,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|<key>[A-Za-z0-9]{16,}</key>|(password|passwd|secret|token|api[_-]?key|access[_-]?key|client[_-]?secret|private[_-]?key)[[:space:]]*["'"'"'\x27]?[[:space:]]*[:=][[:space:]]*["'"'"'\x27]?[A-Za-z0-9+/=_-]{16,}'

# Lines that are NOT secrets: env-var indirection, paths, binary markers.
SAFE_RE='\.git/|\.venv|node_modules|\.svg:|\.png:|\.jpg:|\.ico:|\.woff|\.ttf|\.pdf:|\.zip:|\.gz:|\.der:|\.crt:|\.pem:|\.key:|\.p12:|\.sqlite|\.db:|\.pyc:'

# Files whose own content IS the pattern (the scanner and pre-commit hook).
PATTERN_FILE_RE='/(scan-for-secrets\.sh|pre-commit)$'

# Binary extensions are never scanned.
BINARY_RE='\.(png|jpg|jpeg|gif|ico|svg|webp|bmp|woff2?|ttf|otf|eot|pdf|zip|gz|tgz|bz2|xz|7z|tar|pem|key|crt|der|p12|pfx|jks|keystore|sqlite3?|db|pyc|pyo|so|o|a|exe|dll|dylib|bin)$'

is_binary_name() {
  case "$1" in
    *.png|*.jpg|*.jpeg|*.gif|*.ico|*.svg|*.webp|*.bmp) return 0 ;;
    *.woff|*.woff2|*.ttf|*.otf|*.eot) return 0 ;;
    *.pdf|*.zip|*.gz|*.tgz|*.bz2|*.xz|*.7z|*.tar) return 0 ;;
    *.pem|*.key|*.crt|*.der|*.p12|*.pfx|*.jks|*.keystore) return 0 ;;
    *.sqlite|*.sqlite3|*.db|*.pyc|*.pyo|*.so|*.o|*.a) return 0 ;;
    *.exe|*.dll|*.dylib|*.bin) return 0 ;;
  esac
  return 1
}

# --- regex pass: report secret-shaped lines, minus the allowlisted noise -----
scan_regex() {
  _f="$1"
  [ -f "$_f" ] || return 0
  is_binary_name "$_f" && return 0
  printf '%s\n' "$_f" | grep -qE "$PATTERN_FILE_RE" && return 0
  if grep -aIqE "$SECRET_RE" "$_f" 2>/dev/null; then
    grep -anE "$SECRET_RE" "$_f" 2>/dev/null \
      | grep -avE "$SAFE_RE" \
      | grep -avE '\$\{|\\$\(|process\.env|os\.getenv|os\.environ|secrets\.|vars\.' \
      | grep -avE 'example\.com|example\.org|example\.wazuh|example\.internal|changeme|CHANGE_ME|change-me|your[-_]|placeholder|PLACEHOLDER|REDACTED|<[A-Za-z_]+>|xxxx|XXXXXXXX|sha256sum|checksum|sha256:|ITEM_NAME_OR_ID|_PASSWORD|_SECRET|_TOKEN|_KEY|_PASSWORD[_"\x27 ]|_API_KEY' \
      | sed "s|^|$_f:|" >> "$HITS"
  fi
}

# --- entropy pass: long high-entropy tokens (catches base64 secrets) ---------
# Token rules (deliberately strict):
#   * >= 32 chars, split on non-[A-Za-z0-9+] chars (NO / so paths are split)
#   * at least two character classes (upper/lower/digit)
#   * Shannon entropy >= 4.3
scan_entropy() {
  _f="$1"
  [ -f "$_f" ] || return 0
  is_binary_name "$_f" && return 0
  printf '%s\n' "$_f" | grep -qE "$PATTERN_FILE_RE" && return 0
  awk '
  function ent(s,    n,i,x,c,e,p){ n=length(s); if(n<32) return -1; delete c;
    for(i=1;i<=n;i++){ x=substr(s,i,1); c[x]++ }
    e=0; for(x in c){ p=c[x]/n; e-=p*log(p)/log(2) }
    return e }
  {
    if ($0 ~ /\$\{|\\$\(|process\.env|os\.getenv|os\.environ|secrets\.|vars\./) next
    if ($0 ~ /example\.com|example\.org|changeme|CHANGE_ME|REDACTED|sha256|checksum/) next
    n=split($0, w, /[^A-Za-z0-9+]+/)
    for(i=1;i<=n;i++){
      t=w[i]
      if (length(t)<32) continue
      if (index(t,"/")>0) continue
      lo=(t ~ /[a-z]/); up=(t ~ /[A-Z]/); di=(t ~ /[0-9]/)
      if (lo+up+di < 2) continue
      if (substr(t,1,5)=="http:" || substr(t,1,6)=="https:") continue
      if (ent(t) >= 4.3) printf "%s:%d:entropy:%s\n", FILENAME, FNR, t
    }
  }' "$_f" >> "$HITS" 2>/dev/null
}

find "$ROOT" -type f -print 2>/dev/null | while IFS= read -r _f; do
  case "$_f" in */.git/*|*/.git|*/node_modules/*|*/.venv/*) continue ;; esac
  scan_regex "$_f"
  scan_entropy "$_f"
done

# --- optional: real gitleaks when present -----------------------------------
GITLEAKS_NOTE=""
if command -v gitleaks >/dev/null 2>&1; then
  if ! gitleaks detect --source "$ROOT" --no-banner --redact --log-level error >/dev/null 2>&1; then
    GITLEAKS_NOTE="gitleaks reported findings"
    printf '%s\n' "gitleaks: findings in $ROOT" >> "$HITS"
  fi
fi

if [ -s "$HITS" ]; then
  echo "scan-for-secrets: BLOCKED - secret pattern(s) found:" >&2
  sed 's/^/    /' "$HITS" >&2
  echo "" >&2
  echo "Refusing to publish. Remove or env-indirect the value above, then re-run." >&2
  [ -n "$GITLEAKS_NOTE" ] && echo "($GITLEAKS_NOTE)" >&2
  exit 1
fi

echo "scan-for-secrets: clean ($(find "$ROOT" -type f 2>/dev/null | wc -l | tr -d ' ') files scanned)"
exit 0
