# Airglow 0.1.0-beta.1

Draft external-beta candidate. Do not promote this release to general availability until the physical and pilot gates in RELEASING.md are completed.

- Native NixOS services for AirPlay 2 → PulseAudio → LedFX; no Docker.
- One versioned flake containing the module, web interface and action worker.
- A generic DHCP/UEFI qcow2 appliance for a bridged wired LAN.
- Compact configuration, state and troubleshooting views, including failed and unknown states.
- Independent, deadline-bounded start/end actions with worker recovery and explicit targets.
- Private settings export/import, separate full-data recovery instructions, and release identification in the interface and diagnostics.

Supported reference: x86-64 NixOS 26.05, one wired LAN interface, local discovery. The existing development playback path was user-confirmed with Govee devices. Other LedFX devices are not certified by this release. No audible speaker output is provided.

Assets: compressed qcow2 disk, release manifest, SHA-256 checksums, installation/recovery guides and license/source information. `release.json` records the exact commit, Nixpkgs revision, configuration version and component versions.

Known limits: no automatic Docker-data migration; no ARM support; no routed/NAT AirPlay discovery; no automatic updater. Generation rollback does not restore mutable data. A worker crash after command acceptance and before its receipt can resend that command.

Automated acceptance includes the native-service/mDNS test and actual UEFI-image cold boot, DHCP discovery, data recovery, reboot persistence and independent-clone identity. Physical two-host playback, 100 start/end cycles, a seven-day soak and the five-household pilot remain release gates.
