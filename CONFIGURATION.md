# Configuration

## Airglow settings file

`/var/lib/airglow/airglow.json` is the source of truth for all settings managed by the
Airglow interface. The receiver wrapper, web interface and session-action worker use
this file. It is versioned JSON and is private: it includes the AirPlay password.

See [the public example](configs/airglow.example.json) for the complete version 1 shape:

- `version`: configuration format version, currently 1.
- `receiver`: name, AirPlay mode, fixed-volume flag, password and idle delay.
- `hooks`: independent start/end actions, enable flags, explicit output scope, selected
  virtual IDs and scene IDs. Legacy hook extensions are retained.
- `extensions`: preserved metadata from the previous YAML configuration. It does not
  override Nix-managed network bindings or service installation.

Empty receiver names use the hostname. Only AirPlay 2 is supported. The idle delay is
1–300 whole seconds, default 10. Applying receiver changes requests an AirPlay restart.
The wrapper renders a numeric timeout into runtime storage; it never edits the
Nix-managed Shairport base file. The stable restart signal records which receiver
settings were requested, so a failed signal can be retried without changing the values.
A request receipt is not proof that Shairport has applied or advertised the new settings.

## Download and restore

Open **Configuration → Backup** to download `airglow.json`. Keep it private: the export
includes the AirPlay password. Passwords remain omitted from ordinary settings responses,
restore previews and diagnostics. An optional web login also protects these backup routes.

Choose a JSON file to restore. Airglow validates its format and shows a summary before
applying it. Unsupported versions and malformed/incomplete files are rejected without
replacing saved settings. Restore does not require LedFX to be online.

Restoring replaces the complete Airglow settings file and discards unsaved browser edits.
Receiver changes request a restart; playback-action changes take effect for later events.
Before replacement, Airglow keeps a private `airglow.previous.json` copy. If creating that
copy fails, restoration is aborted. The previous copy is replaced on the next restore,
so backup storage does not grow without limit.

Writes use a process-safe lock, atomic replacement, and file/directory synchronization.
Normal receiver and action saves update only their respective section, preserving the
other settings. Manual tests use a validated runtime snapshot of current on-screen
choices and do not save it as automation.

## Migration

Before the worker starts, Airglow imports an existing `receiver.json` and
`ledfx-hooks.yaml` if the new file does not exist. Existing names, passwords, volume
handling, idle delay, action selections and supported extensions are retained. The old
files are left unchanged. After migration, they are not read or updated; `airglow.json`
is authoritative. An invalid existing file stops migration rather than silently resetting
settings.

Legacy repeat values remain accepted for compatibility. Positive values send one command;
zero leaves an output disabled. Existing scene sequences remain intact until changed.

## What stays outside this file

- LedFX owns its complete `/var/lib/ledfx` directory, including devices, effects, presets
  and scenes. Back it up separately. Restoring Airglow does not import LedFX data; saved
  virtual and scene references must exist in the destination LedFX installation.
- Nix owns host addresses/interfaces, the LedFX browser URL, package versions and service
  installation. SSH access, disk configuration and the optional web-login secret remain
  in private host configuration. Supply web secrets through a private EnvironmentFile.
- `/run/airglow` contains receiver sessions, events and results. Never restore it from a
  backup or replay old events.

## NixOS module

Import `nix/module.nix` and configure `services.airglow`:

| Setting | Meaning |
|---|---|
| `enable` | Enable the native services; defaults to false |
| `address` | Existing host IPv4 address for web, LedFX and AirPlay checks |
| `interface` | LAN interface for AirPlay and lighting reply firewall rules |
| `ledfxBrowserUrl` | Optional browser URL; defaults to the address on port 8888 |

The module enables Shairport Sync with AirPlay 2, NQPTP, Avahi, a local PulseAudio
bridge, LedFX, the web interface and one worker. It installs no Docker and does not set
host networking, disks or SSH keys. Application source and the module stay together.
Shairport/NQPTP source tags and the LedFX package collection revision are pinned; the
host owner manages the overall NixOS/nixpkgs revision.

A NixOS generation rollback restores software, not mutable application data. Retain a
matching Airglow configuration download and separate LedFX data backup before upgrades.
Older generations that predate the new format still read the retained legacy files.
