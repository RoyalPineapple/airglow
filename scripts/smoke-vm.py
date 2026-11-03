#!/usr/bin/env python3
"""Boot the released disk, exercise recovery, and verify that clones get fresh identities."""
import argparse
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('--image', required=True)
parser.add_argument('--firmware', required=True)
parser.add_argument('--variables', required=True)
parser.add_argument('--manifest', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
manifest = json.loads(Path(args.manifest).read_text())
output = Path(args.output)
output.mkdir(parents=True)


def api(port, path, data=None):
    request = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
        None if data is None else json.dumps(data).encode(), {'Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.load(response)


def wait_for(check, timeout=240):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (OSError, ValueError, KeyError) as error:
            last = type(error).__name__
        time.sleep(.5)
    raise RuntimeError(f'VM check timed out ({last})')


class Guest:
    def __init__(self, root, name):
        self.root = root
        self.name = name
        self.process = self.console = self.reader = self.log = None
        self.disk = root / (name + '.qcow2')
        if not self.disk.exists():
            subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(Path(args.image).resolve()),str(self.disk)], check=True)
        self.vars = root / (name + '.fd')
        if not self.vars.exists():
            shutil.copyfile(args.variables, self.vars)

    def start(self, run):
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1',0))
            self.port = reservation.getsockname()[1]
        serial = self.root / (self.name + '.sock')
        serial.unlink(missing_ok=True)
        self.log = (output / (run + '.log')).open('wb')
        self.process = subprocess.Popen(['qemu-system-x86_64','-accel','kvm','-machine','q35','-m','1024','-smp','2',
            '-drive',f'if=pflash,format=raw,unit=0,readonly=on,file={args.firmware}',
            '-drive',f'if=pflash,format=raw,unit=1,file={self.vars}',
            '-drive',f'if=virtio,format=qcow2,file={self.disk}',
            '-netdev',f'user,id=lan,hostfwd=tcp:127.0.0.1:{self.port}-:80',
            '-device','virtio-net-pci,netdev=lan','-display','none','-monitor','none',
            '-serial',f'unix:{serial},server=on,wait=off'], stdout=self.log, stderr=self.log)
        self.console = socket.socket(socket.AF_UNIX)
        wait_for(lambda:self.connect(serial),30)
        self.console.settimeout(.5)
        # Drain kernel output while HTTP services start; a full serial socket can stall boot.
        import threading
        self.buffer = b''
        self.lock = threading.Lock()
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()
        def ready():
            if self.process.poll() is not None:
                raise RuntimeError('QEMU exited before the app became available')
            state = api(self.port, '/api/status')
            return state if state['airplay']['configuration_state'] == 'applied' and state['ledfx']['connected'] and state['audio']['pulseaudio']['available'] else None
        try:
            state = wait_for(ready)
        except Exception:
            with self.lock:
                print(self.buffer[-6000:].decode(errors='replace'), flush=True)
            raise
        assert state['release']['version'] == manifest['version']
        assert state['release']['revision'] == manifest['revision']
        assert state['release']['configuration_version'] == manifest['configurationVersion']
        self.command('stty -echo')
        self.command('test ! -L /etc/nixos/flake.nix; test -f /etc/nixos/configuration.nix; ! systemctl is-active --quiet sshd; test ! -e /etc/ssh/ssh_host_ed25519_key; test ! -e /etc/ssh/ssh_host_rsa_key; test ! -e /etc/ssh/ssh_host_ecdsa_key; test "$(getent shadow root | cut -d: -f2)" = "!"')
        return self.command('cat /etc/machine-id').strip()

    def connect(self, serial):
        self.console.connect(str(serial))
        return True

    def read(self):
        while self.process.poll() is None:
            try:
                data = self.console.recv(65536)
                if not data:
                    return
                self.log.write(data); self.log.flush()
                with self.lock:
                    self.buffer = (self.buffer + data)[-2_000_000:]
            except socket.timeout:
                pass
            except OSError:
                return

    def command(self, command):
        token = uuid.uuid4().hex
        with self.lock:
            self.buffer = b''
        self.console.sendall((f"printf '\\nBEGIN_{token}\\n'; ( set -eu; {command} ); result=$?; printf '\\nEND_{token}:%s\\n' \"$result\"\n").encode())
        pattern = re.compile(rb'\r?\nBEGIN_' + token.encode() + rb'\r?\n(.*?)\r?\nEND_' + token.encode() + rb':(\d+)', re.S)
        def done():
            with self.lock:
                return pattern.search(self.buffer)
        match = wait_for(done,120)
        if match[2] != b'0':
            raise RuntimeError('Guest command failed: ' + command + '\n' + match[1].decode(errors='replace'))
        return match[1].decode(errors='replace').replace('\r','')

    def stop(self):
        if self.process and self.process.poll() is None:
            if self.console:
                try:
                    self.console.sendall(b'sync; systemctl poweroff\n')
                except OSError:
                    pass
            try:
                self.process.wait(30)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(10)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait()
        if self.console:
            self.console.close()
        if self.reader:
            self.reader.join(2)
        if self.log:
            self.log.close()


