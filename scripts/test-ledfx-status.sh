#!/usr/bin/env bash
# Test script to query LedFx status via API
# Based on: https://docs.ledfx.app/en/latest/apis/api.html
set -euo pipefail

LEDFX_HOST="${1:-192.168.2.122}"
LEDFX_PORT="${2:-8888}"

echo "=== LedFx Status ==="
echo "Target: http://${LEDFX_HOST}:${LEDFX_PORT}"
echo

echo "Info:"
curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/info" | jq '.'
echo

echo "Devices:"
curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/devices" | jq '.'
echo

echo "Virtuals (full):"
curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals" | jq '.'
echo

echo "Virtuals (summary - active, streaming, effect):"
curl -s "http://${LEDFX_HOST}:${LEDFX_PORT}/api/virtuals" | jq '.virtuals | to_entries | map({id: .key, active: .value.active, streaming: .value.streaming, effect: (.value.effect.type // "none")})'
echo

