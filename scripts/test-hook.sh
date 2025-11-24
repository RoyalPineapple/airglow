#!/bin/sh
# Minimal test hook - just log that we were called
mkdir -p /var/log/shairport-sync
echo "$(date -Iseconds) HOOK CALLED: $*" >> /var/log/shairport-sync/test-hook.log

