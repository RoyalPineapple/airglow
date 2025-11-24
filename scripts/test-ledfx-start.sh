#!/usr/bin/env bash
# Test script to start LedFx visualization via API
# Based on: https://docs.ledfx.app/en/latest/apis/api.html
set -euo pipefail

LEDFX_HOST="${1:-192.168.2.122}"
LEDFX_PORT="${2:-8888}"
VIRTUAL_ID="${3:-dig-quad}"  # Default virtual ID

echo "=== Testing LedFx Start API ==="
echo "Target: http://${LEDFX_HOST}:${LEDFX_PORT}"
echo "Virtual: ${VIRTUAL_ID}"
echo

echo "1. Get current virtual status:"
curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}" | jq ".virtuals[\"${VIRTUAL_ID}\"] | {active, streaming, effect: (.effect.type // \"none\")}"
echo

echo "2. Activate virtual (PUT /api/virtuals/{virtual_id}):"
curl -X PUT -H "Content-Type: application/json" \
  -d '{"active": true}' \
  -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}" | jq '.'
echo

echo "3. Check status after activation:"
sleep 1
curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals/${VIRTUAL_ID}" | jq ".virtuals[\"${VIRTUAL_ID}\"] | {active, streaming, effect: (.effect.type // \"none\")}"
echo

echo "=== Done ==="

