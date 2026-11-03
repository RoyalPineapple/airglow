# Install Airglow beta

Supported reference: x86-64 NixOS 26.05, one wired LAN interface, and local-subnet AirPlay discovery. This is an audio-analysis endpoint, not an audible speaker. LedFX manages lighting devices and effects.

## Import the VM

1. Download `airglow-0.1.0-beta.1-x86_64-linux.qcow2`, `release.json` and `SHA256SUMS` from the same release. Verify the checksums before importing.
2. Create an x86-64 VM with UEFI/OVMF, Secure Boot disabled, two virtual CPUs and 2 GB RAM. Import the disk as a writable boot disk. Its virtual capacity is 16 GiB; the download is compressed and sparse. Attach one VirtIO network adapter to your wired LAN bridge. NAT networking does not provide the supported AirPlay discovery path.
3. Start the VM. DHCP assigns its address. Find it in your router, hypervisor guest-agent view, or the VM console with `ip -4 address show eth0`.
4. Open `http://<VM-address>/`. `http://airglow.local/` may also resolve on your LAN. Set the receiver name and optional password under **Configuration → AirPlay settings**.
5. Use **Open LedFX** to add your actual lighting device and select an effect. Device support comes from LedFX; a device does not need WLED.
6. Choose this receiver on your Apple source. Confirm discovery, real playback and light response. Configure optional playback actions only after this works.

The image contains no saved lighting devices, receiver password or SSH keys. SSH is disabled. The hypervisor console signs in as root for initial administration; there is no shared console password. Keep the console under your hypervisor's access controls. Set your own credentials before enabling remote administration.

The VM keeps its editable host configuration in `/etc/nixos`. Host configuration is private. Web settings are in `/var/lib/airglow/airglow.json`; LedFX data is in `/var/lib/ledfx`. Do not put credentials into Nix expressions.

For a larger disk, expand the imported disk in the hypervisor before booting. The root partition/filesystem grows on boot. The boot image and its initial configuration stay on the current version until you explicitly update them.

## Install on an existing NixOS host

Use `nix/flake-example.nix` as a starting point. If a host already has a flake, add the Airglow input and module to it; do not replace that flake or its hardware configuration.

```nix
inputs.airglow.url = "github:RoyalPineapple/airglow/v0.1.0-beta.1";
inputs.airglow.inputs.nixpkgs.follows = "nixpkgs";
```

Import `airglow.nixosModules.default`. Set `services.airglow.address` to an existing host address and `services.airglow.interface` to its LAN interface. The `appliance` module is for the downloadable VM; it includes VM networking, disk and boot defaults.

```sh
cd /etc/nixos
sudo nix --extra-experimental-features 'nix-command flakes' flake lock
sudo nixos-rebuild build --flake .#airglow
sudo nixos-rebuild switch --flake .#airglow
```

Use your own host's output name instead of `airglow` when appropriate. Empty web admin passwords mean no login. Both web interfaces belong on a trusted LAN; public exposure is outside beta support.

## Update explicitly

1. Make and verify the private backup described in [RECOVERY.md](RECOVERY.md).
2. Change the Airglow tag in the private `/etc/nixos/flake.nix` to the next release. Keep the previous file and lock file with the backup.
3. Run `nix flake update airglow` and review the new lock file.
4. Run `sudo nixos-rebuild build --flake .#airglow` before switching. Run `sudo nixos-rebuild switch --flake .#airglow` when ready for a receiver interruption.
5. Check State and Troubleshooting, then run a real Apple-source playback test.

Never move an existing release tag. Releases do not update a host automatically. If software or data recovery is needed, follow [RECOVERY.md](RECOVERY.md).
