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
        'password_set': bool(data.get('password')), 'revision': settings_store.revision(data)}


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
    # Libconfig numeric settings cannot use Shairport's string substitution.
    base = Path(os.environ.get('SHAIRPORT_CONF', '/etc/shairport-sync.conf')).read_text()
    configured = base
    for key, value in (('active_state_timeout', f"{data['idle_timeout']}.0"),
                       ('volume_control_type', '0' if data['fixed_volume'] else '3')):
        configured, count = re.subn(rf'(\b{key}\s*=\s*)[0-9]+(?:\.[0-9]*)?(\s*;)',
                                    lambda match: f"{match[1]}{value}{match[2]}", configured)
        if count != 1:
            raise ValueError(f'Expected one {key} in the receiver configuration.')
    runtime_config = runtime / 'receiver.conf'
    runtime_config.write_text(configured)
    runtime_config.chmod(0o640)
    # Atomic replacement also recovers runtime markers left by a root-run diagnostic.
    for name, value in (('receiver', str(uuid.uuid4())),
                        ('receiver.applied', json.dumps({'fingerprint': settings_store._digest(data), 'pid': os.getpid()}))):
        with tempfile.NamedTemporaryFile(mode='w', dir=runtime, delete=False) as output:
            marker = Path(output.name)
            try:
                output.write(value)
                output.flush()
                marker.chmod(0o640)
                marker.replace(runtime / name)
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
