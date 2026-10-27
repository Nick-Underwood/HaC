#!/bin/sh
# Generic Docker-secret (_FILE) -> plain env-var promotion for NetBox 6.x.
#
# NetBox 6.x's configuration loader only reads PLAIN env vars (SECRET_KEY,
# DB_PASSWORD, API_TOKEN_PEPPERS, EMAIL_PASSWORD, NETBOX_TOKEN, ...). It has NO
# support for the "_FILE" secret-mount convention, so compose cannot hand it
# secret files directly. This wrapper runs as the container entrypoint, reads
# every "<NAME>_FILE" env var (pointing at a Docker secret mount), exports the
# plain "<NAME>" var with the file's contents, then execs NetBox's real
# entrypoint (via tini, matching the upstream image) forwarding the original
# args ($@) so each service's command (web / rqworker / housekeeping) is kept.
#
# No secret values live in this file or in the compose — only the file paths.
# Committed (no secrets). Bind-mounted into the container from
# /srv/netbox/scripts (the `scripts` volume) at
# /opt/netbox/netbox/scripts/file-secrets-entrypoint.sh.
set -e

for f in $(env | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*_FILE\)=.*/\1/p'); do
  path=$(printenv "$f" 2>/dev/null || true)
  [ -z "$path" ] && continue
  val=$(cat "$path" 2>/dev/null || true)
  name="${f%_FILE}"
  if [ -n "$val" ]; then
    export "$name=$val"
  fi
done

exec /usr/bin/tini -- /opt/netbox/docker-entrypoint.sh "$@"
