{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    # This migration is currently on a draft branch. Use a release tag when available.
    airglow.url = "github:RoyalPineapple/airglow/nix-migration-frontend";
    airglow.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { nixpkgs, airglow, ... }: {
    nixosConfigurations.airglow = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        # Your existing host configuration retains networking, disks, SSH and boot settings.
        ./configuration.nix
        airglow.nixosModules.default
        {
          services.airglow = {
            enable = true;
            # Replace with an address already assigned to your host and its interface.
            address = "192.0.2.20";
            interface = "enp1s0";
          };
        }
      ];
    };
  };
}
