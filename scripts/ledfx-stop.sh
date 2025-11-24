#!/usr/bin/env bash
# LedFx Stop Script - Stop all effects and deactivate (equivalent to stop button)
# Usage: ledfx-stop.sh [virtual_id] [host] [port]
set -euo pipefail

VIRTUAL_ID="${1:-dig-quad}"
LEDFX_HOST="${2:-192.168.2.122}"
LEDFX_PORT="${3:-8888}"
BASE_URL="http://${LEDFX_HOST}:${LEDFX_PORT}"

# Get current state
STATE=$(curl -s "${BASE_URL}/api/virtuals/${VIRTUAL_ID}")
ACTIVE=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].active // false")
HAS_EFFECT=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].effect | type != \"object\" or length > 0")

# Step 1: Clear effect to stop visualization
if [ "$HAS_EFFECT" = "true" ]; then
    curl -X DELETE -s "${BASE_URL}/api/virtuals/${VIRTUAL_ID}/effects" > /dev/null
fi

# Step 2: Deactivate virtual
if [ "$ACTIVE" = "true" ]; then
    curl -X PUT -H "Content-Type: application/json" \
      -d '{"active": false}' \
      -s "${BASE_URL}/api/virtuals/${VIRTUAL_ID}" > /dev/null
fi

# Note: This fully stops the virtual (equivalent to stop button)
# Use pause/play for temporary pause/resume

