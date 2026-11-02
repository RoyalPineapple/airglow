"""Saved playback actions and LedFX API access for the native interface."""
import hmac
import json
import logging
import os
import subprocess
import tempfile
from urllib.parse import urlsplit

import yaml
from flask import current_app as app, jsonify, request

logger = logging.getLogger(__name__)
LEDFX_HOST = os.environ.get('LEDFX_HOST', 'localhost')
LEDFX_PORT = os.environ.get('LEDFX_PORT', '8888')
LEDFX_URL = f'http://{LEDFX_HOST}:{LEDFX_PORT}'
CONFIG_DIR = os.environ.get('AIRGLOW_CONFIG_DIR', '/var/lib/airglow')
HOOKS_YAML = os.path.join(CONFIG_DIR, 'ledfx-hooks.yaml')


def require_admin():
    if request.path == '/healthz':
        return
    password = os.environ.get('AIRGLOW_ADMIN_PASSWORD', '')
    if password:
        auth = request.authorization
        if not auth or auth.username != 'admin' or not hmac.compare_digest(
                (auth.password or '').encode(), password.encode()):
            return '', 401, {'WWW-Authenticate': 'Basic realm="Airglow"'}
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('Origin')
        if origin and (urlsplit(origin).scheme not in ('http', 'https')
                       or urlsplit(origin).netloc != request.host):
            return jsonify({'error': 'Cross-origin writes are not allowed.'}), 403


