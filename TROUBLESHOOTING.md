# Troubleshooting

1. Open Airglow's State page and follow the first unavailable connection.
2. Open Troubleshooting for service/discovery checks and a diagnostic download.
3. Open LedFX separately to check its selected audio input, effects and output devices.

On the NixOS host, inspect the native services:

```sh
systemctl status airglow airglow-actions shairport-sync nqptp pulseaudio ledfx
journalctl -u airglow -u airglow-actions -u shairport-sync --since '10 minutes ago'
```

`/healthz` checks only the web process. `/api/status` reports connection observations;
neither proves that a physical lamp responded. LedFX's virtual `streaming` flag describes
routing from another virtual, not incoming audio.

## Playback actions

Choose an action and use its Test button; unsaved choices can be tested. A test changes output immediately,
including an end-action test; it does not wait for the inactive-session grace period or save the tested choices.
A successful result means LedFX accepted the command. Check the lamps separately.
Globally paused LedFX output, missing effects, deleted targets and overlapping virtual
segments can prevent the intended result even when the controller is reachable.

If a test cannot be queued, check `airglow-actions` and `/run/airglow/receiver`.
Queue admission checks a live process and a recent worker heartbeat, not marker presence.
After a restart, unfinished events from the current receiver session are retried.
Completed receipts and older receiver sessions are not replayed. Conflicting output
segments fail before activation; use non-overlapping outputs or a LedFX scene.
A partial failure means some targets accepted the command and others failed.
The shared runtime directory must survive worker stop/start while the receiver runs.
Do not copy runtime files between hosts or restore them from a backup.

## Discovery and audio

Use a wired LAN with multicast discovery between the Apple source and receiver.
Confirm Shairport, NQPTP and Avahi are running, and the configured interface is correct.
Only AirPlay 2 is supported. This endpoint has no audible speaker.

LedFX reads the local PulseAudio bridge through its named ALSA capture source.
No active capture while no audio-reactive effect is running is not enough to diagnose a
failure. Check the configured input and an active effect in LedFX during real playback.

## Diagnostics and privacy

The download contains an allowlist of service states, connection results and versions.
It excludes raw configuration, passwords, cookies and unrelated host inventories.
Logs viewed directly on the host are separate from that download; review before sharing.

## Settings backup and recovery

Use Configuration → Backup to download or restore the versioned Airglow settings file.
Keep the download private; it includes the AirPlay password. Restore validates the file
and shows a summary before applying it. It does not need LedFX to be online. Invalid
settings can be replaced by a valid backup through this screen.

The active file is `/var/lib/airglow/airglow.json`. The older receiver JSON and hook YAML
are retained migration inputs and are ignored after migration. Do not edit those old files
expecting live settings to change. Before overwriting the active file during restore,
Airglow saves one private previous copy; a failed previous-copy write aborts the restore.
