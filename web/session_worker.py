"""Process receiver events without blocking Shairport's audio thread."""
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import urllib.parse
import yaml

RUNTIME = Path(os.environ.get('AIRGLOW_RUNTIME', '/runtime'))


def atomic_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data))
    temporary.replace(path)


def actions(config, action):
    hook = config.get('hooks', {}).get('start' if action == 'start' else 'end', {})
    if not hook.get('enabled', False):
        return []
    host = os.environ.get('LEDFX_HOST', 'ledfx')
    port = os.environ.get('LEDFX_PORT', '8888')
    base = f'http://{host}:{port}/api'
    if hook.get('mode', 'toggle') == 'scene':
        return [(base + '/scenes', {'id': sid, 'action': 'activate'}) for sid in hook.get('scenes', [])]
    virtuals = hook.get('virtuals', [])
    if hook.get('all_virtuals', False):
        with urllib.request.urlopen(base + '/virtuals', timeout=2) as response:
            virtuals = [{'id': vid} for vid in json.load(response)['virtuals']]
    result = []
    for virtual in virtuals:
        # Older configurations used zero repeats to disable an output.
        if virtual.get('repeats', 1) == 0:
            continue
        result.append((base + '/virtuals/' + urllib.parse.quote(virtual['id'], safe=''),
                       {'active': action == 'start'}))
    return result


def process(event, current, config_path, status_path):
    deadline = time.monotonic() + 10
    result = {'event': event, 'state': 'success', 'time': time.time()}
    try:
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
            request = urllib.request.Request(url, json.dumps(body).encode(),
                                             {'Content-Type': 'application/json'}, method='PUT')
            with urllib.request.urlopen(request, timeout=min(2, remaining)) as response:
                if json.load(response).get('status') != 'success':
                    raise RuntimeError('LedFX rejected action')
    except Exception as error:
        result.update(state='failed', error=type(error).__name__)
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
    # Existing events describe history, not commands to replay after restart.
    last = current()
    (RUNTIME / 'worker.ready').write_text(str(os.getpid()))
    while True:
        event = current()
        if event and event != last:
            last = event
            job = multiprocessing.Process(target=process, args=(
                event, current, os.environ.get('AIRGLOW_HOOKS_FILE', '/configs/ledfx-hooks.yaml'), RUNTIME / 'action.json'))
            job.start()
            job.join(10)
            if job.is_alive():
                job.terminate()
                job.join(2)
                if job.is_alive():
                    job.kill()
                    job.join()
                atomic_json(RUNTIME / 'action.json', {'event': event, 'state': 'failed', 'error': 'ActionDeadline', 'time': time.time()})
        time.sleep(.1)


if __name__ == '__main__':
    main()
