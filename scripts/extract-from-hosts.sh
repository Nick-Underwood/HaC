#!/bin/bash
# Extract secrets/variables from running containers on docker hosts
# Run this ON THE DOCKER HOST (not from Windows dev machine)
#
# Usage:
#   ssh docker-critical "bash -s" < extract-from-hosts.sh > critical-values.txt
#   ssh docker-noncritical "bash -s" < extract-from-hosts.sh > noncritical-values.txt

echo "# Extracted from $(hostname) at $(date)"
echo "# Review and copy to secrets-values.env"
echo ""

# Function to safely extract env var from container
extract_env() {
  local container="$1"
  local var="$2"

  if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
    value=$(docker inspect "$container" 2>/dev/null | \
            jq -r ".[0].Config.Env[] | select(startswith(\"$var=\"))" | \
            cut -d= -f2-)

    if [ -n "$value" ]; then
      echo "$var=\"$value\""
    fi
  fi
}

echo "# === Core Infrastructure ==="
extract_env "traefik" "DOMAIN_NAME"
extract_env "traefik" "CERTRESOLVER"
extract_env "traefik" "TZ"
extract_env "traefik" "CLOUDFLARE_DNS_API_TOKEN"
extract_env "traefik" "CLOUDFLARE_ZONE_API_TOKEN"
extract_env "traefik" "CLOUDFLARE_EMAIL"
extract_env "traefik" "LETS_ENCRYPT_EMAIL"

echo ""
echo "# === Forgejo ==="
extract_env "forgejo" "GIT_DB_PASSWORD"
extract_env "git-db" "POSTGRES_USER"
extract_env "git-db" "POSTGRES_DB"
extract_env "git-db" "POSTGRES_PASSWORD"

echo ""
echo "# === Authelia ==="
extract_env "authelia" "AUTHELIA_SESSION_SECRET"
extract_env "authelia" "AUTHELIA_STORAGE_ENCRYPTION_KEY"
extract_env "authelia" "AUTHELIA_JWT_SECRET"
extract_env "authelia" "AUTHELIA_IDENTITY_PROVIDERS_OIDC_HMAC_SECRET"
extract_env "authelia-db" "POSTGRES_PASSWORD"
extract_env "lldap" "LLDAP_JWT_SECRET"
extract_env "lldap" "LLDAP_KEY_SEED"
extract_env "lldap" "LLDAP_LDAP_USER_PASS"
extract_env "lldap" "LDAP_BASE_DN"

echo ""
echo "# === Home Assistant ==="
extract_env "homeassistant" "HA_HOST_IP"
extract_env "homeassistant" "ZIGBEE_COORDINATOR_IP"
extract_env "homeassistant-db" "MYSQL_ROOT_PASSWORD"
extract_env "homeassistant-db" "MYSQL_PASSWORD"

echo ""
echo "# === MQTT ==="
extract_env "mosquitto" "MQTT_USER"
extract_env "mosquitto" "MQTT_PASSWORD"

echo ""
echo "# === Plex ==="
extract_env "plex" "PLEX_CLAIM"

echo ""
echo "# === Immich ==="
extract_env "immich" "DB_USERNAME"
extract_env "immich" "DB_DATABASE_NAME"
extract_env "immich-postgres" "POSTGRES_PASSWORD"

echo ""
echo "# === NetBox ==="
extract_env "netbox" "NETBOX_SECRET_KEY"
extract_env "netbox" "DB_PASSWORD"
extract_env "netbox" "DB_HOST"
extract_env "netbox" "DB_NAME"
extract_env "netbox" "DB_USER"
extract_env "netbox" "REDIS_HOST"

echo ""
echo "# === Vikunja ==="
extract_env "vikunja" "VIKUNJA_SERVICE_JWTSECRET"
extract_env "vikunja-db" "POSTGRES_PASSWORD"

echo ""
echo "# === Vaultwarden ==="
extract_env "vaultwarden" "ADMIN_TOKEN"
extract_env "vaultwarden-db" "POSTGRES_PASSWORD"

echo ""
echo "# === Portainer ==="
extract_env "portainer" "PORTAINER_ADMIN_PASSWORD"

echo ""
echo "# === N8N ==="
extract_env "n8n" "N8N_BASIC_AUTH_USER"
extract_env "n8n" "N8N_BASIC_AUTH_PASSWORD"
extract_env "n8n-db" "POSTGRES_PASSWORD"

echo ""
echo "# === Norish ==="
extract_env "norish" "NEXTAUTH_SECRET"
extract_env "norish" "DATABASE_URL"
extract_env "norish" "MEILI_ADDR"
extract_env "norish-db" "POSTGRES_PASSWORD"
extract_env "norish-meilisearch" "MEILI_MASTER_KEY"

echo ""
echo "# === InfluxDB ==="
extract_env "influxdb" "DOCKER_INFLUXDB_INIT_PASSWORD"

echo ""
echo "# === Omada ==="
extract_env "omada" "MANAGE_HTTP_PORT"
extract_env "omada" "MANAGE_HTTPS_PORT"

echo ""
echo "# === Govee ==="
extract_env "govee-sync" "GOVEE_API_KEY"
extract_env "govee-sync" "GOVEE_EMAIL"
extract_env "govee-sync" "GOVEE_PASSWORD"

echo ""
echo "# Check for .env files in compose directories"
echo "# .env files found:"
find /srv/docker -name ".env" 2>/dev/null | while read envfile; do
  echo "#   $envfile"
  cat "$envfile" | sed 's/^/# /'
done

echo ""
echo "# Done! Review this file and copy values to secrets-values.env"
