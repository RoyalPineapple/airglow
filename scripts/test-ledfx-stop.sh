#!/usr/bin/env bash
# Test script to stop LedFx visualization via API
# Handles all possible states: running, active (idle), active (no effect), inactive
# Based on: https://docs.ledfx.app/en/latest/apis/api.html
set -euo pipefail

LEDFX_HOST="${1:-192.168.2.122}"
LEDFX_PORT="${2:-8888}"
VIRTUAL_ID="${3:-dig-quad}"  # Default virtual ID

echo "=== Testing LedFx Stop API (All States) ==="
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
STREAMING=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].streaming // false")
HAS_EFFECT=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].effect | type != \"object\" or length > 0")
LAST_EFFECT=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].last_effect // \"none\"")

echo "2. Current State Analysis:"
if [ "$ACTIVE" = "false" ]; then
    echo "  → State: INACTIVE"
    echo "  → Action: Already stopped, no action needed"
elif [ "$HAS_EFFECT" = "false" ]; then
    echo "  → State: ACTIVE (No Effect)"
    echo "  → Action: Will deactivate virtual"
elif [ "$STREAMING" = "true" ]; then
    echo "  → State: RUNNING"
    echo "  → Action: Will clear effect (preserves last_effect), then deactivate"
else
    echo "  → State: ACTIVE (Idle)"
    echo "  → Action: Will clear effect (preserves last_effect), then deactivate"
fi
echo

# Stop visualization: clear effect first (preserves last_effect)
if [ "$HAS_EFFECT" = "true" ]; then
    echo "3. Clearing active effect (preserves last_effect: $LAST_EFFECT):"
    curl -X DELETE -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}/effects" | jq '.'
    echo
    sleep 1
fi

# Deactivate virtual
if [ "$ACTIVE" = "true" ]; then
    echo "4. Deactivating virtual (PUT /api/virtuals/{virtual_id}):"
    curl -X PUT -H "Content-Type: application/json" \
      -d '{"active": false}' \
      -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}" | jq '.'
    echo
    sleep 1
fi

# Final status
echo "5. Final status:"
FINAL_STATE=$(curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}")
echo "$FINAL_STATE" | jq ".virtuals[\"${VIRTUAL_ID}\"] | {active, streaming, effect: (.effect.type // \"none\"), last_effect}"
echo

FINAL_ACTIVE=$(echo "$FINAL_STATE" | jq -r ".[\"${VIRTUAL_ID}\"].active")
FINAL_LAST_EFFECT=$(echo "$FINAL_STATE" | jq -r ".[\"${VIRTUAL_ID}\"].last_effect // \"none\"")

if [ "$FINAL_ACTIVE" = "false" ]; then
    echo "✓ Virtual is now INACTIVE"
    if [ "$FINAL_LAST_EFFECT" != "none" ]; then
        echo "✓ last_effect preserved: $FINAL_LAST_EFFECT (will be restored on next start)"
    fi
else
    echo "⚠ Warning: Virtual is still active"
fi
echo

echo "=== Done ==="

