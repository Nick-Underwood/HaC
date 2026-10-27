#!/bin/sh
# redact-for-mirror.sh — strip internal topology from the HaC public mirror tree.
#
# Purpose
#   The mirror job publishes the repo to a PUBLIC GitHub repository. The
#   workflows legitimately contain internal hostnames, private addresses and
#   personal mail addresses, because they run on the private LAN. Publishing
#   them verbatim hands over a complete map of the internal service topology
#   (the audit counted 67 .forgejo/workflows + scripts/extract-from-hosts.sh
#   fully published, 41 references to <REDACTED_HOST> alone).
#
#   This script rewrites those values to stable placeholders in the *mirror
#   tree only* — the local repo keeps the real values it needs to deploy.
#
# Usage
#   scripts/redact-for-mirror.sh [DIR]       # DIR defaults to "."
#
#   Exit codes: 0 = ok, 2 = usage/environment error.
#
# Placeholders
#   <REDACTED_HOST>   internal DNS names and machine names
#   <REDACTED_IP>     RFC1918 / CGNAT / link-local addresses
#   <REDACTED_EMAIL>  personal mail addresses on internal domains
#
# The rule list below is the single source of truth for the mirror's
# hostname policy; tune it there. Order matters (emails before hostnames,
# hostnames before the bare domain, everything before IPs).
#
# Note: 192.168.X.x (where X is a letter, e.g. <REDACTED_IP>) is a
# comment-level subnet reference that the bare IP regex misses.
# Also catches standalone host-number notation (.50/.51/.52) after a space,
# e.g. "(HAOS <REDACTED_HOST>)" or "(<REDACTED_HOST> <REDACTED_HOST>)" where the opening paren is
# not immediately before the dot. Apply the (.NN) and (space .NN) patterns
# before the bare-IP rules.

set -u

ROOT="${1:-.}"
if [ ! -d "$ROOT" ]; then
  echo "redact-for-mirror: not a directory: $ROOT" >&2
  exit 2
fi

# Ordered redaction rules, compiled into one sed script up front.
SED_SCRIPT="${TMPDIR:-/tmp}/.redact-for-mirror.$$"
{
  cat <<'SEDEOF'
s#[A-Za-z0-9._%+-]+@u-acres\.(com|local)#<REDACTED_EMAIL>#g
s#[A-Za-z0-9._-]+\.u-acres\.local#<REDACTED_HOST>#g
s#[A-Za-z0-9._-]+\.u-acres\.com#<REDACTED_HOST>#g
s#[A-Za-z0-9._-]+\.local#<REDACTED_HOST>#g
s#u-acres\.local#<REDACTED_HOST>#g
s#u-acres\.com#<REDACTED_HOST>#g
s#uacres\.local#<REDACTED_HOST>#g
s#<REDACTED_HOST>#<REDACTED_HOST>#g
s#<REDACTED_HOST>#<REDACTED_HOST>#g
s#<REDACTED_HOST>#<REDACTED_HOST>#g
s#<REDACTED_HOST>#<REDACTED_HOST>#g
s#<REDACTED_HOST>#<REDACTED_HOST>#g
s#192\.168\.[0-9]+\.[xX]#<REDACTED_IP>#g
s#\(\.[0-9]+\)#<REDACTED_HOST>#g
s#([[:space:]])\.5[0-9]#\1<REDACTED_HOST>#g
s#10\.[0-9]+\.[0-9]+\.[0-9]+#<REDACTED_IP>#g
s#172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+#<REDACTED_IP>#g
s#192\.168\.[0-9]+\.[0-9]+#<REDACTED_IP>#g
s#100\.(6[4-9]|[7-9][0-9]|1[0-1][0-9]|12[0-8])\.[0-9]+\.[0-9]+#<REDACTED_IP>#g
s#169\.254\.[0-9]+\.[0-9]+#<REDACTED_IP>#g
SEDEOF
} > "$SED_SCRIPT" || { echo "redact-for-mirror: cannot write $SED_SCRIPT" >&2; exit 2; }

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

redact_file() {
  _f="$1"
  [ -f "$_f" ] || return 0
  is_binary_name "$_f" && return 0
  sed -i -E -f "$SED_SCRIPT" "$_f" 2>/dev/null || true
}
find "$ROOT" -type f -print 2>/dev/null | while IFS= read -r _f; do
  case "$_f" in */.git/*|*/.git|*/node_modules/*|*/.venv/*) continue ;; esac
  [ -f "$_f" ] || continue
  case "$_f" in
    *.png|*.jpg|*.jpeg|*.gif|*.ico|*.svg|*.webp|*.bmp|*.woff|*.woff2|*.ttf|*.otf|*.eot) continue ;;
    *.pdf|*.zip|*.gz|*.tgz|*.bz2|*.xz|*.7z|*.tar|*.pem|*.key|*.crt|*.der|*.p12|*.pfx|*.jks|*.keystore) continue ;;
    *.sqlite|*.sqlite3|*.db|*.pyc|*.pyo|*.so|*.o|*.a|*.exe|*.dll|*.dylib|*.bin) continue ;;
  esac
  sed -i -E -f "$SED_SCRIPT" "$_f" 2>/dev/null || true
done

rm -f "$SED_SCRIPT"
echo "redact-for-mirror: internal hostnames/IPs rewritten under $ROOT"
exit 0
