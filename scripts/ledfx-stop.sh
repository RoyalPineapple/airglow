#!/bin/sh
# LedFx Stop Script - Pause effects and deactivate virtual(s) (preserves effects)
# Usage: ledfx-stop.sh [virtual_ids] [host] [port]
#   virtual_ids: Comma-separated list of virtual IDs (default: from config or all)
set -eu

# Load configuration if available
if [ -f /configs/ledfx-hooks.conf ]; then
  . /configs/ledfx-hooks.conf
fi

VIRTUAL_IDS="${1:-${VIRTUAL_IDS:-}}"
LEDFX_HOST="${2:-${LEDFX_HOST:-localhost}}"
LEDFX_PORT="${3:-${LEDFX_PORT:-8888}}"
BASE_URL="http://${LEDFX_HOST}:${LEDFX_PORT}"

# Function to deactivate a single virtual
deactivate_virtual() {
  local vid="$1"
  curl -X PUT -H "Content-Type: application/json" \
    -d '{"active": false}' \
    -s "${BASE_URL}/api/virtuals/${vid}" > /dev/null
}

# Step 1: Pause all effects (press pause button) - this is global
curl -X PUT -H "Content-Type: application/json" \
  -d '{"paused": true}' \
  -s "${BASE_URL}/api/virtuals" > /dev/null

# If no virtuals specified, get all virtuals from API
if [ -z "$VIRTUAL_IDS" ]; then
  # Get all virtual IDs from API (requires curl and basic parsing)
  VIRTUAL_IDS=$(curl -s "${BASE_URL}/api/virtuals" | \
    grep -o '"[^"]*":\s*{' | \
    grep -v 'status\|virtuals' | \
    sed 's/":.*//' | \
    sed 's/"//g' | \
    tr '\n' ',' | \
    sed 's/,$//')
fi

# Deactivate each virtual
IFS=','
for vid in $VIRTUAL_IDS; do
  # Trim whitespace
  vid=$(echo "$vid" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  if [ -n "$vid" ]; then
    deactivate_virtual "$vid"
  fi
done
unset IFS

# Note: This pauses and deactivates but preserves all effects
# Effects remain configured and will be active when virtual is reactivated

