# Airglow

Airglow connects **AirPlay 2 → PulseAudio → LedFX** using native NixOS services.
It receives music for lighting analysis; it is not an audible speaker.

Airglow manages the audio connection and optional playback actions. Configure lighting
devices, effects, presets, scenes and brightness in LedFX's separate interface.
Devices do not need to run WLED; the development installation uses Govee devices.

## Deployment

This branch replaces the Docker Compose deployment with a NixOS module and a new web
interface. It does not install Docker or require a Docker socket.

Import [nix/module.nix](nix/module.nix) into an existing NixOS host configuration.
Use [nix/example.nix](nix/example.nix) as a starting point. Its address is reserved
for documentation and must be replaced with an address already assigned to the host.
The module manages services; your host configuration retains networking, disks,
bootloader, SSH access and operating-system version settings.

Keep the repository's `nix`, `scripts` and `web` directories together: the module
packages its runtime source from relative paths. Run `nixos-rebuild build` to check
the candidate before applying it with `nixos-rebuild switch`.

The validated reference is an x86-64 NixOS VM on a wired home LAN. Other host
architectures and routed discovery have not been validated. This is a development
migration, not a general-purpose installer or an automatic migration of existing data.

## Interface

Open the configured host address for Airglow. LedFX runs on port 8888.
Set `services.airglow.ledfxBrowserUrl` if browsers access LedFX through another URL.

- **State:** receiver discovery, audio connectivity, LedFX availability, device status
  and playback-action failures. Missing evidence is shown as unknown.
- **Configuration:** receiver name, optional AirPlay password, volume handling, idle delay, and
  independent start/end actions. The default receiver name comes from the hostname.
- **Backup:** download one private Airglow settings file, or validate and restore an uploaded copy.
- **Troubleshooting:** connection checks and an allowlisted diagnostic download.

Playback actions default to disabled. Select existing outputs or scenes in LedFX.
Start resumes the selected outputs' saved effects; end stops their output after a
configured inactive-session grace period (10 seconds by default). Stopping output is not a physical power-off
command. Scene actions apply the scene's own saved instructions; there is no state
restoration. The manual test buttons run the current on-screen actions immediately without saving them, and change lighting.
Each selected output receives one command. Legacy zero-repeat entries remain disabled.

Saving receiver settings restarts the receiver and may interrupt playback. Saving
playback actions does not restart it. The action worker runs separately from audio,
serializes requests, skips superseded pending events and applies a 10-second deadline.
Worker updates preserve the receiver's shared runtime directory; receiver startup
creates a fresh session and clears old events.

There is no web login when `AIRGLOW_ADMIN_PASSWORD` is empty or unset. Supply that
value through a root-owned systemd `EnvironmentFile` outside the repository to enable
the `admin` login. Do not put passwords in Nix expressions or the Nix store. An AirPlay password
is a separate receiver setting. Keep the services on a trusted LAN; cross-origin
writes are rejected. Do not expose LedFX or Airglow publicly without your own access controls.

## Data and migration

See [CONFIGURATION.md](CONFIGURATION.md) for settings and files, and
[TROUBLESHOOTING.md](TROUBLESHOOTING.md) for checks.

Before replacing an existing deployment, stop it and back up its receiver settings,
playback-action YAML and complete LedFX data directory. There is no automatic Docker
volume importer. Preserve a copy outside the new host. Native LedFX uses
`/var/lib/ledfx`; Airglow uses `/var/lib/airglow/airglow.json` as its settings file.
Download and restore it under **Configuration → Backup**. It includes the AirPlay password;
store backups privately. Legacy receiver JSON and hook YAML are imported once and retained
unchanged. LedFX data and Nix-managed host/deployment settings are backed up separately. Confirm ownership for the respective
service users before starting restored services. The first-start audio configuration
is seeded only when LedFX has no existing configuration file.

A NixOS generation rollback restores software and service configuration, **not mutable
LedFX or Airglow data**. Back up those directories separately before upgrades.

## Repository boundaries

Commit application source, the reusable Nix module, the public example, tests,
documentation and shipped assets. Keep private host configuration under ignored
`nix/hosts/` or outside this repository. Never commit passwords, private SSH keys,
actual LAN addresses, disk identifiers, `.env` files, saved device configurations,
LedFX data, runtime events, backups, logs, screenshots or design mockups.

## Checks and known limits

```sh
python3 -m venv .venv
.venv/bin/pip install -r web/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
node --check web/static/configuration.js
node --check web/static/state.js
sh -n scripts/publish-session.sh
```

The development VM passed a native NixOS rebuild, state/configuration browser checks,
and real start/end test-button requests affecting four Govee virtual outputs. The
user confirmed the playback path and test actions work. Worker stop/start preservation
was checked on systemd. The automated tests use a local LedFX HTTP fixture and mocked
host observations; they do not replace physical acceptance. Multi-host installation,
100-cycle endurance, seven-day soak and external-household pilot remain outstanding.

Airglow is MIT-licensed. Upstream applications retain their own licenses.
