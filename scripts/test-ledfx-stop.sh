#!/usr/bin/env bash
# Test script to stop LedFx visualization via API
# Based on: https://docs.ledfx.app/en/latest/apis/api.html
set -euo pipefail

LEDFX_HOST="${1:-192.168.2.122}"
LEDFX_PORT="${2:-8888}"
VIRTUAL_ID="${3:-dig-quad}"  # Default virtual ID

echo "=== Testing LedFx Stop API ==="
echo "Target: http://${LEDFX_HOST}:${LEDFX_PORT}"
echo "Virtual: ${VIRTUAL_ID}"
echo

echo "1. Get current virtual status:"
curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}" | jq ".virtuals[\"${VIRTUAL_ID}\"] | {active, streaming, effect: (.effect.type // \"none\")}"
echo

echo "2. Clear effect (DELETE /api/virtuals/{virtual_id}/effects):"
curl -X DELETE -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}/effects" | jq '.'
echo

echo "3. Check status after clearing effect:"
sleep 1
curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}" | jq ".virtuals[\"${VIRTUAL_ID}\"] | {active, streaming, effect: (.effect.type // \"none\")}"
echo

echo "=== Alternative: Deactivate virtual ==="
echo "4. Deactivate virtual (PUT /api/virtuals/{virtual_id}):"
curl -X PUT -H "Content-Type: application/json" \
  -d '{"active": false}' \
  -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}" | jq '.'
echo

echo "5. Final status:"
sleep 1
curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}" | jq ".virtuals[\"${VIRTUAL_ID}\"] | {active, streaming, effect: (.effect.type // \"none\")}"
echo

echo "=== Done ==="

