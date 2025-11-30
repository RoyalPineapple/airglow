# Airglow Diagnostic Scripts

This directory contains modular diagnostic scripts for troubleshooting the Airglow audio flow. The scripts are designed to check each component of the system independently, making it easy to identify and fix issues.

## Overview

The diagnostic system consists of:

- **Main script**: `diagnose-airglow.sh` (in parent directory) - Runs all component checks
- **Common functions**: `diagnose-common.sh` - Shared utilities and initialization
- **Component scripts**: Individual scripts for each service

## Architecture

```
scripts/
├── diagnose-airglow.sh          # Main entry point
└── diagnostics/
    ├── diagnose-common.sh       # Shared functions
    ├── diagnose-shairport.sh    # Shairport-Sync checks
    ├── diagnose-avahi.sh        # Avahi mDNS checks
    ├── diagnose-nqptp.sh        # NQPTP timing checks
    ├── diagnose-pulseaudio.sh   # PulseAudio checks
    └── diagnose-ledfx.sh        # LedFX API checks
```

## Usage

### Running the Full Diagnostic

From the `scripts/` directory:

```bash
# Run on localhost
./diagnose-airglow.sh

# Run on remote host via SSH
./diagnose-airglow.sh 192.168.2.122
./diagnose-airglow.sh airglow.office.lab
```

### Running Individual Component Checks

Each component script can be run standalone. First, source the common functions:

```bash
# From scripts/diagnostics/ directory
source diagnose-common.sh
diagnose_init  # Initialize environment (optional for localhost)

# Then source the component script
source diagnose-shairport.sh
```

Or run from the main scripts directory:

```bash
cd scripts
source diagnostics/diagnose-common.sh
diagnose_init
source diagnostics/diagnose-shairport.sh
```

## Component Scripts

### `diagnose-shairport.sh`

Checks the Shairport-Sync AirPlay receiver:

- Container running status
- Shairport-Sync process status
- Configuration file presence
- AirPlay device name
- Session hooks configuration
- Recent AirPlay activity

**Dependencies**: None (first in dependency chain)

### `diagnose-avahi.sh`

Checks the Avahi mDNS/Bonjour service:

- Container running status
- Avahi daemon process
- D-Bus socket availability
- mDNS service advertisement
- AirPlay service discovery
- Reflector mode configuration

**Dependencies**: None (runs on host networking)

### `diagnose-nqptp.sh`

Checks the NQPTP AirPlay 2 timing service:

- Container running status
- NQPTP process status
- Version information
- Port bindings (319, 320/UDP)
- Shared memory access

**Dependencies**: None (runs on host networking)

### `diagnose-pulseaudio.sh`

Checks the PulseAudio audio bridge:

- LedFX container status (hosts PulseAudio)
- PulseAudio server status
- Active audio streams
- Shairport-Sync connection
- Audio sinks

**Dependencies**: Requires LedFX container

### `diagnose-ledfx.sh`

Checks the LedFX visualization engine:

- Container running status
- API accessibility
- Version information
- Global paused state
- Virtual configurations
- Device status
- Effect status

**Dependencies**: Requires LedFX API to be accessible

**Requirements**: `jq` for JSON parsing

## Common Functions

### `diagnose-common.sh`

Provides shared functionality:

- **`check_ok(message)`** - Output success message
- **`check_fail(message)`** - Output error message
- **`check_warn(message)`** - Output warning message
- **`section(title)`** - Print section header
- **`diagnose_init([host])`** - Initialize diagnostic environment
- **`run_cmd(command)`** - Execute command (local or remote)
- **`docker_cmd(command)`** - Execute docker command (local or remote)

### Environment Variables

After calling `diagnose_init()`, the following variables are available:

- `TARGET_HOST` - Target hostname or IP (if remote)
- `LEDFX_PORT` - LedFX API port (default: 8888)
- `SSH_CMD` - SSH command string (if remote)
- `LEDFX_HOST` - LedFX hostname for API calls
- `REMOTE` - Boolean indicating if running remotely
- `LEDFX_URL` - Full LedFX API URL

## Requirements

### System Requirements

- **Bash** 4.0 or later
- **Docker** - For container checks
- **jq** - For JSON parsing (required for LedFX checks)
- **SSH** - For remote diagnostics (optional)
- **curl** - For API checks (usually pre-installed)

### Installing jq

```bash
# Debian/Ubuntu
apt-get install jq

# macOS
brew install jq

# RHEL/CentOS
yum install jq
```

## Output Format

The scripts use a consistent output format:

```
[OK]     - Success/healthy status
[WARN]   - Warning/non-critical issue
[ERROR]  - Error/critical issue
```

Example output:

```
─────────────────────────────────────────────────────────────
  1. Shairport-Sync (AirPlay Receiver)
─────────────────────────────────────────────────────────────
[OK] Container is running
[OK] Shairport-Sync process is running
[OK] Configuration file exists
[OK] Device name: Airglow
[OK] Session hook configured: /scripts/ledfx/ledfx-session-hook.sh
```

## Troubleshooting

### Script Fails with "jq not found"

Install jq using your package manager (see Requirements section).

### Remote SSH Connection Fails

- Ensure SSH key-based authentication is configured
- Check that the target host is reachable
- Verify SSH access: `ssh root@<host>`

### Container Checks Fail

- Ensure Docker is running: `docker ps`
- Check container names match expected values
- Verify you have permission to run docker commands

### API Checks Fail

- Verify LedFX is accessible: `curl http://localhost:8888/api/info`
- Check firewall rules if running remotely
- Ensure LedFX container is running: `docker ps | grep ledfx`

## Integration

### Web Interface

The diagnostic scripts are integrated into the Airglow web interface. Users can run diagnostics from the status page, which executes `diagnose-airglow.sh` inside the `airglow-web` container.

### CI/CD

These scripts can be used in automated testing:

```bash
#!/bin/bash
# Example CI check
if ./scripts/diagnose-airglow.sh staging.example.com; then
    echo "All checks passed"
    exit 0
else
    echo "Diagnostics found issues"
    exit 1
fi
```

## Extending

To add a new component check:

1. Create `diagnose-<component>.sh` in this directory
2. Source `diagnose-common.sh` at the top
3. Use the common functions (`check_ok`, `check_fail`, `check_warn`, `section`)
4. Add the script to `diagnose-airglow.sh` in dependency order

Example:

```bash
#!/usr/bin/env bash
# New Component Diagnostic Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/diagnose-common.sh"

section "X. New Component"

if docker_cmd ps --format '{{.Names}}' | grep -q '^new-component$'; then
    check_ok "Container is running"
else
    check_fail "Container is not running"
fi
```

## Audio Flow

The diagnostic scripts check components in this order (dependency chain):

```
[AirPlay Device]
    ↓
[Avahi] (mDNS discovery)
    ↓
[Shairport-Sync] (AirPlay receiver)
    ↓
[NQPTP] (timing synchronization)
    ↓
[PulseAudio] (audio bridge)
    ↓
[LedFX] (visualization)
    ↓
[LED Devices]
```

## See Also

- [LedFX Scripts README](../ledfx/README.md) - Hook and control scripts
- [Main Scripts README](../README.md) - Overview of all scripts
- [Configuration Guide](../../CONFIGURATION.md) - System configuration