def get_ledfx_virtuals():
    """Get LedFX virtuals status"""
    try:
        result = subprocess.run(
            ['curl', '-s', '-f', f'{LEDFX_URL}/api/virtuals'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            virtuals = {}
            if 'virtuals' in data:
                for vid, vdata in data['virtuals'].items():
                    virtuals[vid] = {
                        'name': vdata.get('config', {}).get('name', vid),
                        'active': vdata.get('active', False),
                        'streaming': vdata.get('streaming', False),
                        'effect': vdata.get('effect', {}).get('type', 'none') if isinstance(vdata.get('effect'), dict) else 'none',
                        'paused': data.get('paused', False)
                    }
            return {'connected': True, 'virtuals': virtuals, 'paused': data.get('paused', False)}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, subprocess.SubprocessError):
        pass
    return {'connected': False, 'virtuals': {}, 'paused': False}


def get_ledfx_devices():
    """Get LedFX devices status"""
    try:
        result = subprocess.run(
            ['curl', '-s', '-f', f'{LEDFX_URL}/api/devices'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            devices = {}
            if 'devices' in data:
                for did, ddata in data['devices'].items():
                    devices[did] = {
                        'online': ddata.get('online', False),
                        'type': ddata.get('type', 'unknown'),
                        'config': ddata.get('config', {})
                    }
            return {'connected': True, 'devices': devices}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, subprocess.SubprocessError):
        pass
    return {'connected': False, 'devices': {}}


def get_ledfx_scenes():
    """Get LedFX scenes"""
    try:
        result = subprocess.run(
            ['curl', '-s', '-f', f'{LEDFX_URL}/api/scenes'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            scenes = {}
            if 'scenes' in data:
                for sid, sdata in data['scenes'].items():
                    scenes[sid] = {
                        'name': sdata.get('name', sid),
                        'virtuals': sdata.get('virtuals', [])
                    }
            return {'connected': True, 'scenes': scenes}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, subprocess.SubprocessError):
        pass
    return {'connected': False, 'scenes': {}}


def get_hook_config():
    """Read hook enable/disable status from YAML only"""
    try:
        # Read from YAML only (shairport-sync.conf is never edited)
        if os.path.exists(HOOKS_YAML):
            with open(HOOKS_YAML, 'r') as f:
                config = yaml.safe_load(f) or {}

            hooks_config = config.get('hooks', {})
            start_hook = hooks_config.get('start', {})
            end_hook = hooks_config.get('end', {})

            return {
                'start_hook_enabled': start_hook.get('enabled', True),
                'end_hook_enabled': end_hook.get('enabled', True)
            }

        # Default if YAML doesn't exist yet (fresh installation - hooks disabled)
        return {
            'start_hook_enabled': False,
            'end_hook_enabled': False
        }
    except Exception as e:
        logger.error(f"Error reading hook config: {e}")
        return {'error': str(e) if app.debug else 'Error reading configuration'}


def get_virtual_config():
    """Read virtual configuration from YAML file"""
    try:
        # Try YAML first
        if os.path.exists(HOOKS_YAML):
            with open(HOOKS_YAML, 'r') as f:
                config = yaml.safe_load(f) or {}

            ledfx_config = config.get('ledfx', {})
            hooks_config = config.get('hooks', {})

            start_hook = hooks_config.get('start', {})
            end_hook = hooks_config.get('end', {})

            start_virtuals = start_hook.get('virtuals', [])
            end_virtuals = end_hook.get('virtuals', [])

            # Check for explicit all_virtuals flag, default to True
            start_all_virtuals = start_hook.get('all_virtuals')
            if start_all_virtuals is None:
                # If flag not present, check if list is empty
                start_all_virtuals = len(start_virtuals) == 0

            end_all_virtuals = end_hook.get('all_virtuals')
            if end_all_virtuals is None:
                # If flag not present, check if list is empty
                end_all_virtuals = len(end_virtuals) == 0

            return {
                'ledfx': {
                    'host': ledfx_config.get('host', 'localhost'),
                    'port': ledfx_config.get('port', 8888)
                },
                'hooks': {
                    'start': {
                        'enabled': start_hook.get('enabled', True),
                        'mode': start_hook.get('mode', 'toggle'),  # 'toggle' or 'scene'
                        'virtuals': start_virtuals,
                        'all_virtuals': start_all_virtuals,
                        'scenes': start_hook.get('scenes', [])  # List of scene IDs
                    },
                    'end': {
                        'enabled': end_hook.get('enabled', True),
                        'mode': end_hook.get('mode', 'toggle'),  # 'toggle' or 'scene'
                        'virtuals': end_virtuals,
                        'all_virtuals': end_all_virtuals,
                        'scenes': end_hook.get('scenes', [])  # List of scene IDs
                    }
                }
            }

        # Default if no config exists (fresh installation - hooks disabled)
        return {
            'ledfx': {'host': 'localhost', 'port': 8888},
            'hooks': {
                'start': {
                    'enabled': False,
                    'mode': 'toggle',  # Default to toggle mode
                    'virtuals': [],
                    'all_virtuals': False,  # New installations choose outputs explicitly.
                    'scenes': []
                },
                'end': {
                    'enabled': False,
                    'mode': 'toggle',  # Default to toggle mode
                    'virtuals': [],
                    'all_virtuals': False,  # Existing YAML keeps its saved scope.
                    'scenes': []
                }
            }
        }
    except Exception as e:
        logger.error(f"Error reading virtual config: {e}")
        return {'error': str(e) if app.debug else 'Error reading configuration'}


def save_virtual_config(config_data):
    """Write virtual configuration to YAML file"""
    try:
        # Build YAML structure with new nested format
        start_hook_data = config_data.get('start_hook', {})
        end_hook_data = config_data.get('end_hook', {})

        yaml_data = {
            'ledfx': {
                'host': LEDFX_HOST,
                'port': int(LEDFX_PORT)
            },
            'hooks': {
                'start': {
                    'enabled': config_data.get('start_enabled', True),
                    'mode': start_hook_data.get('mode', 'toggle'),  # 'toggle' or 'scene'
                    'all_virtuals': start_hook_data.get('all_virtuals', True),
                    'virtuals': start_hook_data.get('virtuals', []),
                    'scenes': start_hook_data.get('scenes', [])  # List of scene IDs
                },
                'end': {
                    'enabled': config_data.get('end_enabled', True),
                    'mode': end_hook_data.get('mode', 'toggle'),  # 'toggle' or 'scene'
                    'all_virtuals': end_hook_data.get('all_virtuals', True),
                    'virtuals': end_hook_data.get('virtuals', []),
                    'scenes': end_hook_data.get('scenes', [])  # List of scene IDs
                }
            }
        }

        # Preserve extension settings that this form does not edit.
        if os.path.exists(HOOKS_YAML):
            with open(HOOKS_YAML) as source:
                previous = yaml.safe_load(source) or {}
            previous.setdefault('ledfx', {}).update(yaml_data['ledfx'])
            hooks = previous.setdefault('hooks', {})
            for key in ('start', 'end'):
                hooks.setdefault(key, {}).update(yaml_data['hooks'][key])
            yaml_data = previous

        # Write YAML file
        with tempfile.NamedTemporaryFile(mode='w', dir=CONFIG_DIR, delete=False) as f:
            temporary_path = f.name
            try:
                yaml.safe_dump(yaml_data, f, default_flow_style=False, sort_keys=False)
                f.flush()
                os.fsync(f.fileno())
                os.chmod(temporary_path, 0o644)
                os.replace(temporary_path, HOOKS_YAML)
            finally:
                if os.path.exists(temporary_path):
                    os.unlink(temporary_path)

        return {'success': True}
    except Exception as e:
        logger.error(f"Error saving virtual config: {e}")
        return {'error': str(e) if app.debug else 'Error saving configuration'}


def get_config():
    """Get current configuration"""
    try:
        hook_config = get_hook_config()
        virtual_config = get_virtual_config()
        virtuals_list = get_ledfx_virtuals()

        # Get list of available virtual IDs
        available_virtuals = list(virtuals_list.get('virtuals', {}).keys()) if virtuals_list.get('connected') else []

        # Get list of available scenes
        scenes_list = get_ledfx_scenes()
        available_scenes = list(scenes_list.get('scenes', {}).keys()) if scenes_list.get('connected') else []

        # Get device count
        devices_data = get_ledfx_devices()
        has_devices = devices_data.get('connected') and len(devices_data.get('devices', {})) > 0

        # Also check if virtuals are available (virtuals can exist without devices being "online")
        has_virtuals = len(available_virtuals) > 0

        return jsonify({
            'hooks': hook_config,
            'virtuals': virtual_config,
            'available_virtuals': available_virtuals,
            'available_scenes': available_scenes,
            'virtual_details': virtuals_list.get('virtuals', {}),
            'scene_details': scenes_list.get('scenes', {}),
            'ledfx_connected': virtuals_list.get('connected', False) and scenes_list.get('connected', False),
            'has_devices': has_devices or has_virtuals,  # Show UI if devices OR virtuals exist
        })
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({'error': str(e) if app.debug else 'Error reading configuration'}), 500


def validate_hook(hook):
    """Validate the action shape shared by saved automation and one-off tests."""
    if not isinstance(hook, dict) or type(hook.get('all_virtuals', True)) is not bool:
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
    return {'mode': mode, 'all_virtuals': hook.get('all_virtuals', True),
            'virtuals': virtuals, 'scenes': scenes}


def save_config():
    """Save configuration changes"""
    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({'error': 'Configuration must be an object.'}), 400
        for key in ('start_enabled', 'end_enabled'):
            if type(data.get(key, False)) is not bool:
                return jsonify({'error': f'{key} must be a boolean.'}), 400
        try:
            for key in ('start_hook', 'end_hook'):
                validate_hook(data.get(key, {}))
        except ValueError as error:
            return jsonify(error=str(error)), 400

        start_enabled = data.get('start_enabled', False)
        end_enabled = data.get('end_enabled', False)

        start_hook_data = data.get('start_hook', {})
        end_hook_data = data.get('end_hook', {})

        start_mode = start_hook_data.get('mode', 'toggle')
        end_mode = end_hook_data.get('mode', 'toggle')

        start_all_virtuals = start_hook_data.get('all_virtuals', True)
        start_virtuals = start_hook_data.get('virtuals', [])
        start_scenes = start_hook_data.get('scenes', [])
        end_all_virtuals = end_hook_data.get('all_virtuals', True)
        end_virtuals = end_hook_data.get('virtuals', [])
        end_scenes = end_hook_data.get('scenes', [])

        # Validate mode values
        if start_mode not in ['toggle', 'scene']:
            return jsonify({'error': f'Invalid mode for start hook: {start_mode}. Must be "toggle" or "scene"'}), 400
        if end_mode not in ['toggle', 'scene']:
            return jsonify({'error': f'Invalid mode for end hook: {end_mode}. Must be "toggle" or "scene"'}), 400

        # Validate virtual IDs if toggle mode and specific virtuals are selected
        if start_mode == 'toggle' or end_mode == 'toggle':
            virtuals_list = get_ledfx_virtuals()
            available_virtuals = set(virtuals_list.get('virtuals', {}).keys()) if virtuals_list.get('connected') else set()

        if start_mode == 'toggle':
            # Validate start hook virtuals
            if not start_all_virtuals and start_virtuals:
                for v in start_virtuals:
                    vid = v.get('id')
                    if vid and vid not in available_virtuals:
                        return jsonify({'error': f'Invalid virtual ID in start hook: {vid}'}), 400

                    # Validate repeat counts
                    repeats = v.get('repeats', 1)
                    if not isinstance(repeats, int) or repeats < 0:
                        return jsonify({'error': f'Invalid repeats for {vid} in start hook: must be integer >= 0'}), 400

        # Validate end hook virtuals
        if end_mode == 'toggle':
            if not end_all_virtuals and end_virtuals:
                for v in end_virtuals:
                    vid = v.get('id')
                    if vid and vid not in available_virtuals:
                        return jsonify({'error': f'Invalid virtual ID in end hook: {vid}'}), 400

                    # Validate repeat counts
                    repeats = v.get('repeats', 0)
                    if not isinstance(repeats, int) or repeats < 0:
                        return jsonify({'error': f'Invalid repeats for {vid} in end hook: must be integer >= 0'}), 400

        # Validate scene IDs if scene mode
        if start_mode == 'scene':
            scenes_list = get_ledfx_scenes()
            available_scenes = set(scenes_list.get('scenes', {}).keys()) if scenes_list.get('connected') else set()

            for sid in start_scenes:
                if sid not in available_scenes:
                    return jsonify({'error': f'Invalid scene ID in start hook: {sid}'}), 400

        if end_mode == 'scene':
            scenes_list = get_ledfx_scenes()
            available_scenes = set(scenes_list.get('scenes', {}).keys()) if scenes_list.get('connected') else set()

            for sid in end_scenes:
                if sid not in available_scenes:
                    return jsonify({'error': f'Invalid scene ID in end hook: {sid}'}), 400

        # Save virtual configuration (includes hook enable/disable in YAML)
        # No restart needed - hook scripts check YAML dynamically
        virtual_config_data = {
            'start_enabled': start_enabled,
            'end_enabled': end_enabled,
            'start_hook': {
                'mode': start_mode,
                'all_virtuals': start_all_virtuals,
                'virtuals': start_virtuals,
                'scenes': start_scenes
            },
            'end_hook': {
                'mode': end_mode,
                'all_virtuals': end_all_virtuals,
                'virtuals': end_virtuals,
                'scenes': end_scenes
            }
        }
        virtual_result = save_virtual_config(virtual_config_data)
        if 'error' in virtual_result:
            return jsonify(virtual_result), 500

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error saving config: {e}", exc_info=True)
        return jsonify({'error': str(e) if app.debug else 'Error saving configuration'}), 500
