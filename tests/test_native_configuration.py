"""Native configuration contracts: private settings and compatible playback actions."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web'))
import native
import receiver
import session_worker
import settings_store


class NativeConfiguration(unittest.TestCase):
    def test_repeated_name_changes_signal_restart_and_noop_does_not(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,
                AIRGLOW_CONFIG_DIR=directory, AIRGLOW_ADMIN_PASSWORD=''):
            client = native.app.test_client()
            signal = Path(directory) / 'receiver.restart'
            previous = None
            for name in ('Studio', 'Kitchen', ''):
                response = client.post('/api/receiver', json={'name':name})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.get_json()['receiver']['restart_requested'])
                self.assertEqual(receiver.load()['name'], name)
                current = signal.read_text()
                self.assertNotEqual(current, previous)
                self.assertFalse(client.post('/api/receiver', json={'name':name}).get_json()['receiver']['restart_requested'])
                self.assertEqual(signal.read_text(), current)
                previous = current

    def test_receiver_roundtrip_keeps_password_private_and_rejects_invalid_changes(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,
                AIRGLOW_CONFIG_DIR=directory, AIRGLOW_DEFAULT_RECEIVER_NAME='airglow-dev', AIRGLOW_ADMIN_PASSWORD=''):
            client = native.app.test_client()
            self.assertEqual(client.get('/api/receiver').get_json()['effective_name'], 'airglow-dev')
            secret = 'fake-secret-"\\${literal}'
            response = client.post('/api/receiver', json={'name':'Studio', 'password':secret, 'fixed_volume':False})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(secret, response.get_data(as_text=True))
            self.assertTrue(response.get_json()['receiver']['password_set'])
            saved = receiver.settings_path().read_bytes()
            self.assertEqual(receiver.settings_path().stat().st_mode & 0o777, 0o640)
            for invalid in ({'name':'bad\nname'}, {'mode':'classic'}, {'mode':'shell'}, {'fixed_volume':'yes'}, {'password':False},
                            *({'idle_timeout':value} for value in (0, -1, 301, True, '20', 1.5))):
                self.assertEqual(client.post('/api/receiver', json=invalid).status_code, 400)
                self.assertEqual(receiver.settings_path().read_bytes(), saved)
            self.assertEqual(client.post('/api/receiver', json={'name':''}).status_code, 200)
            self.assertEqual(receiver.load()['password'], secret)
            data = client.post('/api/receiver', json={'clear_password':True}).get_json()['receiver']
            self.assertFalse(data['password_set'])
            self.assertEqual(data['effective_name'], 'airglow-dev')
            with patch.dict(os.environ, AIRGLOW_ADMIN_PASSWORD='admin-qa'):
                self.assertEqual(client.get('/api/receiver').status_code, 401)
                self.assertEqual(client.post('/api/config', json={}).status_code, 401)
                self.assertEqual(client.post('/api/actions/test', json={'hook':'start'}).status_code, 401)

    def test_idle_delay_preserves_old_settings_and_reaches_receiver_configuration(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,
                AIRGLOW_CONFIG_DIR=directory, AIRGLOW_RUNTIME=directory, AIRGLOW_ADMIN_PASSWORD=''):
            original = {'name':'Studio', 'mode':'airplay2', 'fixed_volume':True, 'password':'fake-private'}
            legacy = Path(directory) / 'receiver.json'
            legacy.write_text(json.dumps(original))
            before = legacy.read_bytes()
            settings_store.ensure()
            receiver.request_restart()
            client = native.app.test_client()
            self.assertEqual(client.get('/api/receiver').get_json()['idle_timeout'], 10)
            self.assertFalse(client.post('/api/receiver', json={'idle_timeout':10}).get_json()['receiver']['restart_requested'])
            self.assertEqual(legacy.read_bytes(), before)
            response = client.post('/api/receiver', json={'idle_timeout':25}).get_json()['receiver']
            self.assertTrue(response['restart_requested'])
            self.assertEqual(receiver.load()['password'], 'fake-private')
            base = Path(directory) / 'base.conf'
            base.write_text('sessioncontrol={active_state_timeout=10.0;};')
            with patch.dict(os.environ, SHAIRPORT_CONF=str(base)), patch.object(receiver.os, 'execv') as execute:
                receiver.run('/test/shairport-sync')
            generated = Path(directory) / 'receiver.conf'
            self.assertIn('active_state_timeout=25.0;', generated.read_text())
            self.assertIn('--configfile=' + str(generated), execute.call_args.args[1])
            self.assertNotIn('fake-private', ' '.join(execute.call_args.args[1]))
            self.assertEqual(generated.stat().st_mode & 0o777, 0o640)
            self.assertIn('10.0', base.read_text())

    def test_action_form_saves_yaml_targets_and_repeats_without_losing_extensions(self):
        commands = []
        class LedFx(BaseHTTPRequestHandler):
            def do_GET(self):
                data = {'/api/virtuals':{'virtuals':{'lamp':{'config':{'name':'Lamp'}}}},
                        '/api/scenes':{'scenes':{'evening':{}}}, '/api/devices':{'devices':{}}}
                body = json.dumps(data.get(self.path, {})).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(body)
            def do_PUT(self):
                commands.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"status":"success"}')
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), LedFx)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'ledfx-hooks.yaml'
                path.write_text('extension: keep\nhooks:\n  start:\n    extension: also-keep\n')
                with patch.dict(os.environ, AIRGLOW_CONFIG_DIR=directory, AIRGLOW_ADMIN_PASSWORD=''), \
                     patch.object(native.config_api, 'LEDFX_URL', f'http://127.0.0.1:{server.server_port}'):
                    client = native.app.test_client()
                    payload = {'start_enabled':True, 'end_enabled':True,
                               'start_hook':{'mode':'toggle', 'all_virtuals':False, 'virtuals':[{'id':'lamp','repeats':3}]},
                               'end_hook':{'mode':'scene', 'scenes':['evening']}}
                    self.assertEqual(client.post('/api/config', json=payload).status_code, 200)
                    legacy_bytes = path.read_bytes()
                    path = settings_store.path()
                    stored = json.loads(path.read_text())
                    self.assertEqual(stored['extensions']['extension'], 'keep')
                    self.assertEqual((Path(directory) / 'ledfx-hooks.yaml').read_bytes(), legacy_bytes)
                    self.assertEqual(stored['hooks']['start']['extension'], 'also-keep')
                    config = client.get('/api/config').get_json()['virtuals']['hooks']
                    self.assertEqual(config['start']['virtuals'], [{'id':'lamp','repeats':3}])
                    self.assertEqual(config['end']['scenes'], ['evening'])
                    details = client.get('/api/config').get_json()
                    self.assertEqual(details['virtual_details']['lamp']['name'], 'Lamp')
                    self.assertTrue(details['ledfx_connected'])
                    runtime = Path(directory) / 'runtime'
                    runtime.mkdir()
                    before_test = path.read_bytes()
                    with patch.dict(os.environ, AIRGLOW_RUNTIME=str(runtime), LEDFX_HOST='127.0.0.1', LEDFX_PORT=str(server.server_port)):
                        self.assertEqual(client.post('/api/actions/test', json={'hook':'shell'}).status_code, 400)
                        self.assertEqual(client.post('/api/actions/test', json={'hook':'start'}, headers={'Origin':'https://other.example'}).status_code, 403)
                        self.assertEqual(client.post('/api/actions/test', json={'hook':'end'}).status_code, 503)
                        (runtime / 'receiver').write_text('receiver-startup-123')
                        (runtime / 'worker.ready').write_text(str(os.getpid()))
                        queued_start = client.post('/api/actions/test', json={'hook':'start'})
                        start_event = queued_start.get_json()['event']
                        session_worker.process(start_event, lambda:start_event, path, runtime / 'action.json')
                        self.assertEqual(commands, [('/api/virtuals/lamp', {'active':True})])
                        commands.clear()
                        queued = client.post('/api/actions/test', json={'hook':'end'})
                        self.assertEqual(queued.status_code, 202)
                        event = json.loads((runtime / 'event.json').read_text())
                        self.assertEqual(event['session'], 'receiver-startup-123')
                        self.assertEqual(event['action'], 'stop')
                        self.assertEqual(event['source'], 'manual')
                        session_worker.process(event, lambda:event, path, runtime / 'action.json')
                        result = client.get('/api/actions/test').get_json()
                        self.assertEqual(result['event']['id'], queued.get_json()['event']['id'])
                        self.assertEqual(result['state'], 'success')
                        self.assertEqual(commands, [('/api/scenes', {'id':'evening', 'action':'activate'})])
                        self.assertEqual(path.read_bytes(), before_test)
                        commands.clear()
                        draft = {'mode':'toggle', 'all_virtuals':False, 'virtuals':[{'id':'lamp'}], 'scenes':[]}
                        queued = client.post('/api/actions/test', json={'hook':'end', 'settings':draft})
                        self.assertEqual(queued.status_code, 202)
                        draft_event = queued.get_json()['event']
                        session_worker.process(draft_event, lambda:draft_event, path, runtime / 'action.json')
                        self.assertEqual(commands, [('/api/virtuals/lamp', {'active':False})])
                        self.assertEqual(path.read_bytes(), before_test)
                        for invalid in ({'mode':'shell'}, {'all_virtuals':'yes'}, {'virtuals':[{'id':5}]}, None):
                            self.assertEqual(client.post('/api/actions/test', json={'hook':'end', 'settings':invalid}).status_code, 400)
                        disabled = json.loads(before_test)
                        disabled['hooks']['end']['enabled'] = False
                        path.write_text(json.dumps(disabled))
                        self.assertEqual(client.post('/api/actions/test', json={'hook':'end'}).status_code, 400)
                        result = session_worker.process(event, lambda:event, path, runtime / 'action.json')
                        self.assertEqual(result['state'], 'skipped')
                        self.assertEqual(len(commands), 1)
                        path.write_bytes(before_test)
                    saved = path.read_bytes()
                    payload['start_hook']['virtuals'][0]['repeats'] = 11
                    self.assertEqual(client.post('/api/config', json=payload).status_code, 400)
                    self.assertEqual(path.read_bytes(), saved)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
