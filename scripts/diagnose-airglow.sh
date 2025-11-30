#!/usr/bin/env bash
# Airglow Diagnostic Tool
# Checks the entire audio flow: AirPlay → Avahi → Shairport-Sync → NQPTP → PulseAudio → LedFx
# Usage:
#   ./diagnose-airglow.sh                    # Run on localhost
#   ./diagnose-airglow.sh 192.168.2.122      # Run on remote host via SSH
#   ./diagnose-airglow.sh airglow.office.lab # Run on remote host via SSH
#   ./diagnose-airglow.sh --json             # Output JSON format
# Requirements: jq (for JSON parsing)
set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check for jq
if ! command -v jq >/dev/null 2>&1; then
    echo "Error: jq is required but not installed."
    echo "Install with: apt-get install jq (Debian/Ubuntu) or brew install jq (macOS)"
    exit 1
fi

# Parse arguments for JSON flag
JSON_OUTPUT=false
TARGET_HOST=""
for arg in "$@"; do
    if [ "$arg" = "--json" ]; then
        JSON_OUTPUT=true
    elif [ -z "$TARGET_HOST" ] && [ "$arg" != "--json" ]; then
        TARGET_HOST="$arg"
    fi
done

# Export JSON_OUTPUT for use by component scripts
export JSON_OUTPUT

# Source common functions
source "${SCRIPT_DIR}/diagnostics/diagnose-common.sh"

# Initialize diagnostic environment (pass target host if provided)
if [ -n "$TARGET_HOST" ]; then
    diagnose_init "$TARGET_HOST"
else
    diagnose_init
fi

if [ "$JSON_OUTPUT" = "true" ]; then
    # JSON output mode - collect all results
    JSON_RESULTS="[]"
    
    # Run component diagnostic scripts and collect JSON output
    SHAIRPORT_OUTPUT=$(source "${SCRIPT_DIR}/diagnostics/diagnose-shairport.sh" 2>&1 | grep -E '^\{"status"' | jq -s '.')
    AVAHI_OUTPUT=$(source "${SCRIPT_DIR}/diagnostics/diagnose-avahi.sh" 2>&1 | grep -E '^\{"status"' | jq -s '.')
    NQPTP_OUTPUT=$(source "${SCRIPT_DIR}/diagnostics/diagnose-nqptp.sh" 2>&1 | grep -E '^\{"status"' | jq -s '.')
    PULSE_OUTPUT=$(source "${SCRIPT_DIR}/diagnostics/diagnose-pulseaudio.sh" 2>&1 | grep -E '^\{"status"' | jq -s '.')
    LEDFX_OUTPUT=$(source "${SCRIPT_DIR}/diagnostics/diagnose-ledfx.sh" 2>&1 | grep -E '^\{"status"' | jq -s '.')
    
    # Count warnings and errors
    WARNINGS=0
    ERRORS=0
    WARNING_MESSAGES=()
    
    for output in "$SHAIRPORT_OUTPUT" "$AVAHI_OUTPUT" "$NQPTP_OUTPUT" "$PULSE_OUTPUT" "$LEDFX_OUTPUT"; do
        if [ -n "$output" ] && [ "$output" != "null" ]; then
            WARN_COUNT=$(echo "$output" | jq '[.[] | select(.status == "warn")] | length' 2>/dev/null || echo "0")
            ERROR_COUNT=$(echo "$output" | jq '[.[] | select(.status == "error")] | length' 2>/dev/null || echo "0")
            WARNINGS=$((WARNINGS + WARN_COUNT))
            ERRORS=$((ERRORS + ERROR_COUNT))
            
            # Collect warning messages
            WARN_MSGS=$(echo "$output" | jq -r '.[] | select(.status == "warn") | .message' 2>/dev/null || echo "")
            if [ -n "$WARN_MSGS" ]; then
                while IFS= read -r msg; do
                    if [ -n "$msg" ]; then
                        WARNING_MESSAGES+=("$msg")
                    fi
                done <<< "$WARN_MSGS"
            fi
        fi
    done
    
    # Output JSON summary
    jq -n \
        --argjson warnings "$WARNINGS" \
        --argjson errors "$ERRORS" \
        --argjson warning_messages "$(printf '%s\n' "${WARNING_MESSAGES[@]}" | jq -R . | jq -s .)" \
        '{
            "warnings": $warnings,
            "errors": $errors,
            "warning_messages": $warning_messages
        }'
else
    # Plain text output mode
    echo "═══════════════════════════════════════════════════════════════"
    echo "  Airglow Diagnostic Tool"
    echo "  Checking audio flow: AirPlay → Avahi → Shairport-Sync → NQPTP → PulseAudio → LedFx"
    echo "═══════════════════════════════════════════════════════════════"
    echo

    # Run component diagnostic scripts in dependency order
    source "${SCRIPT_DIR}/diagnostics/diagnose-shairport.sh"
    source "${SCRIPT_DIR}/diagnostics/diagnose-avahi.sh"
    source "${SCRIPT_DIR}/diagnostics/diagnose-nqptp.sh"
    source "${SCRIPT_DIR}/diagnostics/diagnose-pulseaudio.sh"
    source "${SCRIPT_DIR}/diagnostics/diagnose-ledfx.sh"

    # ============================================================================
    # SUMMARY
    # ============================================================================
    section "Summary"

    echo "Audio Flow Status:"
    echo "  [AirPlay] → [Avahi/mDNS] → [Shairport-Sync] → [NQPTP] → [PulseAudio] → [LedFx] → [LEDs]"
    echo
    echo "Next steps if issues found:"
    if [ "$REMOTE" = true ]; then
        echo "  1. Check Avahi logs: ssh root@${TARGET_HOST} 'docker logs avahi'"
        echo "  2. Check NQPTP logs: ssh root@${TARGET_HOST} 'docker logs nqptp'"
        echo "  3. Check Shairport-Sync logs: ssh root@${TARGET_HOST} 'docker logs shairport-sync'"
        echo "  4. Check LedFx logs: ssh root@${TARGET_HOST} 'docker logs ledfx'"
        echo "  5. Check hook logs: ssh root@${TARGET_HOST} 'docker exec shairport-sync cat /var/log/shairport-sync/ledfx-session-hook.log'"
    else
        echo "  1. Check Avahi logs: docker logs avahi"
        echo "  2. Check NQPTP logs: docker logs nqptp"
        echo "  3. Check Shairport-Sync logs: docker logs shairport-sync"
        echo "  4. Check LedFx logs: docker logs ledfx"
        echo "  5. Check hook logs: docker exec shairport-sync cat /var/log/shairport-sync/ledfx-session-hook.log"
    fi
    echo "  6. Verify AirPlay connection from your device"
    echo
fi

