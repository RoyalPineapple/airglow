#!/bin/sh
# LedFx Stop Script - Deactivate virtual(s) (preserves effects, never pauses)
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

# Function to deactivate a single virtual (toggle pattern for reliability, especially Govee)
deactivate_virtual() {
  local vid="$1"
  # Send deactivate command
  curl -X PUT -H "Content-Type: application/json" \
    -d '{"active": false}' \
    -s "${BASE_URL}/api/virtuals/${vid}" > /dev/null
  # Wait 0.25 seconds
  sleep 0.25
  # Send activate command (toggle to ensure state is processed)
  curl -X PUT -H "Content-Type: application/json" \
    -d '{"active": true}' \
    -s "${BASE_URL}/api/virtuals/${vid}" > /dev/null
  # Wait 0.25 seconds
  sleep 0.25
  # Send deactivate command again (final state)
  curl -X PUT -H "Content-Type: application/json" \
    -d '{"active": false}' \
    -s "${BASE_URL}/api/virtuals/${vid}" > /dev/null
}

# If no virtuals specified, get all virtuals from API
if [ -z "$VIRTUAL_IDS" ]; then
  # Get all virtual IDs from API using jq
  VIRTUAL_IDS=$(curl -s "${BASE_URL}/api/virtuals" | \
    jq -r '.virtuals | keys[]' 2>/dev/null | \
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

# Note: This deactivates virtuals but preserves all effects
# Effects remain configured and will be active when virtual is reactivated
# We never set paused=true - only set paused=false when starting

