{ config, lib, pkgs, ... }:
let
  cfg = config.services.airglow;
  # This revision supplies LedFX 2.2.1 and its matching Python dependencies.
  # Pin the collection so updates happen only when we change this revision and hash.
  latestPackages = import (builtins.fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/0bb2eedc20e4739f29e8045034f2828ad7054f8f.tar.gz";
    sha256 = "008j4dj5yrzww91qvp1lp2c9d1lkwc6i2dpainf5nkdkr3rwj8vy";
  }) { system = pkgs.stdenv.hostPlatform.system; };
  ledfx = latestPackages.ledfx;
  audioPython = latestPackages.python3.withPackages (p: [ p.sounddevice ]);
  webPython = pkgs.python3.withPackages (p: [ p.flask p.pyyaml p.gunicorn ]);
  publishSession = pkgs.writeShellScript "airglow-session" (builtins.readFile ../scripts/publish-session.sh);
  # UI asset changes must not restart the receiver or interrupt an action in progress.
  receiverSource = pkgs.runCommand "airglow-receiver" {} ''
    mkdir -p "$out"
    cp ${../web/receiver.py} "$out/receiver.py"
    cp ${../web/settings_store.py} "$out/settings_store.py"
  '';
  settingsSource = pkgs.writeText "airglow-settings.py" (builtins.readFile ../web/settings_store.py);
  workerSource = pkgs.writeText "airglow-actions.py" (builtins.readFile ../web/session_worker.py);
  # Copy only runtime source into the immutable Nix store, including local assets.
  webSource = builtins.path {
    path = ../web;
    name = "airglow-web";
    filter = path: type: !(builtins.elem (baseNameOf path) [ "__pycache__" "design" ]);
  };
  # Use the latest stable receiver release verified on 2026-11-02.
  # The NixOS channel has an older version, so override its package recipe.
  # "override" changes build options; "overrideAttrs" changes the recipe itself.
  receiver = (pkgs.shairport-sync-airplay2.override {
    # This headless receiver does not need D-Bus control or desktop media controls.
    enableDbus = false;
    enableMpris = false;
  }).overrideAttrs {
    # This is the package label; the source tag below selects the actual code.
    version = "5.6.2";
    # shortcut: The channel edits D-Bus files at old paths; 5.6.2 moved those files.
    # Clear that build step because D-Bus is disabled. Remove this workaround
    # when the channel provides this release or a newer stable release.
    postPatch = "";
    src = pkgs.fetchFromGitHub {
      owner = "mikebrady";
      repo = "shairport-sync";
      # Pin a stable release so rebuilds cannot silently download different code.
      tag = "5.6.2";
      # Nix rejects downloaded source that does not match this content hash.
      # When updating, change the version, tag, and hash together.
      hash = "sha256-JiiZLgeYFoZ+Xq6tn1+KqW6Ewo+j+5JmxJ0Wm3dXqoE=";
    };
  };
  # NQPTP supplies the clock information that AirPlay 2 needs for synchronization.
  # Pin the latest stable release verified on 2026-11-02, as with the receiver.
  timing = pkgs.nqptp.overrideAttrs {
    version = "1.2.9";
    src = pkgs.fetchFromGitHub {
      owner = "mikebrady";
      repo = "nqptp";
      tag = "1.2.9";
      hash = "sha256-qqDqUFtqJjODxSX7eEE6DObXIE6X0LjxnneVlg6uJaw=";
    };
  };
