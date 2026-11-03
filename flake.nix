{
  description = "Airglow: native AirPlay 2, PulseAudio and LedFX services for NixOS";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { self, nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      version = (builtins.fromJSON (builtins.readFile ./web/release.json)).version;
      revision = self.rev or self.dirtyRev or "development";
      airglowModule = { lib, ... }: {
        imports = [ ./nix/module.nix ];
        services.airglow.releaseRevision = lib.mkDefault revision;
      };
      applianceModule = { pkgs, ... }: {
        imports = [ airglowModule ./nix/appliance.nix ];
        systemd.tmpfiles.rules = [
          "d /etc/nixos 0700 root root -"
          "C /etc/nixos/flake.nix 0600 root root - ${pkgs.writeText "airglow-host-flake.nix" ''
            {
              inputs.nixpkgs.url = "github:NixOS/nixpkgs/${nixpkgs.rev}";
              inputs.airglow.url = "github:RoyalPineapple/airglow/v${version}";
              inputs.airglow.inputs.nixpkgs.follows = "nixpkgs";
              outputs = { nixpkgs, airglow, ... }: {
                nixosConfigurations.airglow = nixpkgs.lib.nixosSystem {
                  system = "x86_64-linux";
                  modules = [ airglow.nixosModules.appliance ./configuration.nix ];
                };
              };
            }
          ''}"
          "C /etc/nixos/configuration.nix 0600 root root - ${pkgs.writeText "airglow-host.nix" "{ ... }: {}\n"}"
        ];
      };
      imageSystem = nixpkgs.lib.nixosSystem { inherit system; modules = [ applianceModule ]; };
      manifest = pkgs.writeText "release.json" (builtins.toJSON {
        inherit version revision system;
        configurationVersion = 1;
        nixpkgs = nixpkgs.rev;
        components = builtins.fromJSON imageSystem.config.systemd.services.airglow.environment.AIRGLOW_VERSIONS;
        compatibility = { nixos = "26.05"; airplay = "2"; network = "bridged wired LAN"; firmware = "UEFI"; };
      });
      image = import (nixpkgs + "/nixos/lib/make-disk-image.nix") {
        inherit pkgs;
        lib = nixpkgs.lib;
        config = imageSystem.config;
        name = "airglow-${version}-${system}";
        baseName = "airglow-${version}-${system}";
        format = "qcow2-compressed";
        partitionTableType = "efi";
        bootSize = "512M";
        diskSize = 16384;
        copyChannel = false;
      };
    in {
      nixosModules = { airglow = airglowModule; default = airglowModule; appliance = applianceModule; };
      packages.${system} = {
        qcow2 = image;
        release-manifest = manifest;
      };
      checks.${system} = {
        integration = import ./nix/integration-test.nix { inherit pkgs; };
        image = import ./nix/image-test.nix { inherit pkgs image manifest version; };
      };
    };
}
