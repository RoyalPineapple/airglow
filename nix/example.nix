{ ... }:
{
  imports = [ ./module.nix ];
  networking.hostName = "airglow";
  services.airglow = {
    enable = true;
    # Documentation-only address. Replace with an address already assigned to your host.
    address = "192.0.2.20";
    interface = "enp1s0";
    # Set ledfxBrowserUrl if browsers reach LedFX through a proxy or tunnel.
  };
}
