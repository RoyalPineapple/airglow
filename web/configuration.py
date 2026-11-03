"""Saved playback actions and LedFX API access for the native interface."""
import hmac
import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

from flask import current_app as app, jsonify, request

import settings_store
from settings_store import validate_hook

logger = logging.getLogger(__name__)
LEDFX_HOST = os.environ.get('LEDFX_HOST', 'localhost')
LEDFX_PORT = os.environ.get('LEDFX_PORT', '8888')
LEDFX_URL = f'http://{LEDFX_HOST}:{LEDFX_PORT}'


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


def catalog_resource(resource):
    try:
        result = subprocess.run(['curl', '--fail', '--silent', '--max-time', '2',
                                 f'{LEDFX_URL}/api/{resource}'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if isinstance(data.get(resource), dict):
                return {'connected': True, resource: data[resource]}
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        pass
    return {'connected': False, resource: {}}


def get_ledfx_virtuals():
    result = catalog_resource('virtuals')
    result['virtuals'] = {key: {'name': item.get('config', {}).get('name', key),
        'active': item.get('active', False), 'streaming': item.get('streaming', False),
        'segments': item.get('segments', []), 'is_device': item.get('is_device'),
        'effect': (item.get('effect') or {}).get('type', 'none')}
        for key, item in result['virtuals'].items()}
    return result


def get_ledfx_devices():
    return catalog_resource('devices')


def get_ledfx_scenes():
    return catalog_resource('scenes')


def get_hook_config():
    hooks = settings_store.read()['hooks']
    return {'start_hook_enabled': hooks['start']['enabled'], 'end_hook_enabled': hooks['end']['enabled']}


def get_virtual_config():
    return {'ledfx': {'host': LEDFX_HOST, 'port': int(LEDFX_PORT)}, 'hooks': settings_store.read()['hooks']}


def get_config(include_catalog=True):
    """Get current configuration"""
    try:
        virtual_config = get_virtual_config()
        hook_config = {'start_hook_enabled':virtual_config['hooks']['start']['enabled'],
                       'end_hook_enabled':virtual_config['hooks']['end']['enabled']}
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(fn) for fn in (get_ledfx_virtuals, get_ledfx_scenes, get_ledfx_devices)] if include_catalog else []
            virtuals_list, scenes_list, devices_data = [f.result() for f in futures] if futures else [
                {'connected': False, 'virtuals': {}}, {'connected': False, 'scenes': {}}, {'connected': False, 'devices': {}}]

        # Get list of available virtual IDs
        available_virtuals = list(virtuals_list.get('virtuals', {}).keys()) if virtuals_list.get('connected') else []

        # Get list of available scenes
        available_scenes = list(scenes_list.get('scenes', {}).keys()) if scenes_list.get('connected') else []

        # Get device count
        has_devices = devices_data.get('connected') and len(devices_data.get('devices', {})) > 0

        # Also check if virtuals are available (virtuals can exist without devices being "online")
        has_virtuals = len(available_virtuals) > 0

        return jsonify({
            'revision': settings_store.revision(virtual_config['hooks']),
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
        return jsonify(error='Configuration could not be read. Use Backup to restore a valid configuration.'), 500


def save_config():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Configuration must be an object.'), 400
    try:
        document = settings_store.update_hooks(data)
        return jsonify(success=True, revision=settings_store.revision(document['hooks']))
    except settings_store.ConflictError as error:
        return jsonify(error=str(error)), 409
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        return jsonify(error='Playback settings could not be saved.'), 500
