"""One versioned, private Airglow configuration; legacy files are migration inputs only."""
import base64
import copy
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
from contextlib import contextmanager

import yaml

REVISION_KEY = os.urandom(32)
VERSION = 1
RECEIVER_DEFAULTS = {'name':'', 'mode':'airplay2', 'fixed_volume':True, 'password':'', 'idle_timeout':10}
HOOK_DEFAULTS = {'enabled':False, 'mode':'toggle', 'all_virtuals':False, 'virtuals':[], 'scenes':[]}


class ConflictError(ValueError):
    pass


# A keyed revision must not expose a reusable password hash through the settings API.
def revision(section):
    return hmac.new(REVISION_KEY, json.dumps(section, sort_keys=True).encode(), hashlib.sha256).hexdigest()


def check_revision(changes, section):
    if not isinstance(changes, dict):
        raise ValueError('Settings must be an object.')
    if 'revision' in changes and changes['revision'] != revision(section):
        raise ConflictError('These settings changed elsewhere. Reload before saving your changes.')


def directory():
    return Path(os.environ.get('AIRGLOW_CONFIG_DIR', '/var/lib/airglow'))


def path():
    return directory() / 'airglow.json'


def validate_receiver(data, previous):
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



def validate_hook(hook):
    """Validate the action shape shared by saved automation and one-off tests."""
    if not isinstance(hook, dict) or type(hook.get('all_virtuals', False)) is not bool:
        raise ValueError('Invalid action settings.')
    mode = hook.get('mode', 'toggle')
    if mode not in ('toggle', 'scene'):
        raise ValueError('Choose an output action or a scene.')
    virtuals, scenes = hook.get('virtuals', []), hook.get('scenes', [])
    if not isinstance(virtuals, list) or not isinstance(scenes, list):
        raise ValueError('Outputs and scenes must be lists.')
    if any(not isinstance(v, dict) or not isinstance(v.get('id'), str) or not v['id']
           or type(v.get('repeats', 1)) is not int or not 0 <= v.get('repeats', 1) <= 10 for v in virtuals):
        raise ValueError('Outputs need an ID and a valid legacy repeat count.')
    if any(not isinstance(sid, str) or not sid for sid in scenes):
        raise ValueError('Scene IDs must be nonempty strings.')
    return {'mode': mode, 'all_virtuals': hook.get('all_virtuals', False),
            'virtuals': virtuals, 'scenes': scenes}



def validate_document(value):
    if not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != VERSION:
        raise ValueError('Choose an Airglow configuration file with version 1.')
    if set(value) - {'version', 'receiver', 'hooks', 'extensions'}:
        raise ValueError('The configuration contains unsupported sections.')
    receiver = value.get('receiver')
    if not isinstance(receiver, dict) or set(receiver) != set(RECEIVER_DEFAULTS):
        raise ValueError('The receiver section must contain all receiver settings.')
    hooks = value.get('hooks')
    if not isinstance(hooks, dict) or set(hooks) != {'start', 'end'}:
        raise ValueError('The configuration must contain start and end actions.')
    result = copy.deepcopy(value)
    result['receiver'] = validate_receiver(receiver, {})
    for key in ('start', 'end'):
        hook = hooks[key]
        if not isinstance(hook, dict) or type(hook.get('enabled')) is not bool or 'all_virtuals' not in hook:
            raise ValueError('Each action needs an enabled flag and an explicit output scope.')
        result['hooks'][key].update(validate_hook(hook))
    if not isinstance(value.get('extensions', {}), dict):
        raise ValueError('Configuration extensions must be an object.')
    result.setdefault('extensions', {})
    try:
        json.dumps(result, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError):
        raise ValueError('Configuration values must be valid JSON.') from None
    return result


