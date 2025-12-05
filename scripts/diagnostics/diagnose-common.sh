#!/usr/bin/env bash
# Common functions for Airglow diagnostic scripts
# This file is sourced by individual component diagnostic scripts

# JSON output mode flag
JSON_OUTPUT="${JSON_OUTPUT:-false}"

# Plain text output functions
check_ok() {
    if [ "$JSON_OUTPUT" = "true" ]; then
        echo "{\"status\":\"ok\",\"message\":\"$1\"}"
    else
    echo "[OK] $1"
    fi
}

check_fail() {
    if [ "$JSON_OUTPUT" = "true" ]; then
        echo "{\"status\":\"error\",\"message\":\"$1\"}"
    else
    echo "[ERROR] $1"
    fi
}

check_warn() {
    if [ "$JSON_OUTPUT" = "true" ]; then
        echo "{\"status\":\"warn\",\"message\":\"$1\"}"
    else
    echo "[WARN] $1"
    fi
}

section() {
    if [ "$JSON_OUTPUT" != "true" ]; then
    echo
    echo "─────────────────────────────────────────────────────────────"
    echo "  $1"
    echo "─────────────────────────────────────────────────────────────"
    fi
}

# Initialize diagnostic environment
# This should be called by the main diagnose-airglow.sh script
# Individual component scripts will inherit these variables
diagnose_init() {
    # Parse arguments
    TARGET_HOST="${1:-}"
    LEDFX_PORT="${LEDFX_PORT:-8888}"

    # If target host specified and it's not "localhost", use SSH; otherwise run locally
    if [ -n "$TARGET_HOST" ] && [ "$TARGET_HOST" != "localhost" ]; then
        SSH_CMD="ssh -o BatchMode=yes -o ConnectTimeout=5 root@${TARGET_HOST}"
        # When checking remote host, API calls are made from local machine
        LEDFX_HOST="${TARGET_HOST}"
        REMOTE=true
    else
        SSH_CMD=""
        # When running locally, API is at localhost
        LEDFX_HOST="${LEDFX_HOST:-localhost}"
        REMOTE=false
    fi

    LEDFX_URL="http://${LEDFX_HOST}:${LEDFX_PORT}"

    # Export for use by component scripts
    export TARGET_HOST LEDFX_PORT SSH_CMD LEDFX_HOST REMOTE LEDFX_URL
}

# Function to run commands (local or remote)
run_cmd() {
    if [ "${REMOTE:-false}" = true ]; then
        $SSH_CMD "$1"
    else
        eval "$1"
    fi
}

# Function to run docker commands
docker_cmd() {
    if [ "${REMOTE:-false}" = true ]; then
        $SSH_CMD "docker $*"
    else
        docker "$@"
    fi
}

