"""Validated receiver overrides; Nix owns the service and its base configuration."""
import json
import os
import re
from pathlib import Path
import tempfile
import uuid


from settings_store import validate_receiver as validate
import settings_store


def settings_path():
    return settings_store.path()


def load():
    return settings_store.read()['receiver']


def public(data):
    default = os.environ.get('AIRGLOW_DEFAULT_RECEIVER_NAME', os.uname().nodename)
    return {key: data[key] for key in ('name', 'mode', 'fixed_volume')} | {
        'effective_name': data.get('name') or default, 'default_name': default,
        'idle_timeout': data.get('idle_timeout', 10),
        'password_set': bool(data.get('password'))}


def request_restart():
    settings_store.request_restart()


def save(data):
    document, requested = settings_store.update_receiver(data)
    return public(document['receiver']) | {'restart_requested': requested}


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
