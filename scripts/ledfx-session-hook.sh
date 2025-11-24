#!/bin/sh
# Prototype helper invoked from Shairport-Sync session hooks.
# For now it simply logs start/stop events so we can verify hook wiring
# before it begins toggling LedFx state.

set -eu

usage() {
  cat <<'EOF'
Usage: ledfx-session-hook.sh <start|stop> [message]

Prototype helper that records when Shairport-Sync reports a session start
or end. Additional arguments are appended to the log entry for debugging.
EOF
}

timestamp() {
  date +"%Y-%m-%dT%H:%M:%S%z"
}

log_entry() {
  local level="$1"
  shift
  local msg="$*"
  local log_target="${LEDFX_HOOK_LOG:-/tmp/ledfx-session-hook.log}"
  mkdir -p "$(dirname "$log_target")"
  printf "%s [%s] %s\n" "$(timestamp)" "$level" "$msg" >> "$log_target"
}

if [ $# -lt 1 ]; then
  usage >&2
  exit 1
fi

action="$1"
shift || true

case "$action" in
  start)
    if [ $# -gt 0 ]; then
      log_entry "START" "AirPlay session began - $*"
    else
      log_entry "START" "AirPlay session began"
    fi
    ;;
  stop)
    if [ $# -gt 0 ]; then
      log_entry "STOP" "AirPlay session ended - $*"
    else
      log_entry "STOP" "AirPlay session ended"
    fi
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac

