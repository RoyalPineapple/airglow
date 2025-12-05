# Airglow Troubleshooting Guide

This guide covers common issues and their solutions when using Airglow.

## Table of Contents

- [Container Issues](#container-issues)
- [AirPlay Issues](#airplay-issues)
- [LedFX Issues](#ledfx-issues)
- [Network Issues](#network-issues)
- [Configuration Issues](#configuration-issues)
- [Performance Issues](#performance-issues)

---

## Container Issues

### Container Won't Start

**Symptoms:**
- Container exits immediately after starting
- `docker ps` shows container as "Exited"
- Error messages in `docker logs`

**Solutions:**

1. **Check container logs:**
   ```bash
   docker logs <container-name>
   ```

2. **Check Docker daemon:**
   ```bash
   docker info
   ```

3. **Verify network configuration:**
   - For `shairport-sync`: Ensure macvlan network exists and interface is correct
   - For bridge networking: Ensure `airglow-network` exists
   - Check IP conflicts: `docker network inspect shairport-macvlan`

4. **Check resource limits:**
   ```bash
   docker stats
   ```

5. **Verify volume mounts:**
   - Check that config files exist: `ls -la /opt/airglow/configs/`
   - Verify permissions: `ls -la /opt/airglow/pulse/`

### Container Health Check Failing

**Symptoms:**
- Container shows as "unhealthy" in `docker ps`
- Health check endpoint returns errors

**Solutions:**

1. **Check health check endpoint manually:**
   ```bash
   # For ledfx
   docker exec ledfx curl -f http://127.0.0.1:8888/api/info
   
   # For airglow-web
   docker exec airglow-web curl -f http://localhost/api/status
   
   # For shairport-sync
   docker exec shairport-sync pgrep -f shairport-sync
   ```

2. **Increase health check interval** (if service is slow to start):
   - Edit `docker-compose.yml` healthcheck `interval` value

3. **Check service logs for startup errors:**
   ```bash
   docker logs <container-name> --tail 50
   ```

---

## AirPlay Issues

### AirPlay Device Not Appearing

**Symptoms:**
- Device doesn't show up in iOS/macOS AirPlay menu
- iTunes can't find the device
- Status page shows "Advertising on Network: No"

**Solutions:**

1. **Check shairport-sync is running:**
   ```bash
   docker ps | grep shairport-sync
   docker logs shairport-sync --tail 50
   ```

2. **Verify mDNS advertisement:**
   ```bash
   docker exec shairport-sync avahi-browse -rpt _raop._tcp
   docker exec shairport-sync avahi-browse -rpt _airplay._tcp
   ```

3. **Check D-Bus connection:**
   ```bash
   docker exec shairport-sync dbus-send --system --print-reply \
     --dest=org.freedesktop.DBus /org/freedesktop/DBus \
     org.freedesktop.DBus.ListNames | grep Avahi
   ```

4. **Verify network configuration:**
   - Check macvlan IP is correct: `docker network inspect shairport-macvlan`
   - Verify IP is on correct subnet: `ip addr show`
   - Check for IP conflicts: `ping 192.168.2.202` (or your configured IP)

5. **Check device name configuration:**
   ```bash
   docker exec shairport-sync shairport-sync --displayConfig | grep name
   ```

6. **Restart shairport-sync:**
   ```bash
   docker restart shairport-sync
   ```

### AirPlay Connection Fails

**Symptoms:**
- Device appears in AirPlay menu but connection fails
- "Unable to connect" error on client device
- Status page shows device advertising but connection fails

**Solutions:**

1. **Check port accessibility:**
   ```bash
   # From client device, test connectivity
   telnet <shairport-ip> 7000  # RTSP control
   telnet <shairport-ip> 5000  # RAOP audio
   ```

2. **Verify firewall rules:**
   - Ensure ports 7000, 5000, 319, 320 are not blocked
   - Check iptables/ufw rules

3. **Check network interface:**
   - Verify macvlan parent interface is correct: `docker network inspect shairport-macvlan`
   - Ensure interface is up: `ip link show eth0` (or your interface)

4. **Check shairport-sync logs for connection errors:**
   ```bash
   docker logs shairport-sync | grep -i "error\|fail\|connection"
   ```

5. **Verify AirPlay version:**
   ```bash
   docker logs shairport-sync | grep -i "AirPlay.*mode"
   # Should show "AirPlay 2 mode" for AirPlay 2 support
   ```

### AirPlay Audio Stops or Cuts Out

**Symptoms:**
- Audio plays briefly then stops
- Audio cuts in and out
- Status shows connection but no audio

**Solutions:**

1. **Check PulseAudio connection:**
   ```bash
   docker exec ledfx pactl list sink-inputs
   docker exec shairport-sync test -S /pulse/pulseaudio.socket
   ```

2. **Verify shared memory for NQPTP:**
   ```bash
   docker exec shairport-sync ls -la /dev/shm
   # Should show nqptp or shairport files
   ```

3. **Check network latency:**
   ```bash
   ping <shairport-ip>
   # Should have low latency (<10ms on local network)
   ```

4. **Restart audio pipeline:**
   ```bash
   docker restart shairport-sync
   docker restart ledfx
   ```

---

## LedFX Issues

### LedFX Not Receiving Audio

**Symptoms:**
- Status page shows "LedFX Processing: Inactive"
- No visualizations appear
- Audio streams count is 0

**Solutions:**

1. **Check PulseAudio:**
   ```bash
   docker exec ledfx pactl info
   docker exec ledfx pactl list sink-inputs
   ```

2. **Verify audio device configuration:**
   ```bash
   curl http://localhost:8888/api/audio/devices
   # Check that "pulse" is configured as active device
   ```

3. **Check PulseAudio socket:**
   ```bash
   ls -la /opt/airglow/pulse/
   # Should show pulseaudio.socket and cookie
   ```

4. **Restart LedFX:**
   ```bash
   docker restart ledfx
   ```

### LedFX Virtuals Not Activating

**Symptoms:**
- Hooks configured but virtuals don't activate on AirPlay start
- Status page shows virtuals as inactive

**Solutions:**

1. **Check hook configuration:**
   ```bash
   cat /opt/airglow/configs/ledfx-hooks.yaml
   # Verify hooks.start.enabled is true
   # Verify virtual IDs are correct
   ```

2. **Check hook logs:**
   ```bash
   docker exec shairport-sync cat /var/log/shairport-sync/ledfx-session-hook.log
   ```

3. **Test hook script manually:**
   ```bash
   docker exec shairport-sync /scripts/ledfx/ledfx-start.sh
   ```

4. **Verify LedFX API is accessible:**
   ```bash
   curl http://localhost:8888/api/virtuals
   ```

5. **Check virtual IDs exist:**
   ```bash
   curl http://localhost:8888/api/virtuals | jq '.virtuals | keys'
   ```

---

## Network Issues

### Macvlan Network Creation Fails

**Symptoms:**
- `docker compose up` fails with network error
- "Pool overlaps with other one" error

**Solutions:**

1. **Check existing networks:**
   ```bash
   docker network ls
   docker network inspect shairport-macvlan
   ```

2. **Remove conflicting network:**
   ```bash
   docker network rm shairport-macvlan
   docker compose up -d
   ```

3. **Verify network interface exists:**
   ```bash
   ip link show eth0  # or your configured interface
   ```

4. **Check subnet configuration:**
   - Ensure subnet doesn't conflict with existing networks
   - Verify gateway is correct for your network

### Bridge Network Communication Issues

**Symptoms:**
- Containers can't reach each other
- API calls fail between containers
- DNS resolution fails

**Solutions:**

1. **Check network connectivity:**
   ```bash
   docker exec ledfx ping -c 3 shairport-sync
   docker exec airglow-web ping -c 3 ledfx
   ```

2. **Verify containers are on same network:**
   ```bash
   docker network inspect airglow-network
   # Should list all containers
   ```

3. **Check container names:**
   - Ensure using container names (not IPs) for service discovery
   - Verify container names match in docker-compose.yml

---

## Configuration Issues

### Configuration Not Saving

**Symptoms:**
- Changes in web UI don't persist
- Configuration reverts after restart

**Solutions:**

1. **Check file permissions:**
   ```bash
   ls -la /opt/airglow/configs/
   # Should be writable by container user
   ```

2. **Verify volume mounts:**
   ```bash
   docker inspect airglow-web | grep -A 10 Mounts
   # Should show /configs mounted as rw
   ```

3. **Check disk space:**
   ```bash
   df -h /opt/airglow
   ```

4. **Verify YAML syntax:**
   ```bash
   yq eval /opt/airglow/configs/ledfx-hooks.yaml
   # Should not show syntax errors
   ```

### Invalid Configuration Errors

**Symptoms:**
- Error messages about invalid config
- Services fail to start with config errors

**Solutions:**

1. **Validate YAML syntax:**
   ```bash
   yq eval /opt/airglow/configs/ledfx-hooks.yaml
   ```

2. **Check shairport-sync config:**
   ```bash
   docker exec shairport-sync shairport-sync --displayConfig
   # Should not show syntax errors
   ```

3. **Restore from backup:**
   ```bash
   # Check for backup files
   ls -la /opt/airglow*.backup.*
   # Restore if needed
   cp /opt/airglow*.backup.*/configs/* /opt/airglow/configs/
   ```

---

## Performance Issues

### High CPU Usage

**Symptoms:**
- System becomes slow
- Containers use excessive CPU

**Solutions:**

1. **Check container resource usage:**
   ```bash
   docker stats
   ```

2. **Identify resource-intensive containers:**
   - LedFX may use CPU during visualization
   - Shairport-sync should use minimal CPU when idle

3. **Check for errors causing loops:**
   ```bash
   docker logs <container> | grep -i "error" | wc -l
   # High error count may indicate issues
   ```

4. **Restart containers:**
   ```bash
   docker compose restart
   ```

### Slow API Responses

**Symptoms:**
- Status page loads slowly
- API calls timeout

**Solutions:**

1. **Check API response times:**
   ```bash
   time curl http://localhost:8888/api/info
   ```

2. **Verify network connectivity:**
   ```bash
   docker exec airglow-web ping -c 3 ledfx
   ```

3. **Check for API retries:**
   - API calls now have retry logic with exponential backoff
   - Check logs for retry attempts

4. **Restart web container:**
   ```bash
   docker restart airglow-web
   ```

---

## Diagnostic Tools

### Run Full Diagnostic

```bash
cd /opt/airglow
./scripts/diagnose-airglow.sh
```

### Check Specific Component

```bash
# Shairport-Sync
source scripts/diagnostics/diagnose-shairport.sh

# LedFX
source scripts/diagnostics/diagnose-ledfx.sh

# PulseAudio
source scripts/diagnostics/diagnose-pulseaudio.sh
```

### Get JSON Diagnostic Output

```bash
./scripts/diagnose-airglow.sh --json | jq
```

---

## Getting Help

If issues persist:

1. **Collect diagnostic information:**
   ```bash
   ./scripts/diagnose-airglow.sh --json > diagnostic.json
   docker logs ledfx > ledfx.log
   docker logs shairport-sync > shairport.log
   docker logs airglow-web > web.log
   ```

2. **Check GitHub Issues:**
   - Search for similar issues
   - Create new issue with diagnostic output

3. **Review logs:**
   - Check all container logs
   - Look for error patterns
   - Check system logs: `journalctl -u docker`

---

## Common Error Messages

### "Address already in use"
- **Cause:** Port is already bound by another process
- **Solution:** Find and stop conflicting process, or change port in docker-compose.yml

### "Network not found"
- **Cause:** Docker network doesn't exist
- **Solution:** Run `docker compose up` to create networks

### "Permission denied"
- **Cause:** File permissions incorrect
- **Solution:** Check ownership and permissions, ensure volumes are mounted correctly

### "Connection refused"
- **Cause:** Service not running or not listening on expected port
- **Solution:** Check container is running, verify port configuration

### "Timeout"
- **Cause:** Service not responding within timeout period
- **Solution:** Check service logs, verify service is healthy, increase timeout if needed