in
{
  options.services.airglow = {
    enable = lib.mkEnableOption "Airglow AirPlay 2 audio bridge and web interface";
    address = lib.mkOption {
      type = lib.types.str;
      description = "Existing host IPv4 address for Airglow and LedFX listeners.";
    };
    interface = lib.mkOption {
      type = lib.types.str;
      description = "LAN interface on which to allow AirPlay and lighting reply traffic.";
    };
    ledfxBrowserUrl = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Browser-facing LedFX URL, or null to use the configured host address.";
    };
  };
  config = lib.mkIf cfg.enable {
  services.pulseaudio = {
    enable = true;
    systemWide = true;
    # Create a local audio bridge without a physical speaker or a network listener.
    # Shairport writes to "airglow"; LedFX will read from "airglow.monitor".
    configFile = pkgs.writeText "airglow-pulse.pa" ''
      load-module module-native-protocol-unix auth-group=pulse-access
      load-module module-null-sink sink_name=airglow rate=44100 channels=2 sink_properties=device.description=Airglow
      set-default-sink airglow
      set-default-source airglow.monitor
    '';
  };
  # A headless VM does not activate sound.target through an audio device.
  systemd.services.pulseaudio.wantedBy = [ "multi-user.target" ];

  users.groups.airglow = {};
  users.users.airglow = {
    isSystemUser = true;
    group = "airglow";
    extraGroups = [ "pulse-access" ];
  };
  systemd.services.airglow = {
    description = "Airglow native status interface";
    wantedBy = [ "multi-user.target" ];
    after = [ "network.target" "pulseaudio.service" "shairport-sync.service" "ledfx.service" ];
    # Keep the status page available even when an audio service fails.
    path = [ pkgs.systemd pkgs.pulseaudio pkgs.avahi pkgs.curl ];
    environment = {
      AIRGLOW_ADDRESS = cfg.address;
      LEDFX_API_URL = "http://${cfg.address}:8888";
      LEDFX_BROWSER_URL = if cfg.ledfxBrowserUrl == null then "http://${cfg.address}:8888" else cfg.ledfxBrowserUrl;
      PULSE_SERVER = "unix:/run/pulse/native";
      PYTHONDONTWRITEBYTECODE = "1";
      AIRGLOW_CONFIG_DIR = "/var/lib/airglow";
      AIRGLOW_RUNTIME = "/run/airglow";
      SHAIRPORT_CONF = "/etc/shairport-sync.conf";
      AIRGLOW_DEFAULT_RECEIVER_NAME = config.services.shairport-sync.settings.general.name;
      LEDFX_HOST = cfg.address;
      LEDFX_PORT = "8888";
      AIRGLOW_VERSIONS = builtins.toJSON {
        shairport = receiver.version;
        nqptp = timing.version;
        pulseaudio = pkgs.pulseaudio.version;
        ledfx = ledfx.version;
      };
    };
    serviceConfig = {
      User = "airglow";
      Group = "airglow";
      StateDirectory = "airglow";
      StateDirectoryMode = "0750";
      WorkingDirectory = webSource;
      ExecStart = "${webPython}/bin/gunicorn --bind ${cfg.address}:80 --workers 1 --threads 4 native:app";
      AmbientCapabilities = [ "CAP_NET_BIND_SERVICE" ];
      NoNewPrivileges = true;
      Restart = "on-failure";
      RestartSec = 5;
    };
  };

  # A fixed systemd action applies validated settings. The web process receives no sudo access.
  systemd.paths.airglow-receiver-settings = {
    wantedBy = [ "multi-user.target" ];
    # Atomic JSON replacement invalidates a file watch; signal through a stable file.
    pathConfig.PathChanged = "/var/lib/airglow/receiver.restart";
    pathConfig.Unit = "airglow-receiver-apply.service";
  };
  systemd.services.airglow-receiver-apply = {
    serviceConfig.Type = "oneshot";
    serviceConfig.ExecStart = "${pkgs.systemd}/bin/systemctl restart shairport-sync.service";
  };
  systemd.services.airglow-actions = {
    description = "Airglow session action worker";
    wantedBy = [ "multi-user.target" ];
    after = [ "network.target" ];
    environment = {
      AIRGLOW_RUNTIME = "/run/airglow";
      AIRGLOW_CONFIG_DIR = "/var/lib/airglow";
      AIRGLOW_HOOKS_FILE = "/var/lib/airglow/airglow.json";
      LEDFX_HOST = cfg.address;
      LEDFX_PORT = "8888";
    };
    serviceConfig = {
      User = "airglow";
      Group = "airglow";
      StateDirectory = "airglow";
      StateDirectoryMode = "0750";
      ExecStartPre = "${webPython}/bin/python ${settingsSource} --migrate";
      RuntimeDirectory = "airglow";
      RuntimeDirectoryMode = "2770";
      # Nix updates stop/start this worker while the receiver keeps using the directory.
      RuntimeDirectoryPreserve = true;
      ExecStart = "${webPython}/bin/python ${workerSource}";
      Restart = "on-failure";
      NoNewPrivileges = true;
    };
  };

  # PortAudio reaches PulseAudio through ALSA. Give the bridge a stable device name.
  environment.etc."asound.conf".text = ''
    pcm.airglow {
      type pulse
      hint.description "Airglow audio bridge"
    }
    pcm.!default { type pulse }
    ctl.!default { type pulse }
  '';
  users.groups.ledfx = {};
  users.users.ledfx = {
    isSystemUser = true;
    group = "ledfx";
    extraGroups = [ "pulse-access" ];
    home = "/var/lib/ledfx";
  };
  systemd.services.ledfx = {
    description = "LedFX audio analysis and lighting service";
    wantedBy = [ "multi-user.target" ];
    wants = [ "network-online.target" ];
    after = [ "network-online.target" "pulseaudio.service" ];
    requires = [ "pulseaudio.service" ];
    environment = {
      HOME = "/var/lib/ledfx";
      PULSE_SERVER = "unix:/run/pulse/native";
      PULSE_SOURCE = "airglow.monitor";
      ALSA_PLUGIN_DIR = "${latestPackages.alsa-plugins}/lib/alsa-lib";
    };
    # Seed only a new installation. LedFX owns this file after the first start.
    # Resolve the input by name rather than assuming that its index is zero.
    preStart = ''
      if [ ! -e /var/lib/ledfx/config.json ]; then
        ${audioPython}/bin/python - <<'PY'
      import json
      import sounddevice as sd
      devices = sd.query_devices()
      matches = [i for i, d in enumerate(devices)
                 if d['name'] == 'airglow' and d['max_input_channels'] > 0
                 and sd.query_hostapis(d['hostapi'])['name'] == 'ALSA']
      if len(matches) != 1:
          raise RuntimeError(f"Expected one Airglow audio input; found {matches}")
      with open('/var/lib/ledfx/config.json', 'x') as output:
          json.dump({"configuration_version": "2.3.6", "audio": {
              "audio_device": matches[0], "audio_device_name": "ALSA: airglow"
          }}, output)
      PY
      fi
    '';
    serviceConfig = {
      User = "ledfx";
      Group = "ledfx";
      StateDirectory = "ledfx";
      # Bind only to the configured host address. LedFX keeps its own configuration UI.
      ExecStart = "${ledfx}/bin/ledfx --config /var/lib/ledfx --host ${cfg.address} --port 8888 --no-tray --offline";
      Restart = "on-failure";
      RestartSec = 5;
      UMask = "0077";
    };
  };

  services.shairport-sync = {
    enable = true;
    package = receiver;
    settings = {
      general = {
        # Use the hostname unless another module explicitly sets this AirPlay name.
        # Example override: services.shairport-sync.settings.general.name = "Living Room";
        name = lib.mkDefault config.networking.hostName;
        service_type = "airplay2";
        output_backend = "pulseaudio";
        # Keep the analysis signal at full level regardless of the phone's volume.
        ignore_volume_control = "\${AIRGLOW_FIXED_VOLUME}";
        password = "\${AIRGLOW_AIRPLAY_PASSWORD}";
      };
      pulseaudio = {
        server = "unix:/run/pulse/native";
        sink = "airglow";
      };
      sessioncontrol = {
        run_this_before_entering_active_state = "${publishSession} start";
        run_this_after_exiting_active_state = "${publishSession} stop";
        active_state_timeout = 10.0;
        wait_for_completion = "yes";
      };
      # Verbose Shairport logs can print the configured password.
      diagnostics.log_verbosity = 0;
    };
  };
  # Allow this service account to use the protected local PulseAudio socket.
  users.users.shairport.extraGroups = [ "pulse-access" "airglow" ];
  systemd.services.shairport-sync = {
    # Start the audio bridge and timing service before the receiver.
    after = [ "pulseaudio.service" "nqptp.service" "airglow-actions.service" ];
    wants = [ "airglow-actions.service" ];
    requires = [ "pulseaudio.service" "nqptp.service" ];
    environment = {
      AIRGLOW_RUNTIME = "/run/airglow";
      AIRGLOW_CONFIG_DIR = "/var/lib/airglow";
    };
    serviceConfig.ExecStart = lib.mkForce "${webPython}/bin/python ${receiverSource}/receiver.py ${receiver}/bin/shairport-sync";
  };
  systemd.services.nqptp = {
    description = "AirPlay timing service";
    wants = [ "network-online.target" ];
    after = [ "network-online.target" ];
    before = [ "shairport-sync.service" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      ExecStart = "${timing}/bin/nqptp";
      # Use a temporary service account instead of root. Only low-port access is granted.
      DynamicUser = true;
      LimitRTPRIO = 6;
      AmbientCapabilities = [ "CAP_NET_BIND_SERVICE" ];
      Restart = "on-failure";
    };
  };
  # Avahi announces the receiver so Apple devices can find it on this LAN.
  services.avahi.openFirewall = true;
  # Port 7000 accepts AirPlay connections; UDP 319 and 320 carry clock information.
  networking.firewall.allowedTCPPorts = [ 80 7000 8888 ];
  networking.firewall.allowedUDPPorts = [ 319 320 ];
  # AirPlay 2 allocates audio and event ports from the kernel's ephemeral range.
  networking.firewall.interfaces.${cfg.interface} = {
    # Govee lamps reply to LedFX status requests on this port from a different source port.
    allowedUDPPorts = [ 4002 ];
    allowedTCPPortRanges = [ { from = 32768; to = 60999; } ];
    allowedUDPPortRanges = [ { from = 32768; to = 60999; } ];
  };

  };
}