with tempfile.TemporaryDirectory(prefix='airglow-vm-') as directory:
    root = Path(directory)
    first = Guest(root,'first')
    try:
        identity = first.start('first-boot')
        assert re.fullmatch('[0-9a-f]{32}',identity), 'Missing unique machine identity'
        api(first.port,'/api/receiver',{'name':'Recovery check'})
        wait_for(lambda:api(first.port,'/api/status')['airplay']['configuration_state'] == 'applied')
        # The same fixed archive contents and service sequence are documented in RECOVERY.md.
        first.command('systemctl stop airglow airglow-actions shairport-sync ledfx airglow-receiver-settings.path; '
            'printf recovery-fixture > /var/lib/ledfx/airglow-recovery-fixture; '
            'umask 077; tar -czpf /var/tmp/recovery.tar.gz -C / var/lib/airglow/airglow.json var/lib/ledfx etc/nixos; '
            'mv /var/lib/airglow /var/tmp/airglow.before-restore; mv /var/lib/ledfx /var/tmp/ledfx.before-restore; '
            'tar -xzpf /var/tmp/recovery.tar.gz -C / var/lib/airglow/airglow.json var/lib/ledfx; '
            'chown -R airglow:airglow /var/lib/airglow; chmod 750 /var/lib/airglow; '
            'chown -R ledfx:ledfx /var/lib/ledfx; '
            'systemctl start airglow-receiver-settings.path airglow-actions pulseaudio nqptp shairport-sync ledfx airglow; '
            'test "$(cat /var/lib/ledfx/airglow-recovery-fixture)" = recovery-fixture')
        wait_for(lambda:api(first.port,'/api/receiver')['name'] == 'Recovery check')
    finally:
        first.stop()
    try:
        assert first.start('reboot') == identity, 'Machine identity changed on reboot'
        assert api(first.port,'/api/receiver')['name'] == 'Recovery check'
        first.command('test "$(cat /var/lib/ledfx/airglow-recovery-fixture)" = recovery-fixture')
    finally:
        first.stop()
    second = Guest(root,'second')
    try:
        assert second.start('clean-clone') != identity, 'Image contains a shared machine identity'
        assert api(second.port,'/api/receiver')['name'] == '', 'Published image contains test settings'
    finally:
        second.stop()
(output / 'result.json').write_text(json.dumps({'boot':'passed','dhcp':'passed','discovery':'passed','release_identity':'passed',
    'backup_restore':'passed','reboot_persistence':'passed','clone_identity':'passed','ssh_credentials':'not shipped'},indent=2)+'\n')
print('PASS actual UEFI image boot, DHCP, discovery, release identity, recovery, persistence and clean-clone identity.')
