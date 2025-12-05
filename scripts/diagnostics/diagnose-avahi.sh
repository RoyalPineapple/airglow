#!/usr/bin/env bash
# Avahi Diagnostic Script
# Checks mDNS/Bonjour service discovery status
# Usage: Source diagnose-common.sh first, then run this script

section "2. Avahi (mDNS/Bonjour Service Discovery)"

# Check if container is running
if docker_cmd ps --format '{{.Names}}' | grep -q '^avahi$'; then
    check_ok "Container is running"
    
    # Check Avahi daemon process
    if docker_cmd exec avahi pgrep -f avahi-daemon > /dev/null 2>&1; then
        check_ok "Avahi daemon process is running"
    else
        check_fail "Avahi daemon process not found"
    fi
    
    # Check D-Bus socket and startup issues
    echo
    echo "  D-Bus and Startup Status:"
    if docker_cmd exec avahi test -S /var/run/dbus/system_bus_socket 2>/dev/null; then
        check_ok "D-Bus socket exists"
    else
        check_warn "D-Bus socket not found"
    fi
    
    # Check for D-Bus binding conflicts in logs
    DBUS_CONFLICTS=$(timeout 5 docker_cmd logs avahi --tail 50 2>&1 | grep -iE 'Failed to bind socket.*system_bus_socket|Address in use' | wc -l | tr -d ' \n' || echo "0")
    if [ "${DBUS_CONFLICTS:-0}" -gt 0 ]; then
        check_fail "D-Bus socket binding conflicts detected (Avahi may be trying to start its own dbus-daemon)"
        timeout 5 docker_cmd logs avahi --tail 20 2>&1 | grep -iE 'Failed to bind socket|Address in use' | tail -2 | while read line; do
            echo "    $line"
        done
    fi
    
    # Check for PID file conflicts
    PID_CONFLICTS=$(timeout 5 docker_cmd logs avahi --tail 50 2>&1 | grep -iE 'PID file.*exists|Failed to create PID file' | wc -l | tr -d ' \n' || echo "0")
    if [ "${PID_CONFLICTS:-0}" -gt 0 ]; then
        check_warn "PID file conflicts detected (stale PID files may prevent startup)"
        timeout 5 docker_cmd logs avahi --tail 20 2>&1 | grep -iE 'PID file|Failed to create PID' | tail -2 | while read line; do
            echo "    $line"
        done
    fi
    
    # Check if Avahi actually started successfully
    AVAHI_STARTED=$(timeout 5 docker_cmd logs avahi --tail 50 2>&1 | grep -iE 'Successfully dropped root privileges|Server startup complete' | wc -l | tr -d ' \n' || echo "0")
    if [ "${AVAHI_STARTED:-0}" -eq 0 ]; then
        check_warn "No successful startup message found in logs"
    fi
    
    # Check host IP detection
    if docker_cmd exec avahi test -f /var/run/avahi-daemon/host-ip.txt 2>/dev/null; then
        HOST_IP=$(timeout 5 docker_cmd exec avahi cat /var/run/avahi-daemon/host-ip.txt 2>/dev/null | tr -d ' \n' || echo "")
        if [ -n "$HOST_IP" ] && [ "$HOST_IP" != "127.0.0.1" ]; then
            check_ok "Host IP detected: $HOST_IP"
        else
            check_warn "Host IP not detected or invalid: ${HOST_IP:-not found}"
        fi
    else
        check_warn "Host IP file not found (Avahi may not have detected host IP)"
    fi
    
    # Check if AirPlay service is advertised
    echo
    echo "  mDNS Services:"
    # Get the AirPlay device name from shairport-sync config
    AIRPLAY_NAME=""
    if docker_cmd exec shairport-sync test -f /etc/shairport-sync.conf 2>/dev/null; then
        # Extract name from config file (format: name = "AirGlow-Staging";)
        AIRPLAY_NAME=$(docker_cmd exec shairport-sync grep -i '^[[:space:]]*name[[:space:]]*=' /etc/shairport-sync.conf 2>/dev/null | sed -n 's/.*name[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' | head -1 | tr -d ' \n' || echo "")
    fi
    
    # If we couldn't get it from config, try from shairport-sync displayConfig
    if [ -z "$AIRPLAY_NAME" ]; then
        AIRPLAY_NAME=$(timeout 5 docker_cmd exec shairport-sync shairport-sync --displayConfig 2>&1 | grep -i 'name =' | sed -n 's/.*name[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' | head -1 | tr -d ' \n' || echo "")
    fi
    
    if [ -z "$AIRPLAY_NAME" ]; then
        check_warn "Could not determine AirPlay device name"
    else
        check_ok "Configured device name: $AIRPLAY_NAME"
    fi
    
    # Check both AirPlay 2 (_raop._tcp) and AirPlay 1 (_airplay._tcp) services
    # Use timeout to prevent hanging - avahi-browse can be slow
    echo
    echo "  Network Advertisement:"
    
    # Check AirPlay 2 (RAOP) services
    RAOP_SERVICES=$(timeout 8 docker_cmd exec avahi avahi-browse -rpt _raop._tcp 2>&1 | grep -v '^=' | wc -l 2>/dev/null | tr -d ' \n' || echo "0")
    RAOP_SERVICES=${RAOP_SERVICES:-0}
    
    # Check AirPlay 1 services
    AIRPLAY1_SERVICES=$(timeout 8 docker_cmd exec avahi avahi-browse -rpt _airplay._tcp 2>&1 | grep -v '^=' | wc -l 2>/dev/null | tr -d ' \n' || echo "0")
    AIRPLAY1_SERVICES=${AIRPLAY1_SERVICES:-0}
    
    TOTAL_SERVICES=$((RAOP_SERVICES + AIRPLAY1_SERVICES))
    
    if [ "${TOTAL_SERVICES}" -gt 0 ] 2>/dev/null; then
        check_ok "Found $TOTAL_SERVICES AirPlay service(s) on network ($RAOP_SERVICES RAOP, $AIRPLAY1_SERVICES AirPlay 1)"
        
        # Check if our specific service is advertised
        if [ -n "$AIRPLAY_NAME" ]; then
            # Sanitize device name for matching (handle special characters like ~, spaces, etc.)
            SANITIZED_NAME=$(echo "$AIRPLAY_NAME" | sed 's/~/\\040/g' | sed 's/ /\\032/g' | sed 's/(/\\040/g' | sed 's/)/\\041/g')
            FOUND_RAOP=false
            FOUND_AIRPLAY1=false
            
            # Check RAOP (AirPlay 2)
            if timeout 8 docker_cmd exec avahi avahi-browse -rpt _raop._tcp 2>&1 | grep -qiE "$(echo "$AIRPLAY_NAME" | sed 's/~/.*/g' | sed 's/[()]/.*/g')"; then
                FOUND_RAOP=true
            fi
            
            # Check AirPlay 1
            if timeout 8 docker_cmd exec avahi avahi-browse -rpt _airplay._tcp 2>&1 | grep -qiE "$(echo "$AIRPLAY_NAME" | sed 's/~/.*/g' | sed 's/[()]/.*/g')"; then
                FOUND_AIRPLAY1=true
            fi
            
            if [ "$FOUND_RAOP" = true ] || [ "$FOUND_AIRPLAY1" = true ]; then
                check_ok "Airglow service '$AIRPLAY_NAME' is being advertised"
                if [ "$FOUND_RAOP" = true ]; then
                    echo "    ✓ Found in _raop._tcp (AirPlay 2)"
                fi
                if [ "$FOUND_AIRPLAY1" = true ]; then
                    echo "    ✓ Found in _airplay._tcp (AirPlay 1)"
                fi
            else
                check_fail "Airglow service '$AIRPLAY_NAME' not found in network advertisements"
                # Show what devices were actually found
                FOUND_DEVICES=$(timeout 8 docker_cmd exec avahi avahi-browse -rpt _raop._tcp 2>&1 | grep -oE 'hostname = \[.*\]' | sed 's/hostname = \[\(.*\)\]/\1/' | sort -u | head -5 | tr '\n' ',' | sed 's/,$//' || echo "None")
                if [ -n "$FOUND_DEVICES" ] && [ "$FOUND_DEVICES" != "None" ]; then
                    echo "    Found devices: $FOUND_DEVICES"
                fi
            fi
        else
            # Fallback to generic search if we can't determine the name
            if timeout 8 docker_cmd exec avahi avahi-browse -rpt _raop._tcp 2>&1 | grep -qi 'airglow'; then
                check_ok "Airglow service is being advertised (name not determined)"
            else
                check_warn "Airglow service not found in mDNS browse (may need to wait for advertisement)"
            fi
        fi
    else
        check_warn "No AirPlay services found on network (or mDNS browse timed out)"
    fi
    
    # Check reflector mode
    if docker_cmd exec avahi grep -q 'enable-reflector=yes' /etc/avahi/avahi-daemon.conf 2>/dev/null; then
        check_ok "Reflector mode enabled"
    else
        check_warn "Reflector mode not enabled (may affect bridge networking)"
    fi
    
    # Check connection to next component (Shairport-Sync via D-Bus)
    echo
    echo "  Component Connections:"
    if docker_cmd ps --format '{{.Names}}' | grep -q '^shairport-sync$'; then
        if docker_cmd exec shairport-sync test -S /var/run/dbus/system_bus_socket 2>/dev/null; then
            # Check if shairport-sync can actually connect to Avahi via D-Bus
            # Use timeout to prevent hanging
            DBUS_CHECK=$(timeout 5 docker_cmd exec shairport-sync dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames 2>&1 | grep -q 'org.freedesktop.Avahi' 2>/dev/null && echo "true" || echo "false")
            if [ "$DBUS_CHECK" = "true" ]; then
                check_ok "Shairport-Sync connected to Avahi (D-Bus connection active)"
            else
                check_fail "D-Bus socket exists but Avahi service not found (Shairport-Sync cannot connect to Avahi)"
                # Show D-Bus error details
                DBUS_ERROR=$(timeout 5 docker_cmd exec shairport-sync dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames 2>&1 | grep -iE 'error|fail' | head -1 || echo "")
                if [ -n "$DBUS_ERROR" ]; then
                    echo "    D-Bus error: $DBUS_ERROR"
                fi
            fi
        else
            check_warn "D-Bus socket not accessible to Shairport-Sync"
        fi
    else
        check_warn "Shairport-Sync container not running (cannot check D-Bus connection)"
    fi
    
else
    check_fail "Container is not running"
fi

