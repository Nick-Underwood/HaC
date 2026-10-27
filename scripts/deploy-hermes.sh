#!/bin/bash
## Hermes Docker deploy on <REDACTED_HOST> <REDACTED_HOST>
## Run this on the <REDACTED_HOST> host

set -euo pipefail

sudo mkdir -p /srv/hermes
sudo chown -R 1000:1000 /srv/hermes

REPO_DIR="/opt/hac"
if [ ! -d "$REPO_DIR/.git" ]; then
  echo "ERROR: $REPO_DIR not found or not a git repo" >&2
  exit 1
fi

cd "$REPO_DIR/Docker-NonCritical/Automation/AI/Hermes"

echo "Pulling latest repo..."
git pull origin main

echo "Deploying Hermes (NonCritical)..."
docker compose -p hermes down --remove-orphans || true
docker compose -p hermes -f hermes.yml up -d --force-recreate

echo "Waiting for services to stabilize..."
sleep 20

echo "Verifying dashboard health..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://<REDACTED_HOST>/" || true)
if [ "$STATUS" = "200" ] || [ "$STATUS" = "401" ] || [ "$STATUS" = "302" ]; then
  echo "Dashboard reachable (HTTP $STATUS)"
else
  echo "WARNING: Dashboard HTTP $STATUS — check Traefik routing"
fi

echo "Done. Containers:"
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep hermes
