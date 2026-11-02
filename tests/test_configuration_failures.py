"""Settings remain editable without LedFX; stale editors cannot overwrite newer changes."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web'))
import native
import settings_store


class ConfigurationFailures(unittest.TestCase):
    def test_offline_edits_conflicts_and_corrupt_state_recovery(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,
                AIRGLOW_CONFIG_DIR=directory, AIRGLOW_ADMIN_PASSWORD=''), \
                patch.object(native.config_api, 'get_ledfx_virtuals', side_effect=AssertionError('No network on settings path')):
            client = native.app.test_client()
            response = client.get('/api/config?catalog=0')
            self.assertEqual(response.status_code, 200)
            config = response.get_json()
            revision = config['revision']
            payload = {'start_enabled':True, 'start_hook':{'virtuals':[{'id':'offline-lamp'}]}, 'revision':revision}
            self.assertEqual(client.post('/api/config', json=payload).status_code, 200)
            saved = settings_store.path().read_bytes()
            self.assertEqual(client.post('/api/config', json=payload).status_code, 409)
            self.assertEqual(settings_store.path().read_bytes(), saved)
            # Disabling never requires the old output or scene to be reachable.
            payload.pop('revision'); payload['start_enabled'] = False
            self.assertEqual(client.post('/api/config', json=payload).status_code, 200)
            payload['start_enabled'] = True; payload['start_hook'] = {}
            self.assertEqual(client.post('/api/config', json=payload).status_code, 400)
            for invalid in (None, [], 'text'):
                self.assertEqual(client.post('/api/receiver', json=invalid).status_code, 400)
            receiver = client.get('/api/receiver').get_json()
            self.assertEqual(client.post('/api/receiver', json={'name':'First', 'revision':receiver['revision']}).status_code, 200)
            self.assertEqual(client.post('/api/receiver', json={'name':'Stale', 'revision':receiver['revision']}).status_code, 409)
            good = settings_store.read()
            settings_store.path().write_text('{broken')
            self.assertEqual(client.get('/api/config?catalog=0').status_code, 500)
            with patch.object(native, 'command', side_effect=OSError('Unavailable')):
                status = client.get('/api/status')
                self.assertEqual(status.status_code, 200)
                self.assertIn('Restore a valid backup', status.get_json()['configuration_error'])
            self.assertEqual(client.post('/api/settings/restore', json={'config':good}).status_code, 200)
            self.assertEqual(settings_store.read(), good)
            damaged = b'\xffbroken'
            settings_store.path().write_bytes(damaged)
            self.assertEqual(client.post('/api/settings/restore', json={'config':good}).status_code, 200)
            previous = json.loads((Path(directory) / 'airglow.previous.json').read_text())
            self.assertEqual(base64.b64decode(previous['invalid_configuration_base64']), damaged)
