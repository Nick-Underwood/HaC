#!/bin/bash
# Helper script to add ha.* labels to compose files
# Usage: add-labels-to-compose.sh <compose-file> <container-name> <service-name> <category>
# Example: add-labels-to-compose.sh Docker-Critical/Home/Test/test.yml my-container test home

set -e

COMPOSE_FILE="$1"
CONTAINER_NAME="$2"
SERVICE_NAME="$3"
CATEGORY="$4"

if [ -z "$COMPOSE_FILE" ] || [ -z "$CONTAINER_NAME" ] || [ -z "$SERVICE_NAME" ] || [ -z "$CATEGORY" ]; then
    echo "Usage: $0 <compose-file> <container-name> <service-name> <category>"
    echo "Example: $0 Docker-Critical/Home/Test/test.yml my-container test home"
    echo ""
    echo "Categories: home, networking, auth, tools, media, management, finance"
    exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: Compose file not found: $COMPOSE_FILE"
    exit 1
fi

echo "Adding ha.* labels to $COMPOSE_FILE"
echo "  Container: $CONTAINER_NAME"
echo "  Service: $SERVICE_NAME"
echo "  Category: $CATEGORY"
echo ""

# Create backup
cp "$COMPOSE_FILE" "${COMPOSE_FILE}.backup"

# Check if container already has ha.monitor label
if grep -q "ha.monitor=true" "$COMPOSE_FILE"; then
    echo "Warning: This file already contains ha.monitor=true labels"
    echo "Please review manually: $COMPOSE_FILE"
    exit 0
fi

# Create labels to add
LABELS=$(cat <<EOF
      - ha.monitor=true
      - ha.category=$CATEGORY
      - ha.compose-file=$COMPOSE_FILE
      - ha.service-name=$SERVICE_NAME
EOF
)

echo "Labels to add:"
echo "$LABELS"
echo ""
echo "Note: This script creates a backup at ${COMPOSE_FILE}.backup"
echo "You'll need to manually insert the labels in the correct location."
echo ""
echo "Add these labels under the 'labels:' section for the service that creates '$CONTAINER_NAME'"
