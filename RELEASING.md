# Release Airglow

Use one tagged Git revision for the flake, application and VM. Do not rebuild or move a published tag. Private host configuration, credentials, backups and lighting data never belong in release assets.

## Prepare the candidate

1. Set `web/release.json` to the candidate version. Update the public example's release tag and release notes.
2. Run Python/JavaScript/shell checks and `nix flake check`. This boots native services and the actual qcow2 image, including fresh-clone identity and data recovery.
3. Require green checks on the exact candidate commit. On branch/tag pushes, CI packages the VM, manifest, checksums and guides as an `airglow-release-<commit>` artifact. Pull-request merge commits do not produce distributable artifacts.
4. Download that artifact and verify every checksum. The manifest revision must equal the candidate Git commit; `development` builds are not release artifacts.
5. Create an annotated `v<version>` tag on the tested commit. Push the tag, verify its CI run, and fetch the flake through that public tag on a clean NixOS host.
6. Tag CI creates a draft GitHub pre-release and attaches the tested assets only after all checks pass. It refuses to overwrite a published release. Keep the release in draft until the gates below pass. Do not add reviewers or merge the migration PR as part of release packaging.

## Publication gates

- [ ] Exact tagged commit passed CI and public-tag installation/recovery rehearsal.
- [ ] VM checksums and source revision match; no user configuration, SSH host keys, passwords or machine identity were embedded.
- [ ] License notices and corresponding-source access for the complete redistributed VM closure are checked. THIRD_PARTY.md is an index, not a substitute for that review.
- [ ] Two clean supported hosts passed real Apple-source discovery and 30-minute playback with intended lighting outputs.
- [ ] Pauses, disconnects, receiver restart and network loss passed; callbacks meet the reference-host latency gate.
- [ ] 100 start/end cycles passed without stale final actions or hook-caused audio interruption.
- [ ] Seven-day soak completed without manual recovery or uncontrolled disk growth.
- [ ] Named pilot participants and the supported setup are agreed. Invite five households; target four unassisted installations and zero configuration loss.

Only then publish the pre-release and begin the pilot. Keep changes explicit and maintain matching software/data recovery copies. Promote beyond beta only after pilot acceptance.

## Build locally on x86-64 Linux with KVM

```sh
nix flake check --option max-jobs 1 --print-build-logs
nix build .#qcow2 .#release-manifest
```

No binary cache is required. Measure clean installation time before introducing an additional cache and signing credentials. See docs/INSTALL.md and docs/RECOVERY.md for the operator's update path.
