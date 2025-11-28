# Airglow Configuration Files

## shairport-sync.conf

Main Shairport-Sync configuration file. **AirPlay session hooks are disabled by default.**

To enable automatic LedFx control when AirPlay connects/disconnects:
1. Edit `configs/shairport-sync.conf`
2. Uncomment the hook lines in the `sessioncontrol` section:
   ```conf
   run_this_before_entering_active_state = "/scripts/ledfx-session-hook.sh start active_state";
   run_this_after_exiting_active_state = "/scripts/ledfx-session-hook.sh stop exit_active";
   active_state_timeout = 10.0;
   wait_for_completion = "yes";
   ```
3. Redeploy: `./scripts/maintenance/update-airglow.sh <CT_ID>`

## ledfx-hooks.yaml

Configuration file for AirPlay session hooks that control LedFx virtuals.
**Only used when hooks are enabled in shairport-sync.conf.**

See [CONFIGURATION.md](../CONFIGURATION.md) for detailed documentation on the YAML format.

