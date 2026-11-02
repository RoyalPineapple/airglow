"""Process receiver events without blocking Shairport's audio thread."""
import json
import multiprocessing
import os
from pathlib import Path
import signal
import tempfile
import time
import urllib.request
import urllib.parse
import yaml

RUNTIME = Path(os.environ.get('AIRGLOW_RUNTIME', '/runtime'))


def atomic_json(path, data):
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(data, output)
            output.flush()
            temporary.chmod(0o640)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def worker_available(runtime):
    try:
        marker = runtime / 'worker.ready'
        pid = int(marker.read_text())
        if pid <= 0 or time.time() - marker.stat().st_mtime > 3:
            return False
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def actions(config, action):
    hook = config.get('hooks', {}).get('start' if action == 'start' else 'end', {})
    if not hook.get('enabled', False):
        return []
    base = f"http://{os.environ.get('LEDFX_HOST', 'ledfx')}:{os.environ.get('LEDFX_PORT', '8888')}/api"
    if hook.get('mode', 'toggle') == 'scene':
        return [(base + '/scenes', {'id': sid, 'action': 'activate'}) for sid in hook.get('scenes', [])]
    virtuals = hook.get('virtuals', [])
    if hook.get('all_virtuals', False) or action == 'start':
        with urllib.request.urlopen(base + '/virtuals', timeout=2) as response:
            available = json.load(response)['virtuals']
        if hook.get('all_virtuals', False):
            virtuals = [{'id': vid} for vid in available]
        if action == 'start':
            selected = {v['id']: available.get(v['id'], {}) for v in virtuals if v.get('repeats', 1) > 0}
            # LedFX deactivates a device's own virtual, or overlapping external segments.
            gaps = set()
            if any(segment[0].startswith('gap-') for virtual in selected.values() for segment in virtual.get('segments', [])):
                with urllib.request.urlopen(base + '/devices', timeout=2) as response:
                    gaps = {key for key, item in json.load(response)['devices'].items() if key.startswith('gap-') and item.get('type') == 'dummy'}
            segments = []
            for vid, virtual in selected.items():
                for device, start, end, *_ in virtual.get('segments', []):
                    for other, other_device, low, high, own in segments:
                        if vid != other and device == other_device and (own or vid == device or device not in gaps and start <= high and low <= end):
                            raise ValueError('Selected outputs conflict in LedFX. Select non-overlapping outputs or use a scene.')
                    segments.append((vid, device, start, end, vid == device))
    return [(base + '/virtuals/' + urllib.parse.quote(vid, safe=''), {'active': action == 'start'})
            for vid in dict.fromkeys(v['id'] for v in virtuals if v.get('repeats', 1) > 0)]


def process(event, current, config_path, status_path):
    deadline = time.monotonic() + 10
    result = {'event': event, 'state': 'success', 'time': time.time(), 'targets': []}
    try:
        if current() != event:
            result['state'] = 'superseded'
            atomic_json(status_path, result)
            return result
        if event.get('source') == 'manual' and 'hook_config' in event:
            key = 'start' if event['action'] == 'start' else 'end'
            config = {'hooks': {key: event['hook_config']}}
        else:
            path = Path(config_path)
            config = (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}
        commands = actions(config, event['action'])
        if not commands:
            result['state'] = 'skipped'
        for url, body in commands:
            if current() != event:
                result['state'] = 'superseded'
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Action deadline exceeded')
            target = {'id': body.get('id') or urllib.parse.unquote(url.rsplit('/', 1)[-1]), 'state': 'success'}
            try:
                request = urllib.request.Request(url, json.dumps(body).encode(),
                                                 {'Content-Type': 'application/json'}, method='PUT')
                with urllib.request.urlopen(request, timeout=min(2, remaining)) as response:
                    if json.load(response).get('status') != 'success':
                        raise RuntimeError('LedFX rejected action')
            except Exception as error:
                target.update(state='failed', error=type(error).__name__)
            result['targets'].append(target)
        if result['state'] == 'success' and any(t['state'] == 'failed' for t in result['targets']):
            result['state'] = 'partial_failure' if any(t['state'] == 'success' for t in result['targets']) else 'failed'
    except Exception as error:
        result.update(state='failed', error=type(error).__name__)
        if isinstance(error, ValueError):
            result['message'] = str(error)
    atomic_json(status_path, result)
    return result


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    def current():
        try:
            session = (RUNTIME / 'receiver').read_text().strip()
            event = json.loads((RUNTIME / 'event.json').read_text())
            return event if event.get('session') == session else None
        except (OSError, ValueError):
            return None
    # Completed events are receipts; unfinished events in the current receiver session are retried.
    try:
        last = json.loads((RUNTIME / 'action.json').read_text())['event']
    except (OSError, ValueError, KeyError):
        last = None
    ready = RUNTIME / 'worker.ready'
    job = None
    def stop(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    try:
        atomic_json(ready, os.getpid())
        while True:
            ready.touch()
            event = current()
            if event and event != last:
                job = multiprocessing.get_context('fork').Process(target=process, args=(event, current,
                    os.environ.get('AIRGLOW_HOOKS_FILE', '/var/lib/airglow/airglow.json'), RUNTIME / 'action.json'))
                job.start()
                deadline = time.monotonic() + 10
                while job.is_alive() and time.monotonic() < deadline and current() == event:
                    ready.touch()
                    job.join(.1)
                if job.is_alive():
                    job.terminate()
                    job.join(1)
                    if job.is_alive():
                        job.kill()
                        job.join()
                    atomic_json(RUNTIME / 'action.json', {'event': event,
                        'state': 'superseded' if current() != event else 'failed',
                        'error': 'ActionDeadline' if current() == event else 'NewerEvent', 'time': time.time()})
                last = event
            time.sleep(.1)
    finally:
        ready.unlink(missing_ok=True)
        if job and job.is_alive():
            job.terminate()
            job.join(1)
            if job.is_alive():
                job.kill()
                job.join()


if __name__ == '__main__':
    main()
