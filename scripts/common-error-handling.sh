#!/usr/bin/env bash
# Common Error Handling Functions for Airglow Scripts
# Source this file in scripts to get standardized error handling
#
# Usage:
#   source "$(dirname "$0")/common-error-handling.sh"
#   or
#   source /scripts/common-error-handling.sh

# Error handling configuration
ERROR_LOG_FILE="${ERROR_LOG_FILE:-/var/log/airglow/error.log}"
ENABLE_ERROR_LOGGING="${ENABLE_ERROR_LOGGING:-true}"

# Ensure error log directory exists
mkdir -p "$(dirname "$ERROR_LOG_FILE")" 2>/dev/null || true

# Log error message to file and stderr
log_error() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    if [ "$ENABLE_ERROR_LOGGING" = "true" ]; then
        echo "[$timestamp] ERROR: $message" >> "$ERROR_LOG_FILE" 2>/dev/null || true
    fi
    echo "ERROR: $message" >&2
}

# Log warning message
log_warning() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    if [ "$ENABLE_ERROR_LOGGING" = "true" ]; then
        echo "[$timestamp] WARNING: $message" >> "$ERROR_LOG_FILE" 2>/dev/null || true
    fi
    echo "WARNING: $message" >&2
}

# Log info message
log_info() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    if [ "$ENABLE_ERROR_LOGGING" = "true" ]; then
        echo "[$timestamp] INFO: $message" >> "$ERROR_LOG_FILE" 2>/dev/null || true
    fi
    echo "INFO: $message"
}

# Execute command with error handling and logging
# Usage: safe_exec "description" command [args...]
safe_exec() {
    local description="$1"
    shift
    local cmd="$*"
    
    log_info "Executing: $description"
    if "$@"; then
        log_info "Success: $description"
        return 0
    else
        local exit_code=$?
        log_error "Failed: $description (exit code: $exit_code)"
        return $exit_code
    fi
}

# Execute command with timeout and retry
# Usage: retry_exec max_attempts delay_seconds "description" command [args...]
retry_exec() {
    local max_attempts="$1"
    local delay_seconds="$2"
    local description="$3"
    shift 3
    local cmd="$*"
    
    local attempt=1
    while [ $attempt -le "$max_attempts" ]; do
        log_info "Attempt $attempt/$max_attempts: $description"
        if timeout "${CURL_MAX_TIME:-5}" "$@"; then
            log_info "Success: $description"
            return 0
        else
            local exit_code=$?
            if [ $attempt -lt "$max_attempts" ]; then
                log_warning "Failed attempt $attempt/$max_attempts: $description (exit code: $exit_code), retrying in ${delay_seconds}s..."
                sleep "$delay_seconds"
                attempt=$((attempt + 1))
            else
                log_error "Failed after $max_attempts attempts: $description (exit code: $exit_code)"
                return $exit_code
            fi
        fi
    done
}

# Cleanup function for trap handlers
cleanup_on_error() {
    local exit_code=$?
    local line_number=$1
    log_error "Script failed at line $line_number with exit code $exit_code"
    exit $exit_code
}

# Set up error trap (call this at the start of scripts)
setup_error_trap() {
    trap 'cleanup_on_error $LINENO' ERR
    trap 'cleanup_on_error $LINENO' EXIT
}

