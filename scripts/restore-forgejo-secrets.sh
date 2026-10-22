#!/bin/bash
# Restore secrets and variables to Forgejo via API
#
# Usage: ./restore-forgejo-secrets.sh [secrets-values.env]
#
# Prerequisites:
# 1. Create a Forgejo access token at: https://git.u-acres.com/user/settings/applications
# 2. Export it: export FORGEJO_TOKEN="your-token-here"
# 3. Fill in secrets-values.env with actual values

FORGEJO_URL="https://git.u-acres.com"
REPO_OWNER="nicholas"
REPO_NAME="HaC"
VALUES_FILE="${1:-secrets-values.env}"

if [ -z "$FORGEJO_TOKEN" ]; then
  echo "ERROR: FORGEJO_TOKEN environment variable not set"
  echo "Create a token at: $FORGEJO_URL/user/settings/applications"
  echo "Then run: export FORGEJO_TOKEN='your-token-here'"
  exit 1
fi

if [ ! -f "$VALUES_FILE" ]; then
  echo "ERROR: Values file not found: $VALUES_FILE"
  echo "Create it from secrets-values.env.template"
  exit 1
fi

# Source the values file
set -a
source "$VALUES_FILE"
set +a

echo "Restoring secrets and variables to $REPO_OWNER/$REPO_NAME..."
echo ""

# Function to add or update a secret
add_secret() {
  local name="$1"
  local value="$2"

  if [ -z "$value" ]; then
    echo "⚠️  SKIP secret $name (no value provided)"
    return
  fi

  # Forgejo API expects base64-encoded value for some endpoints, but we'll use the simpler approach
  response=$(curl -s -w "\n%{http_code}" -X PUT \
    "$FORGEJO_URL/api/v1/repos/$REPO_OWNER/$REPO_NAME/actions/secrets/$name" \
    -H "Authorization: token $FORGEJO_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"data\":\"$value\"}")

  http_code=$(echo "$response" | tail -n1)

  if [ "$http_code" = "201" ] || [ "$http_code" = "204" ]; then
    echo "✅ Added secret: $name"
  else
    echo "❌ Failed to add secret $name (HTTP $http_code)"
  fi
}

# Function to add or update a variable
add_variable() {
  local name="$1"
  local value="$2"

  if [ -z "$value" ]; then
    echo "⚠️  SKIP variable $name (no value provided)"
    return
  fi

  response=$(curl -s -w "\n%{http_code}" -X PUT \
    "$FORGEJO_URL/api/v1/repos/$REPO_OWNER/$REPO_NAME/actions/variables/$name" \
    -H "Authorization: token $FORGEJO_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"value\":\"$value\"}")

  http_code=$(echo "$response" | tail -n1)

  if [ "$http_code" = "201" ] || [ "$http_code" = "204" ]; then
    echo "✅ Added variable: $name"
  else
    echo "❌ Failed to add variable $name (HTTP $http_code)"
  fi
}

# Read secrets from required-secrets.txt and add them
echo "=== Adding Secrets ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/required-secrets.txt" ]; then
  while IFS= read -r secret_name; do
    [ -z "$secret_name" ] && continue
    # Get value from environment (sourced from VALUES_FILE)
    secret_value=$(eval echo "\$$secret_name")
    add_secret "$secret_name" "$secret_value"
  done < "$SCRIPT_DIR/required-secrets.txt"
else
  echo "⚠️  required-secrets.txt not found. Run scan-workflows.sh first."
fi

echo ""
echo "=== Adding Variables ==="
if [ -f "$SCRIPT_DIR/required-vars.txt" ]; then
  while IFS= read -r var_name; do
    [ -z "$var_name" ] && continue
    # Get value from environment (sourced from VALUES_FILE)
    var_value=$(eval echo "\$$var_name")
    add_variable "$var_name" "$var_value"
  done < "$SCRIPT_DIR/required-vars.txt"
else
  echo "⚠️  required-vars.txt not found. Run scan-workflows.sh first."
fi

echo ""
echo "✅ Done! Check https://git.u-acres.com/nicholas/HaC/settings/secrets"
