"""Small product-facing status and privacy boundary."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


def release_identification():
    version = json.loads(Path(__file__).with_name('release.json').read_text())['version']
    return {'version': version, 'revision': os.environ.get('AIRGLOW_REVISION', 'development')}


def browser_url(host):
    url = os.environ.get('LEDFX_BROWSER_URL') or f'http://{host}:8888'
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('LEDFX_BROWSER_URL must be an HTTP(S) URL without credentials')
    return url




def action_status():
    try:
        runtime = Path(os.environ.get('AIRGLOW_RUNTIME', '/runtime'))
        result = json.loads((runtime / 'action.json').read_text())
        if result.get('event', {}).get('session') != (runtime / 'receiver').read_text().strip():
            return {'state': 'unknown'}
        return result
    except (OSError, ValueError):
        return {'state': 'unknown'}


def summary(status):
    audio, ledfx, airplay = (status.get(k) or {} for k in ('audio', 'ledfx', 'airplay'))
    checks = [audio.get('pulseaudio', {}).get('available'), ledfx.get('connected'), airplay.get('advertising')]
    if any(value is False for value in checks):
        return 'degraded'
    if (status.get('session_action') or action_status()).get('state') in ('failed', 'partial_failure'):
        return 'degraded'
    if (status.get('diagnostics') or {}).get('available') is False:
        return 'unknown'
    if any(value is None for value in checks):
        return 'unknown'
    if audio.get('shairport_connected') and not audio.get('shairport_corked'):
        return 'playing'
    return 'idle' if audio.get('shairport_connected') else 'ready'
