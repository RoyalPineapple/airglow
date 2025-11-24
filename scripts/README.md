# Airglow Scripts

Scripts for controlling LedFx based on AirPlay session events.

## Scripts

### `ledfx-start.sh`
Activates LedFx virtual(s) when AirPlay connects.

**Usage:**
```bash
ledfx-start.sh [virtual_ids] [host] [port]
```

**Behavior:**
- Sets `active: true` for specified virtual(s)
- Does NOT touch global paused state (only affects specified virtuals)
- Preserves existing effects

### `ledfx-stop.sh`
Deactivates LedFx virtual(s) when AirPlay disconnects.

**Usage:**
```bash
ledfx-stop.sh [virtual_ids] [host] [port]
```

**Behavior:**
- Sets `active: false` for specified virtual(s)
- Preserves effects for next activation

### `ledfx-session-hook.sh`
Main hook script called by Shairport-Sync on AirPlay session events.

**Actions:**
- `start`: Activates virtual(s) via `ledfx-start.sh`
- `stop`: Deactivates virtual(s) via `ledfx-stop.sh`
- `log`: Logs events (for play_begins/play_ends callbacks)

### `diagnose-airglow.sh`
Comprehensive diagnostic tool for the entire audio flow.

**Usage:**
```bash
./diagnose-airglow.sh                    # Run on localhost
./diagnose-airglow.sh 192.168.2.122     # Run on remote host
```

**Checks:**
1. Shairport-Sync (container, process, config, hooks, device name)
2. PulseAudio (server, sink-inputs, Shairport connection)
3. LedFx (API, virtuals, effects, devices, streaming state)

## Configuration

### `ledfx-hooks.conf`
Configuration file for AirPlay session hooks.

**Variables:**
- `VIRTUAL_IDS`: Comma-separated list of virtual IDs to control
- `LEDFX_HOST`: LedFx API hostname (default: localhost)
- `LEDFX_PORT`: LedFx API port (default: 8888)

## TODO: Callback Configuration Improvements

### High Priority

- [ ] **Device/Scene Selection**
  - [ ] Add configuration option to choose between controlling devices (virtuals) or scenes
  - [ ] Support scene activation/deactivation via LedFx API
  - [ ] Update `ledfx-hooks.conf` to support `CONTROL_TYPE` (devices|scenes)
  - [ ] Update scripts to handle both devices and scenes

- [ ] **Effect Selection**
  - [ ] Add configuration option to specify which effect to activate on AirPlay connect
  - [ ] Support effect name or type (e.g., "rain", "gradient", "energy")
  - [ ] Allow different effects for different virtuals
  - [ ] Option to restore last effect vs. always use specified effect
  - [ ] Update `ledfx-hooks.conf` to support `EFFECT_NAME` or `EFFECT_TYPE`

### Medium Priority

- [ ] **Enhanced Logging**
  - [ ] Add structured logging (JSON format option)
  - [ ] Log effect changes and virtual state transitions
  - [ ] Add log rotation for hook logs

- [ ] **Error Handling**
  - [ ] Better error messages when virtual/scene not found
  - [ ] Retry logic for API calls
  - [ ] Validation of configuration values

- [ ] **Testing**
  - [ ] Add unit tests for script functions
  - [ ] Integration tests for full AirPlay → LedFx flow
  - [ ] Test with multiple virtuals and scenes

### Low Priority

- [ ] **Documentation**
  - [ ] Add examples for common configurations
  - [ ] Document all available effects
  - [ ] Add troubleshooting guide

- [ ] **Performance**
  - [ ] Optimize API calls (batch operations if possible)
  - [ ] Cache virtual/scene lists

## Current Limitations

1. **Only controls virtuals** - No scene support yet
2. **No effect selection** - Uses whatever effect is already configured
3. **Global paused state** - We intentionally don't touch it, but this means if global is paused, our virtuals won't work
4. **Single configuration** - One config applies to all AirPlay connections

## Future: MQTT Integration

Once callback configuration is complete, we'll prototype an MQTT-based solution that:
- Subscribes to Shairport-Sync MQTT events (`play_start`, `play_end`)
- Provides more reliable playback detection
- Enables integration with Home Assistant and other automation systems
- Supports per-track effect selection based on metadata

