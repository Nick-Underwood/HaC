#!/bin/bash
# Fetch all containers with ha.monitor=true label from Docker API
# Usage: get-docker-containers.sh <docker-host-url>
# Example: get-docker-containers.sh http://DOCKER_HOST:2375

DOCKER_HOST="${1}"

if [ -z "$DOCKER_HOST" ]; then
  echo "Error: Docker host URL required as first argument" >&2
  echo "Usage: $0 http://DOCKER_HOST:2375" >&2
  exit 1
fi

# Fetch all containers (running and stopped)
containers=$(curl -s "${DOCKER_HOST}/containers/json?all=true" 2>/dev/null)

# Filter for containers with ha.monitor=true label and format as JSON
echo "$containers" | jq '[.[] | select(.Labels["ha.monitor"] == "true") | {
  name: .Names[0] | ltrimstr("/"),
  state: .State,
  status: .Status,
  image: .Image,
  category: .Labels["ha.category"],
  compose_file: .Labels["ha.compose-file"],
  service_name: .Labels["ha.service-name"]
}]'
