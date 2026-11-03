{ pkgs ? import <nixpkgs> {} }:
pkgs.testers.runNixOSTest {
  name = "airglow-native";
  nodes.machine = { lib, ... }: {
    imports = [ ./module.nix ];
    services.airglow = {
      enable = true;
      address = "192.0.2.20";
      interface = "eth1";
    };
    networking.hostName = "airglow-test";
    networking.useDHCP = false;
    networking.interfaces.eth1.ipv4.addresses = lib.mkForce [{ address = "192.0.2.20"; prefixLength = 24; }];
    virtualisation.memorySize = 1024;
    virtualisation.cores = 2;
    system.stateVersion = "26.05";
    specialisation.rollback-candidate.configuration.environment.etc."airglow-rollback-test".text = "candidate";
  };
  testScript = ''
    import json
    import shlex
    import time

    start_all()
    for unit in ("airglow", "airglow-actions", "pulseaudio", "nqptp", "shairport-sync", "ledfx"):
        machine.wait_for_unit(unit + ".service")
    machine.wait_until_succeeds("curl --fail --silent http://192.0.2.20/healthz")

    def api(path, data=None):
        command = "curl --fail --silent http://192.0.2.20" + path
        if data is not None:
            command += " -H 'Content-Type: application/json' --data " + shlex.quote(json.dumps(data))
        return json.loads(machine.succeed(command))

    # These are real receiver restarts through the systemd path, with both mDNS records checked.
    for name in ("Studio", "Kitchen", "Final"):
        api("/api/receiver", {"name":name, "idle_timeout":12})
        machine.wait_until_succeeds("avahi-browse -rpt _airplay._tcp | grep ';" + name + ";_airplay._tcp;'")
        machine.wait_until_succeeds("avahi-browse -rpt _raop._tcp | grep '" + name + ";_raop._tcp;'")
        print(machine.succeed("curl --fail --silent http://192.0.2.20/api/status"))
        machine.wait_until_succeeds("curl --fail --silent http://192.0.2.20/api/status | grep '\"configuration_state\":\"applied\"'", timeout=60)

    # Settings reads and disabling actions remain independent of a stopped LedFX service.
    machine.succeed("systemctl stop ledfx")
    api("/api/config?catalog=0")
    api("/api/config", {"start_enabled":False, "start_hook":{"virtuals":[{"id":"missing-output"}]}})
    before = api("/api/settings/export")

    # An event created while the worker is down is processed after restart, once only.
    machine.succeed("systemctl stop airglow-actions")
    machine.succeed("printf '123' > /run/airglow/worker.ready")
    status = machine.succeed("curl --silent -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' --data '{\"hook\":\"end\",\"settings\":{\"virtuals\":[{\"id\":\"missing-output\"}]}}' http://192.0.2.20/api/actions/test")
    assert status == "503", status
    session = machine.succeed("cat /run/airglow/receiver").strip()
    event = {"session":session, "id":"downtime", "action":"stop"}
    machine.succeed("printf %s " + shlex.quote(json.dumps(event)) + " > /run/airglow/event.json; chown airglow:airglow /run/airglow/event.json")
    machine.succeed("systemctl start airglow-actions")
    machine.wait_until_succeeds("grep downtime /run/airglow/action.json", timeout=30)
    receipt = machine.succeed("cat /run/airglow/action.json")
    machine.succeed("systemctl restart airglow-actions")
    time.sleep(1)
    assert machine.succeed("cat /run/airglow/action.json") == receipt
    assert api("/api/settings/export") == before
    machine.succeed("systemctl start ledfx")
    # Exercise a real generation change and rollback; application data is independent.
    base_system = machine.succeed("readlink -f /run/current-system").strip()
    candidate = base_system + "/specialisation/rollback-candidate"
    machine.succeed("nix-env -p /nix/var/nix/profiles/system --set " + shlex.quote(base_system))
    machine.succeed("nix-env -p /nix/var/nix/profiles/system --set " + shlex.quote(candidate))
    machine.succeed(candidate + "/bin/switch-to-configuration switch")
    machine.succeed("test $(cat /etc/airglow-rollback-test) = candidate")
    machine.succeed("nixos-rebuild switch --rollback --no-reexec")
    machine.succeed("test ! -e /etc/airglow-rollback-test")
    machine.wait_for_unit("airglow.service")
    assert api("/api/settings/export") == before

  '';
}
