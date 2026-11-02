"""Validated receiver overrides; Nix owns the service and its base configuration."""
import json
import os
import re
from pathlib import Path
import tempfile
import uuid


def settings_path():
    return Path(os.environ.get('AIRGLOW_CONFIG_DIR', '/var/lib/airglow')) / 'receiver.json'


def load():
    try:
        data = json.loads(settings_path().read_text())
        data.setdefault('idle_timeout', 10)
        return data
    except FileNotFoundError:
        return {'name': '', 'mode': 'airplay2', 'fixed_volume': True, 'password': '', 'idle_timeout': 10}


def validate(data, previous):
    if not isinstance(data, dict):
        raise ValueError('Receiver settings must be an object.')
    name = data.get('name', previous.get('name', ''))
    mode = data.get('mode', previous.get('mode', 'airplay2'))
    volume = data.get('fixed_volume', previous.get('fixed_volume', True))
    idle_timeout = data.get('idle_timeout', previous.get('idle_timeout', 10))
    if type(idle_timeout) is not int or not 1 <= idle_timeout <= 300:
        raise ValueError('Use an idle delay from 1 to 300 whole seconds.')
    supplied_password = data.get('password', '')
    if not isinstance(supplied_password, str) or type(data.get('clear_password', False)) is not bool:
        raise ValueError('Use text for the password and a boolean for password removal.')
    password = supplied_password or previous.get('password', '')
    if data.get('clear_password') is True:
        password = ''
    if not isinstance(name, str) or len(name.strip()) > 50 or any(c in name for c in ('"', '\\')) or any(ord(c) < 32 for c in name):
        raise ValueError('Use a receiver name of up to 50 characters without quotes, backslashes, or control characters.')
    if mode != 'airplay2':
        raise ValueError('Airglow supports AirPlay 2 only.')
    if type(volume) is not bool:
        raise ValueError('Fixed audio level must be a boolean.')
    if not isinstance(password, str) or len(password) > 128 or any(ord(c) < 32 for c in password):
        raise ValueError('Use an AirPlay password of up to 128 characters without control characters.')
    return {'name': name.strip(), 'mode': mode, 'fixed_volume': volume, 'password': password, 'idle_timeout': idle_timeout}


def public(data):
    default = os.environ.get('AIRGLOW_DEFAULT_RECEIVER_NAME', os.uname().nodename)
    return {key: data[key] for key in ('name', 'mode', 'fixed_volume')} | {
        'effective_name': data.get('name') or default, 'default_name': default,
        'idle_timeout': data.get('idle_timeout', 10),
        'password_set': bool(data.get('password'))}


def request_restart():
    # Keep the watched inode stable; settings themselves are replaced atomically.
    path = settings_path().parent / 'receiver.restart'
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640), 'w') as output:
        output.write(uuid.uuid4().hex)


def save(data):
    previous = load()
    updated = validate(data, previous)
    if updated == previous:
        return public(updated) | {'restart_requested': False}
    path = settings_path()
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(updated, output)
            output.flush()
            os.fsync(output.fileno())
            os.chmod(temporary, 0o640)
            temporary.replace(path)
            request_restart()
        finally:
            temporary.unlink(missing_ok=True)
    return public(updated) | {'restart_requested': True}


def run(binary):
    data = validate(load(), {})
    # These values enter libconfig strings through Shairport's native substitution.
    os.environ['AIRGLOW_AIRPLAY_PASSWORD'] = json.dumps(data['password'], ensure_ascii=False)[1:-1]
    os.environ['AIRGLOW_FIXED_VOLUME'] = 'yes' if data['fixed_volume'] else 'no'
    runtime = Path(os.environ['AIRGLOW_RUNTIME'])
    # Libconfig requires a numeric timeout; environment substitution only handles strings.
    base = Path(os.environ.get('SHAIRPORT_CONF', '/etc/shairport-sync.conf')).read_text()
    configured, count = re.subn(r'(\bactive_state_timeout\s*=\s*)[0-9]+(?:\.[0-9]*)?(\s*;)',
                                lambda match: f"{match[1]}{data['idle_timeout']}.0{match[2]}", base)
    if count != 1:
        raise ValueError('Expected one active_state_timeout in the receiver configuration.')
    runtime_config = runtime / 'receiver.conf'
    runtime_config.write_text(configured)
    runtime_config.chmod(0o640)
    # Replace rather than truncate a marker recovered by the web/worker service account.
    with tempfile.NamedTemporaryFile(mode='w', dir=runtime, delete=False) as output:
        marker = Path(output.name)
        try:
            output.write(str(uuid.uuid4()))
            output.flush()
            marker.chmod(0o640)
            marker.replace(runtime / 'receiver')
        finally:
            marker.unlink(missing_ok=True)
    for name in ('event.json', 'action.json'):
        (runtime / name).unlink(missing_ok=True)
    args = [binary, '--service-type=airplay2', '--configfile=' + str(runtime_config)]
    if data['name']:
        args.append('--name=' + data['name'])
    os.execv(binary, args)


if __name__ == '__main__':
    import sys
    run(sys.argv[1])
