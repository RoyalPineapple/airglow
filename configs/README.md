# Airglow Configuration Files

## ledfx-hooks.conf

Configuration file for AirPlay session hooks that control LedFx virtuals.

### Configuration Options

#### VIRTUAL_IDS
Comma-separated list of LedFx virtual IDs to control when AirPlay connects/disconnects.

**Examples:**
```bash
# Control a single virtual
VIRTUAL_IDS="dig-quad"

# Control multiple virtuals
VIRTUAL_IDS="dig-quad,bedroom-strip,living-room"

# Control all virtuals (leave empty or unset)
VIRTUAL_IDS=""
```

**Default:** `dig-quad`

#### LEDFX_HOST
LedFx API hostname or IP address.

**Default:** `localhost`

#### LEDFX_PORT
LedFx API port.

**Default:** `8888`

### How to Configure

1. **Edit the config file** (recommended):
   ```bash
   vim configs/ledfx-hooks.conf
   ```

2. **Or use environment variables** in `docker-compose.yml`:
   ```yaml
   environment:
     - LEDFX_VIRTUAL_IDS=dig-quad,another-virtual
   ```

3. **Redeploy** to apply changes:
   ```bash
   ./scripts/maintenance/update-airglow.sh <CT_ID>
   ```

### Finding Your Virtual IDs

List all virtuals in LedFx:
```bash
curl -s http://localhost:8888/api/virtuals | jq '.virtuals | keys'
```

Or check the LedFx web UI at `http://<host>:8888` - virtual IDs are shown in the device list.

### Behavior

- **On AirPlay Connect:** All specified virtuals are activated and unpaused
- **On AirPlay Disconnect:** All specified virtuals are paused and deactivated
- **If VIRTUAL_IDS is empty:** All virtuals in LedFx are controlled automatically