def _legacy():
    receiver_file = directory() / 'receiver.json'
    receiver = json.loads(receiver_file.read_text()) if receiver_file.exists() else {}
    receiver = validate_receiver(receiver, {})
    hooks_file = directory() / 'ledfx-hooks.yaml'
    old = (yaml.safe_load(hooks_file.read_text()) or {}) if hooks_file.exists() else {}
    if not isinstance(old, dict) or not isinstance(old.get('hooks', {}), dict):
        raise ValueError('The existing playback configuration is invalid.')
    hooks = {}
    for key in ('start', 'end'):
        previous = old.get('hooks', {}).get(key, {})
        if not isinstance(previous, dict):
            raise ValueError('The existing playback action is invalid.')
        hook = copy.deepcopy(HOOK_DEFAULTS) | previous
        if previous:
            hook['enabled'] = previous.get('enabled', True)
            hook['all_virtuals'] = previous.get('all_virtuals', not previous.get('virtuals', []))
        hooks[key] = hook
    return validate_document({'version': VERSION, 'receiver': receiver, 'hooks': hooks,
                              'extensions': {k:v for k,v in old.items() if k != 'hooks'}})


def read():
    try:
        return validate_document(json.loads(path().read_text())) if path().exists() else _legacy()
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ValueError('Airglow configuration could not be read or validated. Restore a valid backup.') from error


@contextmanager
def locked():
    directory().mkdir(parents=True, exist_ok=True, mode=0o750)
    with os.fdopen(os.open(directory() / '.airglow.lock', os.O_RDWR | os.O_CREAT, 0o640), 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _write(destination, data):
    with tempfile.NamedTemporaryFile(mode='w', dir=directory(), delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')
            output.flush()
            os.fsync(output.fileno())
            temporary.chmod(0o640)
            temporary.replace(destination)
            descriptor = os.open(directory(), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)


def _digest(receiver):
    return hashlib.sha256(json.dumps(receiver, sort_keys=True).encode()).hexdigest()


def _signal_pending(receiver):
    marker = directory() / 'receiver.restart'
    try:
        return marker.read_text() != _digest(receiver)
    except FileNotFoundError:
        return True


def _signal(receiver, force=False):
    marker = directory() / 'receiver.restart'
    if not force and not _signal_pending(receiver):
        return False
    # The stable watched inode records the requested configuration, not proof of application.
    with os.fdopen(os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640), 'w') as output:
        output.write(_digest(receiver))
    return True


def ensure():
    with locked():
        data = read()
        if not path().exists():
            _write(path(), data)
        return data


def update_receiver(changes):
    with locked():
        data = read()
        check_revision(changes, data['receiver'])
        updated = validate_receiver(changes, data['receiver'])
        changed = updated != data['receiver']
        data['receiver'] = updated
        if changed or not path().exists():
            _write(path(), data)
        return data, _signal(updated)


def update_hooks(changes):
    with locked():
        data = read()
        check_revision(changes, data['hooks'])
        for key in ('start', 'end'):
            enabled = changes.get(key + '_enabled', False)
            if type(enabled) is not bool:
                raise ValueError('Action enabled flags must be boolean.')
            data['hooks'][key].update(validate_hook(changes.get(key + '_hook', {})))
            data['hooks'][key]['enabled'] = enabled
            hook = data['hooks'][key]
            targets = hook['scenes'] if hook['mode'] == 'scene' else hook['all_virtuals'] or any(v.get('repeats', 1) > 0 for v in hook['virtuals'])
            if enabled and not targets:
                raise ValueError('Choose an output or scene before enabling an action.')
        data = validate_document(data)
        _write(path(), data)
        return data


def request_restart():
    with locked():
        return _signal(read()['receiver'], force=True)


def restore(value, preview=False):
    incoming = validate_document(value)
    with locked():
        try:
            old = read()
        except ValueError:
            old = None
        changed = old is None or incoming['receiver'] != old['receiver']
        if preview:
            return incoming, changed or _signal_pending(incoming['receiver'])
        replacing = old is None or incoming != old
        if path().exists() and replacing:
            # Abort before replacement if a consistent previous copy cannot be saved.
            try:
                previous = json.loads(path().read_text()) if old is not None else {'invalid_configuration': path().read_text()}
            except UnicodeDecodeError:
                previous = {'invalid_configuration_base64': base64.b64encode(path().read_bytes()).decode('ascii')}
            _write(directory() / 'airglow.previous.json', previous)
        if replacing or not path().exists():
            _write(path(), incoming)
        requested = _signal(incoming['receiver'], force=old is None)
        return incoming, requested


if __name__ == '__main__':
    import sys
    if sys.argv[1:] != ['--migrate']:
        raise SystemExit('Usage: settings_store.py --migrate')
    ensure()
