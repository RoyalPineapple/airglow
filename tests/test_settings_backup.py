"""Full configuration backups, migration, failure recovery and secret boundaries."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web'))
import native
import settings_store


class SettingsBackup(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        environment = patch.dict(os.environ, AIRGLOW_CONFIG_DIR=self.directory.name, AIRGLOW_ADMIN_PASSWORD='')
        environment.start()
        self.addCleanup(environment.stop)
        self.client = native.app.test_client()

    def test_export_preview_and_restore_roundtrip_without_ledfx(self):
        root = Path(self.directory.name)
        legacy = {'name':'Studio', 'mode':'airplay2', 'fixed_volume':False, 'password':'FAKE_BACKUP_SECRET'}
        (root / 'receiver.json').write_text(json.dumps(legacy))
        (root / 'ledfx-hooks.yaml').write_text('extension: keep\nhooks:\n  start:\n    enabled: true\n    mode: scene\n    scenes: [music]\n    extension: retained\n  end:\n    enabled: false\n')
        originals = [(p, p.read_bytes()) for p in (root / 'receiver.json', root / 'ledfx-hooks.yaml')]
        settings_store.ensure()
        response = self.client.get('/api/settings/export')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        exported = response.get_json()
        self.assertEqual(exported['receiver']['password'], 'FAKE_BACKUP_SECRET')
        self.assertEqual(exported['receiver']['idle_timeout'], 10)
        self.assertEqual(exported['hooks']['start']['scenes'], ['music'])
        self.assertEqual(exported['hooks']['start']['extension'], 'retained')
        self.assertEqual(exported['extensions']['extension'], 'keep')
        self.assertEqual(settings_store.path().stat().st_mode & 0o777, 0o640)
        self.assertNotIn('FAKE_BACKUP_SECRET', self.client.get('/api/receiver').get_data(as_text=True))
        candidate = copy.deepcopy(exported)
        candidate['receiver'].update(name='Restored', password='', idle_timeout=25)
        before = settings_store.path().read_bytes()
        with patch.object(native.config_api, 'get_ledfx_virtuals', side_effect=AssertionError('backup needs no catalog')):
            preview = self.client.post('/api/settings/restore', json={'config':candidate, 'preview':True})
            self.assertEqual(preview.status_code, 200)
            self.assertFalse(preview.get_json()['receiver']['password_set'])
            self.assertNotIn('FAKE_BACKUP_SECRET', preview.get_data(as_text=True))
            self.assertEqual(settings_store.path().read_bytes(), before)
            response = self.client.post('/api/settings/restore', json={'config':candidate})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(settings_store.read(), candidate)
        self.assertEqual(json.loads((root / 'airglow.previous.json').read_text()), exported)
        self.assertFalse(self.client.get('/api/receiver').get_json()['password_set'])
        for path, contents in originals:
            self.assertEqual(path.read_bytes(), contents)
        with patch.dict(os.environ, AIRGLOW_ADMIN_PASSWORD='fake-admin'):
            self.assertEqual(self.client.get('/api/settings/export').status_code, 401)
            self.assertEqual(self.client.post('/api/settings/restore', json={'config':candidate}).status_code, 401)
        self.assertEqual(self.client.post('/api/settings/restore', json={'config':candidate}, headers={'Origin':'https://other.example'}).status_code, 403)

    def test_invalid_import_and_failed_previous_backup_preserve_current_settings(self):
        data = settings_store.ensure()
        before = settings_store.path().read_bytes()
        invalid = [None, [], {}, data | {'version':2}, data | {'version':True}, data | {'receiver':{'name':'missing fields'}}, data | {'hooks':{}}]
        for candidate in invalid:
            self.assertEqual(self.client.post('/api/settings/restore', json={'config':candidate}).status_code, 400)
            self.assertEqual(settings_store.path().read_bytes(), before)
        response = self.client.post('/api/settings/restore', data='x' * (1024 * 1024 + 1), content_type='application/json')
        self.assertEqual(response.status_code, 413)
        self.assertIn('error', response.get_json())
        replacement = copy.deepcopy(data)
        replacement['receiver']['name'] = 'Replacement'
        rename = Path.replace
        def fail_previous(source, destination):
            if Path(destination).name == 'airglow.previous.json':
                raise OSError('fake backup failure')
            return rename(source, destination)
        with patch.object(Path, 'replace', new=fail_previous):
            self.assertEqual(self.client.post('/api/settings/restore', json={'config':replacement}).status_code, 500)
        self.assertEqual(settings_store.path().read_bytes(), before)
        broken = '{"invalid":NaN}'
        settings_store.path().write_text(broken)
        response = self.client.post('/api/settings/restore', json={'config':data})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['restart_requested'])
        self.assertEqual(settings_store.read(), data)
        previous = json.loads((settings_store.directory() / 'airglow.previous.json').read_text())
        self.assertEqual(previous['invalid_configuration'], broken)

    def test_retry_after_failed_restart_signal_requests_application(self):
        settings_store.ensure()
        open_file = os.open
        def fail_signal(path, *args, **kwargs):
            if Path(path).name == 'receiver.restart':
                raise OSError('fake signal failure')
            return open_file(path, *args, **kwargs)
        with patch.object(settings_store.os, 'open', side_effect=fail_signal):
            self.assertEqual(self.client.post('/api/receiver', json={'name':'Retry me'}).status_code, 500)
        self.assertEqual(settings_store.read()['receiver']['name'], 'Retry me')
        response = self.client.post('/api/receiver', json={'name':'Retry me'})
        self.assertTrue(response.get_json()['receiver']['restart_requested'])
        self.assertFalse(self.client.post('/api/receiver', json={'name':'Retry me'}).get_json()['receiver']['restart_requested'])
        original = settings_store.read()
        incoming = copy.deepcopy(original)
        incoming['receiver']['name'] = 'Restore retry'
        with patch.object(settings_store.os, 'open', side_effect=fail_signal):
            self.assertEqual(self.client.post('/api/settings/restore', json={'config':incoming}).status_code, 500)
        previous_file = settings_store.directory() / 'airglow.previous.json'
        self.assertEqual(json.loads(previous_file.read_text()), original)
        self.assertEqual(self.client.post('/api/settings/restore', json={'config':incoming}).status_code, 200)
        self.assertEqual(json.loads(previous_file.read_text()), original)

    def test_concurrent_receiver_and_action_updates_preserve_both_sections(self):
        settings_store.ensure()
        for index in range(4):
            barrier = threading.Barrier(2)
            def receiver_change():
                barrier.wait()
                settings_store.update_receiver({'name':f'Room {index}'})
            def action_change():
                barrier.wait()
                settings_store.update_hooks({'start_enabled':bool(index % 2), 'start_hook':{'all_virtuals':True}})
            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(receiver_change)
                second = executor.submit(action_change)
                first.result()
                second.result()
            data = settings_store.read()
            self.assertEqual(data['receiver']['name'], f'Room {index}')
            self.assertEqual(data['hooks']['start']['enabled'], bool(index % 2))


if __name__ == '__main__':
    unittest.main()
