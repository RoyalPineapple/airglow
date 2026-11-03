{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    airglow.url = "github:RoyalPineapple/airglow/v0.1.0-beta.1";
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
          nix.settings.experimental-features = [ "nix-command" "flakes" ];
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
