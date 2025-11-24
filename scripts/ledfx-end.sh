#!/usr/bin/env bash
# LedFx End Script - Pause effects and deactivate virtual
# Equivalent to: press pause button + deactivate
# Usage: ledfx-end.sh [virtual_id] [host] [port]
set -euo pipefail

VIRTUAL_ID="${1:-dig-quad}"
LEDFX_HOST="${2:-192.168.2.122}"
LEDFX_PORT="${3:-8888}"
BASE_URL="http://${LEDFX_HOST}:${LEDFX_PORT}"

# Get current state
STATE=$(curl -s "${BASE_URL}/api/virtuals/${VIRTUAL_ID}")
ACTIVE=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].active // false")

# Step 1: Pause all effects (press pause button)
curl -X PUT -H "Content-Type: application/json" \
  -d '{"paused": true}' \
  -s "${BASE_URL}/api/virtuals" > /dev/null

# Step 2: Deactivate virtual
if [ "$ACTIVE" = "true" ]; then
    curl -X PUT -H "Content-Type: application/json" \
      -d '{"active": false}' \
      -s "${BASE_URL}/api/virtuals/${VIRTUAL_ID}" > /dev/null
fi

# Note: streaming is read-only and automatically becomes false when audio input stops
# Pausing stops effect updates, deactivating fully stops the virtual

