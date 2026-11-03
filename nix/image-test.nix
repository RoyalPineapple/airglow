{ pkgs, image, manifest, version }:
pkgs.runCommand "airglow-image-smoke" {
  nativeBuildInputs = [ pkgs.python3 pkgs.qemu_kvm ];
  requiredSystemFeatures = [ "kvm" ];
} ''
  python ${../scripts/smoke-vm.py} \
    --image ${image}/airglow-${version}-x86_64-linux.qcow2 \
    --firmware ${pkgs.OVMF.fd.firmware} --variables ${pkgs.OVMF.fd.variables} \
    --manifest ${manifest} --output "$out"
''
