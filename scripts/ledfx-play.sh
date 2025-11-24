#!/usr/bin/env bash
# LedFx Play Script - Resume all effects (equivalent to play button)
# Usage: ledfx-play.sh [host] [port]
set -euo pipefail

LEDFX_HOST="${1:-192.168.2.122}"
LEDFX_PORT="${2:-8888}"
BASE_URL="http://${LEDFX_HOST}:${LEDFX_PORT}"

# Set global paused state to false (resume)
curl -X PUT -H "Content-Type: application/json" \
  -d '{"paused": false}' \
  -s "${BASE_URL}/api/virtuals" > /dev/null

# Note: This resumes all paused effects
# Effects must be active for this to have an effect

