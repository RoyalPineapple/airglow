"""Airglow status for native NixOS services. LedFX keeps its own settings UI."""
import json
import os
import subprocess
import tempfile
import re
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, render_template, request

import product
import receiver
from session_worker import worker_available
import settings_store
import configuration as config_api
from configuration import require_admin

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
app.before_request(require_admin)
UNITS = ('shairport-sync', 'nqptp', 'pulseaudio', 'ledfx')


@app.context_processor
def build_context():
    return {'build_info': product.release_identification()}


@app.errorhandler(413)
def upload_too_large(error):
    return jsonify(error='Configuration files must be smaller than 1 MB.'), 413


@app.get('/api/settings/export')
def export_settings():
    try:
        data = settings_store.read()
    except ValueError as error:
        return jsonify(error=str(error)), 500
    return app.response_class(json.dumps(data, indent=2) + '\n', mimetype='application/json', headers={
        'Content-Disposition': 'attachment; filename=airglow.json', 'Cache-Control': 'no-store'})


@app.post('/api/settings/restore')
def restore_settings():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or type(payload.get('preview', False)) is not bool:
        return jsonify(error='Choose a valid Airglow configuration file.'), 400
    try:
        data, restart = settings_store.restore(payload.get('config'), preview=payload.get('preview', False))
        summary = {key: {'enabled':hook['enabled'], 'mode':hook['mode'],
                         'all_virtuals':hook['all_virtuals'], 'output_count':len(hook['virtuals']),
                         'scenes':hook['scenes']} for key,hook in data['hooks'].items()}
        return jsonify(success=True, preview=payload.get('preview', False), receiver=receiver.public(data['receiver']),
                       hooks=summary, restart_requested=restart and not payload.get('preview', False), restart_required=restart), {'Cache-Control': 'no-store'}
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        return jsonify(error='Configuration could not be applied. Check the saved settings and retry.'), 500


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
    airplay = {'device_name': None, 'desired_name': None, 'advertising': None,
               'configuration_state': 'unknown', 'observed_names': {},
               'running': services['shairport-sync']['running']}
    configuration_error = None
    try:
        saved = receiver.load()
        settings = receiver.public(saved)
        airplay['desired_name'] = settings['effective_name']
        airplay['revision'] = settings['revision']
        address = os.environ['AIRGLOW_ADDRESS']
        addresses = {address}
        if address == '0.0.0.0':
            links = json.loads(command('ip', '-json', '-4', 'address', 'show', 'dev', os.environ['AIRGLOW_INTERFACE']))
            addresses = {item['local'] for link in links for item in link.get('addr_info', []) if item.get('family') == 'inet' and item.get('scope') == 'global'}
        for service, port in (('_airplay._tcp', '7000'), ('_raop._tcp', '7000')):
            rows = [line.split(';') for line in command('avahi-browse', '-rpt', service).splitlines()]
            names = []
            for row in rows:
                if len(row) >= 9 and row[0] == '=' and row[4] == service and row[7] in addresses and row[8] == port:
                    name = re.sub(rb'\\([0-9]{3})', lambda match: bytes([int(match[1])]), row[3].encode()).decode('utf-8', errors='replace')
                    if service == '_raop._tcp':
                        name = name.partition('@')[2]
                    names.append(name)
            airplay['observed_names'][service] = sorted(set(names))
        observed = airplay['observed_names']
        matching = all(settings['effective_name'] in observed[service] for service in ('_airplay._tcp', '_raop._tcp'))
        airplay['advertising'] = matching
        names = observed.get('_airplay._tcp', [])
        airplay['device_name'] = names[0] if len(names) == 1 else None
        airplay['configuration_state'] = 'mismatch' if any(observed.values()) and not matching else 'pending'
        try:
            receipt = json.loads((Path(os.environ.get('AIRGLOW_RUNTIME', '/runtime')) / 'receiver.applied').read_text())
            pid = int(command('systemctl', 'show', 'shairport-sync.service', '--property=MainPID', '--value').strip())
            if matching and services['shairport-sync']['running'] and receipt.get('pid') == pid and receipt.get('fingerprint') == settings_store._digest(saved):
                airplay['configuration_state'] = 'applied'
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        if airplay['configuration_state'] != 'applied':
            try:
                result = command('systemctl', 'show', 'airglow-receiver-apply.service', '--property=Result', '--value').strip()
                if result not in ('success', ''):
                    airplay['configuration_state'] = 'failed'
            except (OSError, subprocess.SubprocessError):
                pass
    except ValueError as error:
        configuration_error = str(error)
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
    try:
        hooks = config_api.get_hook_config()
    except ValueError as error:
        configuration_error = str(error)
        hooks = {}
    actions_enabled = hooks.get('start_hook_enabled') or hooks.get('end_hook_enabled')
    data = {'services': services, 'audio': audio, 'airplay': airplay, 'ledfx': engine,
            'devices': devices, 'configuration_error': configuration_error,
            'diagnostics': {'available': all(s['running'] is not None for s in services.values()),
                            'actions_worker_running': worker_available(Path(os.environ.get('AIRGLOW_RUNTIME', '/runtime'))) if actions_enabled else None},
            'session_action': product.action_status() if actions_enabled else {'state': 'disabled'},
            'release': product.release_identification() | {'configuration_version': settings_store.VERSION, 'runtime': 'NixOS', 'versions': json.loads(os.environ.get('AIRGLOW_VERSIONS', '{}'))},
            'ledfx_browser_url': product.browser_url(request.host.split(':')[0])}
    data['state'] = product.summary(data)
    if airplay['configuration_state'] == 'pending' and data['state'] != 'degraded':
        data['state'] = 'unknown'
    if configuration_error or airplay['configuration_state'] in ('mismatch', 'failed') or data['diagnostics']['actions_worker_running'] is False:
        data['state'] = 'degraded'
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
    return jsonify(observe()), {'Cache-Control': 'no-store'}


