{ lib, modulesPath, ... }:
{
  imports = [ (modulesPath + "/profiles/qemu-guest.nix") ];
  networking.hostName = lib.mkDefault "airglow";
  networking.usePredictableInterfaceNames = false;
  networking.useDHCP = false;
  networking.interfaces.eth0.useDHCP = true;
  services.airglow = {
    enable = true;
    # The appliance intentionally listens on its DHCP LAN. The module's host defaults stay unchanged.
    address = "0.0.0.0";
    interface = "eth0";
  };
  services.avahi = { enable = true; publish.enable = true; publish.addresses = true; };
  services.qemuGuest.enable = true;
  users.users.root.initialHashedPassword = lib.mkDefault "!";
  services.journald.extraConfig = "SystemMaxUse=128M\nRuntimeMaxUse=32M";
  services.openssh.enable = lib.mkDefault false;
  # Hypervisor-console access only; no shared password or SSH credentials are shipped.
  services.getty.autologinUser = "root";
  boot.kernelParams = [ "console=ttyS0" ];
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = false;
  boot.growPartition = true;
  fileSystems."/" = { device = "/dev/disk/by-label/nixos"; fsType = "ext4"; autoResize = true; };
  fileSystems."/boot" = { device = "/dev/disk/by-label/ESP"; fsType = "vfat"; };
  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  system.stateVersion = "26.05";
}
