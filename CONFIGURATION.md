# Configuration

## NixOS service settings

Import `nix/module.nix` and configure `services.airglow`:

| Setting | Meaning |
|---|---|
| `enable` | Enable the native services; defaults to false |
| `address` | Existing host IPv4 address for the web, LedFX and AirPlay checks |
| `interface` | LAN interface for AirPlay and lighting reply firewall rules |
| `ledfxBrowserUrl` | Optional browser-facing LedFX URL; defaults to the address on port 8888 |

The module enables Shairport Sync with AirPlay 2, NQPTP, Avahi, a local PulseAudio
bridge, LedFX, the web interface and one session-action worker. No Docker is installed.
It does not set host networking, credentials, filesystem UUIDs or SSH keys.

Shairport and NQPTP source tags/hashes and the LedFX package collection revision are
pinned in the module. The host's own NixOS/nixpkgs revision is managed by the host owner.
Do not treat package pinning as a pin of the whole operating system.

## Saved settings

| Path | Contents | In Git? |
|---|---|---|
| `/var/lib/airglow/receiver.json` | Receiver name, volume handling, idle delay and optional AirPlay password | No |
| `/var/lib/airglow/ledfx-hooks.yaml` | Enabled playback actions and selected outputs/scenes | No |
| `/var/lib/ledfx/` | LedFX configuration, devices, effects, scenes and other saved data | No |
| `/run/airglow/` | Current receiver session, event mailbox, worker readiness and last result | No; runtime only |
| `nix/hosts/` | Optional local host deployment configuration | No |

Receiver overrides are written atomically with mode 0640. Passwords are not returned
by the settings API or included in the diagnostic download. Empty receiver names use
the hostname. Only AirPlay 2 is supported.

Existing hook YAML extensions are preserved. Legacy repeat values are accepted for
compatibility; positive values send one command, and zero leaves an output disabled.
Existing multiple-scene selections are preserved until replaced with one scene in the UI.

Use LedFX's interface/API while it runs. Airglow never overwrites an existing LedFX
configuration during service startup. First installation resolves the named audio
bridge rather than assuming the capture-device index is zero.

## Upgrades and rollback

Back up the two mutable state directories before applying an upgrade. Use a consistent
backup made with their writers stopped. Do not back up `/run/airglow` or replay old events.

Build the candidate NixOS configuration before switching. NixOS software rollback does
not restore saved application state; use the matching state backup when necessary.
There are no automatic updates, automatic data migrations or automatic data rollback.

The Receiver tab configures the inactive-session grace period from 1 to 300 whole
seconds (default 10). Applying it restarts AirPlay. The wrapper renders a numeric
Shairport timeout in runtime storage; it does not edit the Nix-managed base file.

Run test sends a validated snapshot of the current on-screen action to the worker.
It does not save the snapshot as automation. Playback callbacks still use the saved YAML.
