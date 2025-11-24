#!/usr/bin/env bash
# LedFx Begin Script - Activate virtual and ensure not paused
# Equivalent to: activate virtual + press play button
# Usage: ledfx-begin.sh [virtual_id] [host] [port]
set -euo pipefail

VIRTUAL_ID="${1:-dig-quad}"
LEDFX_HOST="${2:-192.168.2.122}"
LEDFX_PORT="${3:-8888}"
BASE_URL="http://${LEDFX_HOST}:${LEDFX_PORT}"

# Get current state
STATE=$(curl -s "${BASE_URL}/api/virtuals/${VIRTUAL_ID}")
ACTIVE=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].active // false")

# Step 1: Activate if not active
if [ "$ACTIVE" != "true" ]; then
    curl -X PUT -H "Content-Type: application/json" \
      -d '{"active": true}' \
      -s "${BASE_URL}/api/virtuals/${VIRTUAL_ID}" > /dev/null
fi

# Step 2: Ensure not paused (press play)
curl -X PUT -H "Content-Type: application/json" \
  -d '{"paused": false}' \
  -s "${BASE_URL}/api/virtuals" > /dev/null

# Note: streaming is read-only and automatically becomes true when audio input starts
# We ensure active=true and paused=false, then streaming will follow when audio arrives

