"""The native HTTP status contract must distinguish playback and missing evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web'))
import native


class NativeStatus(unittest.TestCase):
    def test_status_uses_service_audio_and_discovery_evidence(self):
        read_text = Path.read_text

        def read_config(path, *args, **kwargs):
            if str(path) == '/etc/shairport-sync.conf':
                return 'general={name="airglow-dev";};'
            return read_text(path, *args, **kwargs)

        for scenario, expected in [('ready', 'ready'), ('playing', 'playing'),
                                   ('paused', 'idle'), ('stopped', 'degraded'),
                                   ('discovery_timeout', 'unknown'), ('device_offline', 'degraded')]:
            with self.subTest(scenario=scenario):
                def run(args, **kwargs):
                    if args[0] == 'systemctl':
                        output = 'inactive' if scenario == 'stopped' and args[2] == 'nqptp.service' else 'active'
                    elif args[0] == 'pactl':
                        if args[-1] == 'info':
                            output = json.dumps({'server_string': 'unix:/run/pulse/native'})
                        else:
                            streams = [] if scenario == 'ready' else [{
                                'corked': scenario == 'paused',
                                'properties': {'application.name': 'Shairport Sync'}}]
                            output = json.dumps(streams)
                    elif args[0] == 'avahi-browse':
                        if scenario == 'discovery_timeout':
                            raise subprocess.TimeoutExpired(args, 3)
                        output = '=;ens18;IPv4;airglow-dev;_airplay._tcp;local;airglow-dev.local;192.0.2.20;7000;'
                    elif args[0] == 'curl':
                        if args[-1].endswith('/api/devices'):
                            output = json.dumps({'devices': {'lamp': {'config': {'name': 'Table Lamp'}, 'online': scenario != 'device_offline'}}})
                        else:
                            output = json.dumps({'version': '2.2.1', 'name': 'LedFX', 'secret': 'fake-password-keep-private'})
                    else:
                        raise AssertionError(f'Unexpected external program: {args[0]}')
                    return SimpleNamespace(stdout=output, returncode=0)

                with patch.dict(os.environ, AIRGLOW_ADDRESS='192.0.2.20',
                                LEDFX_API_URL='http://192.0.2.20:8888',
                                LEDFX_BROWSER_URL='http://example.test:8888',
                                AIRGLOW_ADMIN_PASSWORD=''), \
                     patch.object(native.subprocess, 'run', side_effect=run), \
                     patch.object(Path, 'read_text', autospec=True, side_effect=read_config):
                    client = native.app.test_client()
                    response = client.get('/api/status')
                    self.assertEqual(response.status_code, 200)
                    data = response.get_json()
                    self.assertEqual(data['state'], expected)
                    if scenario == 'discovery_timeout':
                        self.assertIsNone(data['airplay']['advertising'])
                    bundle = client.get('/api/diagnostics/download')
                    self.assertNotIn('fake-password-keep-private', bundle.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
