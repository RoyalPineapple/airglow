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

Save and enable an action, then use its Test button. A test changes output immediately,
including an end-action test; it does not wait for the inactive-session grace period.
A successful result means LedFX accepted the command. Check the lamps separately.
Globally paused LedFX output, missing effects, deleted targets and overlapping virtual
segments can prevent the intended result even when the controller is reachable.

If a test cannot be queued, check `airglow-actions` and `/run/airglow/receiver`.
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
