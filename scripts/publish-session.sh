#!/bin/sh
# Publish locally; a missing worker must never hold up playback.
set -eu
runtime="${AIRGLOW_RUNTIME:-/runtime}"
action="${1:-}"
case "$action" in start|stop) ;; *) exit 0 ;; esac
session=$(cat "$runtime/receiver" 2>/dev/null) || exit 0
temporary=$(mktemp "$runtime/event.XXXXXX") || exit 0
trap 'rm -f "$temporary"' EXIT
printf '{"session":"%s","id":"%s","action":"%s"}\n' "$session" "$(basename "$temporary")" "$action" > "$temporary"
chmod 640 "$temporary"
mv "$temporary" "$runtime/event.json"
