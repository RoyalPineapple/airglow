#!/usr/bin/env bash
# LedFx Pause Script - Pause all effects (equivalent to pause button)
# Usage: ledfx-pause.sh [host] [port]
set -euo pipefail

LEDFX_HOST="${1:-192.168.2.122}"
LEDFX_PORT="${2:-8888}"
BASE_URL="http://${LEDFX_HOST}:${LEDFX_PORT}"

# Set global paused state to true
curl -X PUT -H "Content-Type: application/json" \
  -d '{"paused": true}' \
  -s "${BASE_URL}/api/virtuals" > /dev/null

# Note: This pauses all effects globally but keeps them active
# Effects will resume when paused is set to false

