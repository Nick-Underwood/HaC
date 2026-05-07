#!/bin/bash
# Vikunja API helper for Home Assistant command_line sensors
# Usage: vikunja_api.sh <endpoint> <url> <api_token>

set -euo pipefail

ENDPOINT="${1:-}"
VIKUNJA_URL="${2:-}"
API_TOKEN="${3:-}"

if [ -z "$ENDPOINT" ] || [ -z "$VIKUNJA_URL" ] || [ -z "$API_TOKEN" ]; then
  echo '{"error": "missing arguments"}'
  exit 1
fi

AUTH_HEADER="Authorization: Bearer ${API_TOKEN}"
TODAY=$(date -u +%Y-%m-%dT00:00:00Z)
TOMORROW=$(date -u -d "+1 day" +%Y-%m-%dT00:00:00Z 2>/dev/null || date -u -v+1d +%Y-%m-%dT00:00:00Z)

case "$ENDPOINT" in
  today)
    # Tasks due today (filter by due date range)
    curl -sf -X GET "${VIKUNJA_URL}/api/v1/tasks/all?filter=due_date%3E%3D${TODAY}%26%26due_date%3C${TOMORROW}&sort_by=priority&order_by=desc" \
      -H "$AUTH_HEADER" \
      -H "Content-Type: application/json" 2>/dev/null || echo '[]'
    ;;
  overdue)
    # Tasks overdue (due before today, not done)
    curl -sf -X GET "${VIKUNJA_URL}/api/v1/tasks/all?filter=due_date%3C${TODAY}%26%26done%3Dfalse&sort_by=due_date&order_by=asc" \
      -H "$AUTH_HEADER" \
      -H "Content-Type: application/json" 2>/dev/null || echo '[]'
    ;;
  all_pending)
    # All incomplete tasks
    curl -sf -X GET "${VIKUNJA_URL}/api/v1/tasks/all?filter=done%3Dfalse&sort_by=priority&order_by=desc&per_page=50" \
      -H "$AUTH_HEADER" \
      -H "Content-Type: application/json" 2>/dev/null || echo '[]'
    ;;
  completed_today)
    # Tasks completed today
    curl -sf -X GET "${VIKUNJA_URL}/api/v1/tasks/all?filter=done%3Dtrue%26%26done_at%3E%3D${TODAY}&sort_by=done_at&order_by=desc" \
      -H "$AUTH_HEADER" \
      -H "Content-Type: application/json" 2>/dev/null || echo '[]'
    ;;
  *)
    echo '{"error": "unknown endpoint. Use: today, overdue, all_pending, completed_today"}'
    exit 1
    ;;
esac