@app.route('/api/config', methods=['GET', 'POST'])
def configuration():
    if request.method == 'POST':
        return config_api.save_config()
    response = app.make_response(config_api.get_config(include_catalog=request.args.get('catalog') != '0'))
    if response.status_code == 200:
        data = response.get_json()
        data['airplay_name'] = receiver.public(receiver.load())['effective_name']
        return jsonify(data)
    return response


@app.get('/api/catalog')
def catalog():
    return config_api.get_config()


@app.route('/api/receiver', methods=['GET', 'POST'])
@app.post('/api/airplay-name')
def receiver_settings():
    try:
        if request.method == 'GET':
            return jsonify(receiver.public(receiver.load()))
        saved = receiver.save(request.get_json(silent=True))
        return jsonify(success=True, name=saved['effective_name'], receiver=saved)
    except settings_store.ConflictError as error:
        return jsonify(error=str(error)), 409
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        return jsonify(error='Receiver settings could not be applied. Check the saved settings and retry.'), 500


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
        if not worker_available(runtime):
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
    try:
        receiver.request_restart()
        return jsonify(success=True)
    except (OSError, ValueError):
        return jsonify(error='The receiver restart could not be requested. Check saved settings.'), 503


@app.get('/api/diagnostics/download')
def diagnostics():
    data = observe()
    # Export only service states and connection results, never raw config or host inventories.
    return jsonify({key: data[key] for key in ('services', 'state', 'audio', 'airplay', 'ledfx', 'release')}), {
        'Content-Disposition': 'attachment; filename=airglow-diagnostics.json', 'Cache-Control': 'no-store'}


@app.get('/config')
@app.get('/status')
@app.get('/browser')
@app.get('/ledfx')
def details():
    if request.path == '/config':
        return render_template('native_config.html', ledfx_url=product.browser_url(request.host.split(':')[0]))
    return render_template('native.html', ledfx_url=product.browser_url(request.host.split(':')[0]))
