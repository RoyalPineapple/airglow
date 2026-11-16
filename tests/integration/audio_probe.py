"""Prove PulseAudio-to-LedFX analysis inside the isolated NixOS test VM."""
import array
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

from websockets.sync.client import connect


base = sys.argv[1]


def api(path, method='GET', data=None):
    request = urllib.request.Request(base + path, None if data is None else json.dumps(data).encode(),
                                     {'Content-Type': 'application/json'}, method=method)
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.load(response)
    assert result.get('status') == 'success', result
    return result


device = api('/api/devices', 'POST', {'type': 'dummy', 'config': {'name': 'Audio probe', 'pixel_count': 16}})['device']['id']
try:
    api(f'/api/virtuals/{device}/effects', 'POST', {'type': 'energy', 'config': {}})
    with connect(base.replace('http://', 'ws://') + '/api/websocket', open_timeout=5, close_timeout=2) as socket:
        socket.send(json.dumps({'id': 1, 'type': 'subscribe_event', 'event_type': 'graph_update'}))

        def measure(seconds):
            deadline = time.monotonic() + seconds
            peak, events = 0, 0
            while time.monotonic() < deadline:
                try:
                    message = json.loads(socket.recv(timeout=max(.01, deadline - time.monotonic())))
                except TimeoutError:
                    break
                event = message.get('event', message)
                if 'melbank' in event:
                    events += 1
                    peak = max(peak, *event['melbank'])
            return peak, events

        quiet, quiet_events = measure(1)
        assert quiet_events > 0 and quiet < .01, (quiet, quiet_events)
        samples = array.array('h', (int(16000 * math.sin(2 * math.pi * 120 * frame / 44100))
                                   for frame in range(44100 * 3) for channel in range(2)))
        if sys.byteorder != 'little':
            samples.byteswap()
        environment = os.environ | {'PULSE_SERVER': 'unix:/run/pulse/native'}
        with tempfile.TemporaryFile() as audio:
            audio.write(samples.tobytes())
            audio.seek(0)
            with subprocess.Popen(['paplay', '--raw', '--format=s16le', '--rate=44100', '--channels=2',
                                   '--device=airglow'], stdin=audio, env=environment) as player:
                try:
                    signal, signal_events = measure(4)
                    assert player.wait(timeout=5) == 0
                    assert signal_events > 0 and signal > .1, (signal, signal_events)
                finally:
                    if player.poll() is None:
                        player.kill()
        print(f'PASS audio bridge: quiet={quiet:.4f}, signal={signal:.4f}, analyser_events={signal_events}')
finally:
    api(f'/api/devices/{device}', 'DELETE')
