{
  description = "Airglow: native AirPlay 2, PulseAudio and LedFX services for NixOS";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { nixpkgs, ... }: {
    nixosModules = {
      airglow = import ./nix/module.nix;
      default = import ./nix/module.nix;
    };

    # The beta supports x86-64 Linux; this check builds and boots the complete stack.
    checks.x86_64-linux.integration = import ./nix/integration-test.nix {
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
    };
  };
}
