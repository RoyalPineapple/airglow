"""Validated receiver overrides; Nix owns the service and its base configuration."""
import json
import os
from pathlib import Path
import tempfile
import uuid


def settings_path():
    return Path(os.environ.get('AIRGLOW_CONFIG_DIR', '/var/lib/airglow')) / 'receiver.json'


def load():
    try:
        return json.loads(settings_path().read_text())
    except FileNotFoundError:
        return {'name': '', 'mode': 'airplay2', 'fixed_volume': True, 'password': ''}


def validate(data, previous):
    if not isinstance(data, dict):
        raise ValueError('Receiver settings must be an object.')
    name = data.get('name', previous.get('name', ''))
    mode = data.get('mode', previous.get('mode', 'airplay2'))
    volume = data.get('fixed_volume', previous.get('fixed_volume', True))
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
    return {'name': name.strip(), 'mode': mode, 'fixed_volume': volume, 'password': password}


def public(data):
    default = os.environ.get('AIRGLOW_DEFAULT_RECEIVER_NAME', os.uname().nodename)
    return {key: data[key] for key in ('name', 'mode', 'fixed_volume')} | {
        'effective_name': data.get('name') or default, 'default_name': default,
        'password_set': bool(data.get('password'))}


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
        finally:
            temporary.unlink(missing_ok=True)
    return public(updated) | {'restart_requested': True}


def run(binary):
    data = validate(load(), {})
    # These values enter libconfig strings through Shairport's native substitution.
    os.environ['AIRGLOW_AIRPLAY_PASSWORD'] = json.dumps(data['password'], ensure_ascii=False)[1:-1]
    os.environ['AIRGLOW_FIXED_VOLUME'] = 'yes' if data['fixed_volume'] else 'no'
    runtime = Path(os.environ['AIRGLOW_RUNTIME'])
    (runtime / 'receiver').write_text(str(uuid.uuid4()))
    for name in ('event.json', 'action.json'):
        (runtime / name).unlink(missing_ok=True)
    args = [binary, '--service-type=airplay2']
    if data['name']:
        args.append('--name=' + data['name'])
    os.execv(binary, args)


if __name__ == '__main__':
    import sys
    run(sys.argv[1])
