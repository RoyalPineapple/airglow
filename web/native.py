"""Airglow status for native NixOS services. LedFX keeps its own settings UI."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, render_template, request

import product
import receiver
import configuration as config_api
from configuration import require_admin

app = Flask(__name__)
app.before_request(require_admin)
UNITS = ('shairport-sync', 'nqptp', 'pulseaudio', 'ledfx')


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=3, check=True)
    return result.stdout


def observe():
    services = {}
    for unit in UNITS:
        try:
            state = command('systemctl', 'show', f'{unit}.service', '--property=ActiveState', '--value').strip()
            services[unit] = {'running': state == 'active', 'state': state}
        except (OSError, subprocess.SubprocessError):
            services[unit] = {'running': None, 'state': 'unknown'}
    audio = {'pulseaudio': {'available': None}, 'shairport_connected': None,
             'shairport_corked': None}
    try:
        info = json.loads(command('pactl', '--format=json', 'info'))
        audio['pulseaudio'] = {'available': True, 'server': info['server_string']}
        streams = json.loads(command('pactl', '--format=json', 'list', 'sink-inputs'))
        receiver_streams = [s for s in streams if s.get('properties', {}).get('application.name') == 'Shairport Sync']
        audio.update(shairport_connected=bool(receiver_streams),
                     shairport_corked=all(s['corked'] for s in receiver_streams) if receiver_streams else False)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        pass
    airplay = {'device_name': None, 'advertising': None,
               'running': services['shairport-sync']['running']}
    try:
        settings = receiver.public(receiver.load())
        airplay['device_name'] = settings['effective_name']
        rows = [line.split(';') for line in command('avahi-browse', '-rpt', '_airplay._tcp').splitlines()]
        airplay['advertising'] = any(len(row) >= 9 and row[0] == '='
                                    and row[7] == os.environ['AIRGLOW_ADDRESS']
                                    and row[8] == '7000' for row in rows)
    except (OSError, subprocess.SubprocessError, KeyError):
        pass
    engine = {'connected': None}
    try:
        info = json.loads(command('curl', '--fail', '--silent', '--max-time', '2',
                                 f"{os.environ['LEDFX_API_URL']}/api/info"))
        engine.update({key: info.get(key) for key in ('version', 'name')})
        engine['connected'] = True
    except subprocess.CalledProcessError:
        engine['connected'] = False
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        pass
    devices = {'connected': None, 'devices': {}}
    if engine['connected']:
        try:
            response = json.loads(command('curl', '--fail', '--silent', '--max-time', '2',
                                         f"{os.environ['LEDFX_API_URL']}/api/devices"))
            devices = {'connected': True, 'devices': {
                key: {'online': item.get('online'), 'name': item.get('config', {}).get('name', key)}
                for key, item in response['devices'].items()}}
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, AttributeError):
            pass
    hooks = config_api.get_hook_config()
    actions_enabled = hooks.get('start_hook_enabled') or hooks.get('end_hook_enabled')
    data = {'services': services, 'audio': audio, 'airplay': airplay, 'ledfx': engine,
            'devices': devices,
            'diagnostics': {'available': all(s['running'] is not None for s in services.values())},
            'session_action': product.action_status() if actions_enabled else {'state': 'disabled'},
            'release': {'runtime': 'NixOS', 'versions': json.loads(os.environ.get('AIRGLOW_VERSIONS', '{}'))},
            'ledfx_browser_url': product.browser_url(request.host.split(':')[0])}
    data['state'] = product.summary(data)
    if any(s['running'] is False for s in services.values()):
        data['state'] = 'degraded'
    elif any(d['online'] is False for d in devices['devices'].values()):
        data['state'] = 'degraded'
    elif devices['connected'] is not True or any(d['online'] is None for d in devices['devices'].values()):
        if data['state'] != 'degraded':
            data['state'] = 'unknown'
    return data


@app.get('/healthz')
def health():
    return jsonify(healthy=True)


@app.get('/')
def home():
    return render_template('home.html', ledfx_url=product.browser_url(request.host.split(':')[0]))


@app.get('/api/status')
def status():
    return jsonify(observe())


@app.route('/api/config', methods=['GET', 'POST'])
def configuration():
    if request.method == 'POST':
        return config_api.save_config()
    response = config_api.get_config()
    if response.status_code == 200:
        data = response.get_json()
        data['airplay_name'] = receiver.public(receiver.load())['effective_name']
        return jsonify(data)
    return response


@app.route('/api/receiver', methods=['GET', 'POST'])
@app.post('/api/airplay-name')
def receiver_settings():
    try:
        if request.method == 'GET':
            return jsonify(receiver.public(receiver.load()))
        saved = receiver.save(request.get_json(silent=True))
        return jsonify(success=True, name=saved['effective_name'], receiver=saved)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        return jsonify(error='Receiver settings could not be saved. The previous settings remain in use.'), 500


@app.route('/api/actions/test', methods=['GET', 'POST'])
def test_action():
    if request.method == 'GET':
        return jsonify(product.action_status())
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('hook') not in ('start', 'end'):
        return jsonify(error='Choose a start or end action.'), 400
    draft = 'settings' in data
    if draft:
        try:
            hook = config_api.validate_hook(data['settings']) | {'enabled': True}
        except ValueError as error:
            return jsonify(error=str(error)), 400
    else:
        config = config_api.get_virtual_config()
        if 'error' in config:
            return jsonify(error='Playback settings could not be read.'), 503
        hook = config['hooks'][data['hook']]
        if not hook.get('enabled'):
            return jsonify(error='Enable this action or provide current test settings.'), 400
    if not (hook.get('scenes') if hook.get('mode') == 'scene' else
            hook.get('all_virtuals') or any(v.get('repeats', 1) > 0 for v in hook.get('virtuals', []))):
        return jsonify(error='Choose an output or scene before testing.'), 400
    runtime = Path(os.environ.get('AIRGLOW_RUNTIME', '/runtime'))
    try:
        if not (runtime / 'worker.ready').exists():
            return jsonify(error='The action worker is unavailable.'), 503
        session = (runtime / 'receiver').read_text().strip()
        if not session:
            return jsonify(error='The receiver is unavailable.'), 503
        event = {'session': session, 'id': uuid4().hex,
                 'action': 'start' if data['hook'] == 'start' else 'stop', 'source': 'manual'}
        if draft:
            event['hook_config'] = hook
        # Use a unique temporary file so receiver callbacks can publish concurrently.
        with tempfile.NamedTemporaryFile(mode='w', dir=runtime, delete=False) as output:
            temporary = Path(output.name)
            json.dump(event, output)
        try:
            temporary.chmod(0o640)
            temporary.replace(runtime / 'event.json')
        finally:
            temporary.unlink(missing_ok=True)
        return jsonify(event=event, state='queued'), 202
    except OSError:
        return jsonify(error='The test could not be queued. Check the receiver and action worker.'), 503


@app.post('/api/shairport/restart')
def restart_receiver():
    import time
    (receiver.settings_path().parent / 'receiver.restart').write_text(str(time.time_ns()))
    return jsonify(success=True)


@app.get('/api/diagnostics/download')
def diagnostics():
    data = observe()
    # Export only service states and connection results, never raw config or host inventories.
    return jsonify({key: data[key] for key in ('services', 'state', 'audio', 'airplay', 'ledfx', 'release')}), {
        'Content-Disposition': 'attachment; filename=airglow-diagnostics.json'}


@app.get('/config')
@app.get('/status')
@app.get('/browser')
@app.get('/ledfx')
def details():
    if request.path == '/config':
        return render_template('native_config.html', ledfx_url=product.browser_url(request.host.split(':')[0]))
    data = observe()
    title = 'Connection checks'
    description = 'These are live service checks. Use LedFX to configure devices, effects, and scenes.'
    rows = [(unit, state['state']) for unit, state in data['services'].items()]
    rows += [('AirPlay discovery', str(data['airplay']['advertising'])),
             ('Versions', ', '.join(f'{k}: {v}' for k, v in data['release']['versions'].items()))]
    return render_template('native.html', title=title, description=description, rows=rows,
                           receiver_name=data['airplay']['device_name'] or 'the receiver',
                           ledfx_url=data['ledfx_browser_url'])
