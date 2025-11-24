#!/usr/bin/env bash
# Test script to start LedFx visualization via API
# Handles all possible states: inactive, active (no effect), active (idle), running
# Based on: https://docs.ledfx.app/en/latest/apis/api.html
set -euo pipefail

LEDFX_HOST="${1:-192.168.2.122}"
LEDFX_PORT="${2:-8888}"
VIRTUAL_ID="${3:-dig-quad}"  # Default virtual ID

echo "=== Testing LedFx Start API (All States) ==="
echo "Target: http://${LEDFX_HOST}:${LEDFX_PORT}"
echo "Virtual: ${VIRTUAL_ID}"
echo

# Get current state
echo "1. Get current virtual status:"
STATE=$(curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}")
echo "$STATE" | jq ".[\"${VIRTUAL_ID}\"] | {active, streaming, effect: (.effect.type // \"none\"), last_effect}"
echo

# Extract state components (single virtual endpoint returns {status, virtual_id: {...}})
ACTIVE=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].active")
HAS_EFFECT=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].effect | type != \"object\" or length > 0")
LAST_EFFECT=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].last_effect // \"none\"")

echo "2. Current State Analysis:"
if [ "$ACTIVE" = "false" ]; then
    echo "  → State: INACTIVE"
    echo "  → Action: Will activate virtual"
elif [ "$HAS_EFFECT" = "false" ]; then
    echo "  → State: ACTIVE (No Effect)"
    if [ "$LAST_EFFECT" != "none" ]; then
        echo "  → Action: Will restore last_effect: $LAST_EFFECT"
    else
        echo "  → Action: Virtual active but no effect to restore"
    fi
else
    echo "  → State: ACTIVE (Has Effect) or RUNNING"
    echo "  → Action: Already ready, may just need to ensure active"
fi
echo

# Activate virtual if needed
if [ "$ACTIVE" = "false" ]; then
    echo "3. Activating virtual (PUT /api/virtuals/{virtual_id}):"
    curl -X PUT -H "Content-Type: application/json" \
      -d '{"active": true}' \
      -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}" | jq '.'
    echo
    sleep 1
fi

# Restore effect if needed
if [ "$HAS_EFFECT" = "false" ] && [ "$LAST_EFFECT" != "none" ]; then
    echo "4. Restoring last effect: $LAST_EFFECT"
    echo "   Note: This requires the full effect config. For testing, you may need to"
    echo "   manually set an effect via POST /api/virtuals/${VIRTUAL_ID}/effects"
    echo "   with the effect configuration."
    echo
fi

# Final status
echo "5. Final status:"
sleep 1
curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}" | jq ".virtuals[\"${VIRTUAL_ID}\"] | {active, streaming, effect: (.effect.type // \"none\"), last_effect}"
echo

echo "=== Done ==="
echo "Virtual should now be ACTIVE and ready to receive audio."
echo "When audio starts, streaming will become true automatically."

