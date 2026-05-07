#!/bin/sh
# Wait for the indexer to be ready, then apply the ISM retention policy.
# This runs as a one-shot init container alongside the Wazuh stack.

INDEXER_URL="http://wazuh.indexer:9200"
POLICY_FILE="/ism-policy.json"
MAX_RETRIES=30
RETRY_INTERVAL=10

echo "Waiting for Wazuh indexer to be ready..."

i=0
while [ $i -lt $MAX_RETRIES ]; do
  if curl -s -o /dev/null -w "%{http_code}" "$INDEXER_URL" | grep -q "200"; then
    echo "Indexer is ready."
    break
  fi
  i=$((i + 1))
  echo "Attempt $i/$MAX_RETRIES - indexer not ready, retrying in ${RETRY_INTERVAL}s..."
  sleep $RETRY_INTERVAL
done

if [ $i -eq $MAX_RETRIES ]; then
  echo "ERROR: Indexer did not become ready after $MAX_RETRIES attempts."
  exit 1
fi

# Check if policy already exists
existing=$(curl -s -o /dev/null -w "%{http_code}" "$INDEXER_URL/_plugins/_ism/policies/wazuh-index-retention")

if [ "$existing" = "200" ]; then
  echo "ISM policy already exists, updating..."
  # Get seq_no and primary_term for optimistic concurrency
  seq_info=$(curl -s "$INDEXER_URL/_plugins/_ism/policies/wazuh-index-retention")
  seq_no=$(echo "$seq_info" | grep -o '"_seq_no":[0-9]*' | head -1 | cut -d: -f2)
  primary_term=$(echo "$seq_info" | grep -o '"_primary_term":[0-9]*' | head -1 | cut -d: -f2)

  curl -s -X PUT "$INDEXER_URL/_plugins/_ism/policies/wazuh-index-retention?if_seq_no=${seq_no}&if_primary_term=${primary_term}" \
    -H "Content-Type: application/json" \
    -d @"$POLICY_FILE"
else
  echo "Creating ISM policy..."
  curl -s -X PUT "$INDEXER_URL/_plugins/_ism/policies/wazuh-index-retention" \
    -H "Content-Type: application/json" \
    -d @"$POLICY_FILE"
fi

echo ""
echo "ISM retention policy applied: 30-day index lifecycle."
echo "Compressed archives persist on NFS at /mnt/data/wazuh/archives."
