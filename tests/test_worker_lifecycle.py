"""Exercise the actual supervised worker and HTTP boundary, without physical lights."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web'))
import native
import session_worker


class WorkerLifecycle(unittest.TestCase):
    def test_pending_restart_supersession_partial_failure_and_deadline(self):
        requests = []
        entered = threading.Event()
        virtuals = {'a':{'segments':[['strip', 0, 9, False]]},
                    'b':{'segments':[['strip', 10, 19, False]]}}
        class LedFX(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'devices':{'gap-test':{'type':'dummy'}}} if self.path.endswith('/devices') else {'virtuals':virtuals}).encode())
            def do_PUT(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path, body))
                if 'slow' in self.path:
                    entered.set(); time.sleep(2.2)
                self.send_response(500 if self.path.endswith('/bad') else 200); self.end_headers()
                try:
                    self.wfile.write(b'{"status":"success"}')
                except (BrokenPipeError, ConnectionResetError):
                    pass
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), LedFX)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        worker = None
        try:
            with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,
                    AIRGLOW_RUNTIME=directory, AIRGLOW_ADMIN_PASSWORD='', LEDFX_HOST='127.0.0.1', LEDFX_PORT=str(server.server_port)):
                runtime = Path(directory)
                (runtime / 'receiver').write_text('current-session')
                def publish(id, targets, session='current-session', action='stop'):
                    event = {'id':id, 'session':session, 'source':'manual', 'action':action,
                             'hook_config':{'enabled':True, 'mode':'toggle', 'virtuals':[{'id':v} for v in targets]}}
                    session_worker.atomic_json(runtime / 'event.json', event)
                    return event
                def start():
                    return subprocess.Popen([sys.executable, str(Path(session_worker.__file__).resolve())], env=os.environ.copy())
                def wait_result(id):
                    deadline = time.monotonic() + 12
                    while time.monotonic() < deadline:
                        try:
                            result = json.loads((runtime / 'action.json').read_text())
                            if result['event']['id'] == id:
                                return result
                        except (OSError, ValueError):
                            pass
                        time.sleep(.05)
                    self.fail('Worker did not complete ' + id)
                # A callback published before worker startup must still run.
                publish('before-start', ['a']); worker = start()
                self.assertEqual(wait_result('before-start')['state'], 'success')
                worker.terminate(); worker.wait(5)
                self.assertFalse((runtime / 'worker.ready').exists())
                count = len(requests)
                worker = start(); time.sleep(.4)
                self.assertEqual(len(requests), count, 'Completed events must not replay')
                worker.terminate(); worker.wait(5)
                # A preserved marker cannot make the API accept tests from a dead worker.
                (runtime / 'worker.ready').write_text(str(worker.pid))
                client = native.app.test_client()
                response = client.post('/api/actions/test', json={'hook':'end', 'settings':{'virtuals':[{'id':'a'}]}})
                self.assertEqual(response.status_code, 503)
                publish('downtime', ['b']); worker = start()
                self.assertEqual(wait_result('downtime')['state'], 'success')
                publish('old-receiver', ['a'], session='previous-session'); time.sleep(.3)
                self.assertEqual(json.loads((runtime / 'action.json').read_text())['event']['id'], 'downtime')
                publish('partial', ['bad', 'b'])
                partial = wait_result('partial')
                self.assertEqual(partial['state'], 'partial_failure')
                self.assertEqual([t['state'] for t in partial['targets']], ['failed', 'success'])
                publish('obsolete', ['slow', 'obsolete-second'])
                self.assertTrue(entered.wait(3))
                publish('latest', ['a'])
                self.assertEqual(wait_result('latest')['state'], 'success')
                self.assertFalse(any(path.endswith('/obsolete-second') for path, body in requests))
                publish('conflict', ['a','b'], action='start')
                self.assertEqual(wait_result('conflict')['state'], 'success')
                virtuals['b']['segments'][0][1] = 9
                count = len(requests)
                publish('overlap', ['a','b'], action='start')
                overlap = wait_result('overlap')
                self.assertEqual(overlap['state'], 'failed')
                self.assertIn('conflict', overlap['message'])
                self.assertEqual(len(requests), count)
                virtuals['a']['segments'] = [['gap-test', 0, 9, False]]
                virtuals['b']['segments'] = [['gap-test', 0, 9, False]]
                publish('gap-layout', ['a','b'], action='start')
                self.assertEqual(wait_result('gap-layout')['state'], 'success')
                virtuals['strip'] = {'segments':[['strip', 0, 1, False]]}
                virtuals['b']['segments'] = [['strip', 8, 9, False]]
                publish('device-conflict', ['strip','b'], action='start')
                self.assertEqual(wait_result('device-conflict')['state'], 'failed')
                started = time.monotonic()
                publish('deadline', ['slow' + str(n) for n in range(7)])
                self.assertEqual(wait_result('deadline')['state'], 'failed')
                self.assertLess(time.monotonic() - started, 11.5)
        finally:
            if worker and worker.poll() is None:
                worker.terminate(); worker.wait(5)
            server.shutdown(); server.server_close(); thread.join()
