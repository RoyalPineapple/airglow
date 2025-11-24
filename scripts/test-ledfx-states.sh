#!/usr/bin/env bash
# Test script to explore all LedFx virtual states
# Based on: https://docs.ledfx.app/en/latest/apis/api.html
set -euo pipefail

LEDFX_HOST="${1:-192.168.2.122}"
LEDFX_PORT="${2:-8888}"
VIRTUAL_ID="${3:-dig-quad}"

echo "=== LedFx Virtual State Explorer ==="
echo "Target: http://${LEDFX_HOST}:${LEDFX_PORT}"
echo "Virtual: ${VIRTUAL_ID}"
echo

# Get full state
echo "Current State:"
STATE=$(curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}")
echo "$STATE" | jq '.'
echo

# Extract state components (single virtual endpoint returns {status, virtual_id: {...}})
ACTIVE=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].active")
STREAMING=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].streaming // false")
HAS_EFFECT=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].effect | type != \"object\" or length > 0")
LAST_EFFECT=$(echo "$STATE" | jq -r ".[\"${VIRTUAL_ID}\"].last_effect // \"none\"")
GLOBAL_PAUSED=$(curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals" | jq -r '.paused // false')

echo "State Components:"
echo "  active: $ACTIVE"
echo "  streaming: $STREAMING"
echo "  has_effect: $HAS_EFFECT"
echo "  last_effect: $LAST_EFFECT"
echo "  global_paused: $GLOBAL_PAUSED"
echo

# Determine current state
echo "Current State Classification:"
if [ "$ACTIVE" = "false" ]; then
    echo "  → INACTIVE (virtual is not active)"
elif [ "$HAS_EFFECT" = "false" ]; then
    echo "  → ACTIVE BUT NO EFFECT (virtual active but no effect loaded)"
elif [ "$STREAMING" = "true" ]; then
    echo "  → RUNNING (active + effect + streaming audio)"
elif [ "$GLOBAL_PAUSED" = "true" ]; then
    echo "  → PAUSED (global pause active)"
else
    echo "  → ACTIVE/IDLE (active + effect but not streaming)"
fi
echo

echo "Possible State Transitions:"
echo "  INACTIVE → ACTIVE: PUT /api/virtuals/{id} with {\"active\": true}"
echo "  ACTIVE → INACTIVE: PUT /api/virtuals/{id} with {\"active\": false}"
echo "  HAS EFFECT → NO EFFECT: DELETE /api/virtuals/{id}/effects"
echo "  NO EFFECT → HAS EFFECT: POST /api/virtuals/{id}/effects with effect config"
echo

