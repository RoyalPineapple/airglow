# Airglow

Airglow connects **AirPlay 2 → PulseAudio → LedFX** using native NixOS services.
It receives music for lighting analysis; it is not an audible speaker.

Airglow manages the audio connection and optional playback actions. Configure lighting
devices, effects, presets, scenes and brightness in LedFX's separate interface.
Devices do not need to run WLED; the development installation uses Govee devices.

## Deployment

The beta package is one versioned flake. For the downloadable DHCP/UEFI VM or an
existing NixOS host, follow [the installation guide](docs/INSTALL.md). Use
[the recovery guide](docs/RECOVERY.md) before switching releases. Release assets
and publication gates are described in [RELEASING.md](RELEASING.md).

Use Airglow as a flake input in your NixOS host configuration. The flake includes
both the NixOS module and Airglow's web/worker source; no separate application checkout
or installation is needed.

Copy [nix/flake-example.nix](nix/flake-example.nix) to `/etc/nixos/flake.nix` as a starting
point, keeping your existing `configuration.nix` and hardware configuration. Replace
the documentation address and interface with your host's settings. If the existing
configuration imports Airglow directly, remove that duplicate import.

```sh
cd /etc/nixos
sudo nix --extra-experimental-features 'nix-command flakes' flake lock
sudo nixos-rebuild build --flake .#airglow
sudo nixos-rebuild switch --flake .#airglow
```

Enable `nix.settings.experimental-features = [ "nix-command" "flakes" ];` in your host
configuration for later commands. Commit your host's `flake.lock` to its private
configuration repository. It fixes the exact Airglow and Nixpkgs revisions used by
that host. Updates are explicit: run `nix flake update airglow`, review the lock change,
then build before switching. Change the release tag in the host input before updating its lock file.

Airglow exports `nixosModules.default` and the equivalent `nixosModules.airglow`.
Host networking, disks, bootloader, SSH and operating-system version settings stay
in your host configuration. Credentials and mutable settings stay outside the public
repository and Nix store.

Direct module imports still work: use [nix/example.nix](nix/example.nix) and keep the
repository's `nix`, `scripts` and `web` directories together.

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
- **Backup & restore:** download one private Airglow settings file, or validate and restore an uploaded copy.
- **Troubleshooting:** connection checks and an allowlisted diagnostic download.

Playback actions default to disabled. Select existing outputs or scenes in LedFX.
Start resumes the selected outputs' saved effects; end stops their output after a
configured inactive-session grace period (10 seconds by default). Stopping output is not a physical power-off
command. Scene actions apply the scene's own saved instructions; there is no state
restoration. The manual test buttons run the current on-screen actions immediately without saving them, and change lighting.
Each selected output receives one command. Legacy zero-repeat entries remain disabled.

Saving receiver settings requests a restart and may interrupt playback. The interface
confirms application only after the runtime configuration and both discovery names match. Saving
playback actions does not restart it. The action worker runs separately from audio,
serializes requests, skips superseded pending events and applies a 10-second deadline.
Worker updates preserve the receiver's shared runtime directory; receiver startup
creates a fresh session and clears old events. Unfinished current-session events are
retried after a worker restart; completed events are not replayed. A crash between a
LedFX request and its receipt can cause that command to be sent again.
Conflicting output selections are rejected before activation; use a LedFX scene
for deliberate overlapping layouts. Independent targets report partial failures.

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
Download and restore it under **Configuration → Backup & restore**. It includes the AirPlay password;
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
node --check web/static/troubleshooting.js
sh -n scripts/publish-session.sh
# Linux with Nix and KVM: builds the stack and runs native service/discovery checks.
nix --extra-experimental-features 'nix-command flakes' flake check --print-build-logs
```

The development VM passed a native NixOS rebuild, state/configuration browser checks,
and real start/end test-button requests affecting four Govee virtual outputs. The
user confirmed the playback path and test actions work. The NixOS integration test boots the full stack and checks repeated receiver updates,
both discovery records, offline editing, stale worker readiness and event recovery
through real systemd services. Python regressions also use a local LedFX HTTP fixture
and mocked host observations. These checks do not replace physical acceptance. Multi-host installation,
100-cycle endurance, seven-day soak and external-household pilot remain outstanding.

Airglow is MIT-licensed. Upstream applications retain their own licenses.
