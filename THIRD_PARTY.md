# Third-party software and source

Airglow application code is MIT-licensed; see LICENSE. The VM is a NixOS system containing separately licensed upstream software. Airglow does not relicense it.

Primary components and their pinned source:

- Shairport Sync 5.6.2: https://github.com/mikebrady/shairport-sync/tree/5.6.2 — notices in LICENSES and the source headers.
- NQPTP 1.2.9: https://github.com/mikebrady/nqptp/tree/1.2.9 — GPL version 2; see its LICENSE and source notices.
- LedFX 2.2.1: https://github.com/LedFx/LedFx/tree/v2.2.1 — see LICENSE.txt and the Nixpkgs package recipe for the actual pinned source revision.
- PulseAudio and the operating-system closure: the exact Nixpkgs revision is recorded in release.json and flake.lock. Nixpkgs recipes identify source URLs, hashes, patches and licenses.

The release's flake and nix/module.nix contain the corresponding Airglow build/service definitions and upstream source overrides. Preserve these references and upstream notices when redistributing.

Before publicly distributing the VM, check corresponding-source availability and license notices for its entire runtime closure. This index covers primary components and does not claim to be a complete OS license inventory. The draft VM is not cleared for public binary redistribution until that release gate is recorded.
