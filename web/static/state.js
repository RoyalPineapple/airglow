'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let timer, lastObservation = null;
  const known = value => typeof value === 'boolean';
  function show(id, text, state = 'unknown') { $(id).textContent = text; $(id).dataset.state = state; }
  function next(text, label, href) {
    $('next-step').textContent = text;
    $('next-link').hidden = !label;
    if (label) { $('next-link').textContent = label + ' ↗'; $('next-link').href = href; }
  }
  function unavailable() {
    $('state').textContent = 'State unavailable';
    $('explanation').textContent = 'Airglow could not complete its connection check. The last observation may be out of date.';
    $('overall-dot').dataset.state = 'unknown';
    for (const id of ['receiver','pulse','ledfx','stream','output']) show(id, 'Not checked');
    show('session', 'Not checked');
    $('updated').textContent = lastObservation ? 'Last observation ' + lastObservation.toLocaleTimeString() + ' · stale' : 'No observations yet';
    next('Check that the Airglow services are running, then refresh the state.', 'Troubleshoot', '/status');
  }
  function render(data) {
    const receiver = data.airplay?.advertising;
    const pulse = data.audio?.pulseaudio?.available;
    const engine = data.ledfx?.connected;
    const connected = data.audio?.shairport_connected;
    const paused = data.audio?.shairport_corked;
    const outputs = data.devices?.connected === true ? Object.values(data.devices.devices || {}) : null;
    const offline = outputs?.filter(device => device.online === false) || [];
    const outputUnknown = !outputs || outputs.some(device => !known(device.online));
    show('output', outputUnknown ? 'Not checked' : !outputs.length ? 'Not configured' : offline.length ? offline.length + ' unavailable' : outputs.length + ' connected', outputUnknown ? 'unknown' : !outputs.length || offline.length ? 'attention' : 'good');
    show('receiver', !known(receiver) ? 'Not checked' : receiver ? 'Visible in AirPlay' : 'Not discovered', !known(receiver) ? 'unknown' : receiver ? 'good' : 'attention');
    show('pulse', !known(pulse) ? 'Not checked' : pulse ? 'Available' : 'Unavailable', !known(pulse) ? 'unknown' : pulse ? 'good' : 'attention');
    show('ledfx', !known(engine) ? 'Not checked' : engine ? 'Connected' : 'Not connected', !known(engine) ? 'unknown' : engine ? 'good' : 'attention');
    const streamKnown = known(connected) && (connected === false || known(paused));
    show('stream', !streamKnown ? 'Not checked' : !connected ? 'Idle' : paused ? 'Paused' : 'Active stream', !streamKnown ? 'unknown' : connected && !paused ? 'good' : 'idle');
    const action = data.session_action?.state;
    show('session', ({disabled:'Disabled',success:'Completed',failed:'Failed',superseded:'Superseded',unknown:'No result yet'})[action] || 'No result yet', action === 'failed' ? 'attention' : action === 'success' ? 'good' : 'unknown');
    let title, explanation, state;
    const stopped = Object.entries(data.services || {}).filter(([,service]) => service.running === false).map(([name]) => name);
    if (stopped.length) {
      title = 'A service needs attention'; explanation = 'Not running: ' + stopped.join(', ') + '.'; state = 'attention';
      next('Open troubleshooting to inspect the service states.', 'Troubleshoot', '/status');
    } else if (engine === false) {
      title = 'LedFX is not connected'; explanation = 'Airglow cannot reach the audio engine.'; state = 'attention';
      next('Check that LedFX is running and reachable from Airglow.', 'Troubleshoot', '/status');
    } else if (pulse === false) {
      title = 'Audio bridge unavailable'; explanation = 'The PulseAudio connection needs attention.'; state = 'attention';
      next('Check the audio bridge and the input selected in LedFX.', 'Troubleshoot', '/status');
    } else if (receiver === false) {
      title = 'Receiver not discovered'; explanation = 'Airglow has not confirmed its AirPlay advertisement.'; state = 'attention';
      next('Check receiver discovery on the same LAN as your Apple device.', 'Check discovery', '/browser');
    } else if (![receiver,pulse,engine].every(value => value === true) || !streamKnown || outputUnknown || Object.values(data.services || {}).some(service => service.running !== true)) {
      title = 'Connection check incomplete'; explanation = 'Some connection states have not been confirmed.'; state = 'unknown';
      next('Refresh the state or use troubleshooting to inspect the missing checks.', 'Troubleshoot', '/status');
    } else if (!outputs.length) {
      title = 'Audio ready · add a lighting device'; explanation = 'The audio connections are available. LedFX has no lighting device configured.'; state = 'attention';
      next('Add your supported lighting device in LedFX, then select an effect.', 'Open LedFX', data.ledfx_browser_url);
    } else if (offline.length) {
      title = 'Lighting device unavailable'; explanation = 'LedFX reports offline: ' + offline.map(device => device.name || device.config?.name || 'Unnamed device').join(', ') + '.'; state = 'attention';
      next('Check the device address and LAN connection in LedFX.', 'Open LedFX', data.ledfx_browser_url);
    } else if (action === 'failed') {
      title = 'Audio connected · action failed'; explanation = 'The connections are available, but the last optional session action failed.'; state = 'attention';
      next('Check the enabled start and end rules and their LedFX targets.', 'Session settings', '/config');
    } else {
      title = !connected ? 'Ready for audio' : paused ? 'Session paused' : 'Session active';
      explanation = !connected ? 'The receiver, audio bridge, and LedFX are connected.' : paused ? 'AirPlay remains connected. A paused stream is normal.' : 'AirPlay is connected and its stream is not paused. Audio amplitude is not measured.';
      state = 'good';
      next(!connected ? 'Select ' + (data.airplay?.device_name || 'Airglow') + ' in AirPlay on your Apple device to start a session.' : paused ? 'Resume playback on your Apple device when you are ready.' : 'No action needed.');
    }
    $('state').textContent = title; $('explanation').textContent = explanation; $('overall-dot').dataset.state = state;
    lastObservation = new Date(); $('updated').textContent = 'Observed ' + lastObservation.toLocaleTimeString();
  }
  async function refresh() {
    clearTimeout(timer); $('refresh').disabled = true; $('refresh').textContent = 'Checking…';
    try {
      const response = await fetch('/api/status', {signal: AbortSignal.timeout(15000), cache:'no-store'});
      if (!response.ok) throw new Error('Status request failed');
      const data = await response.json();
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Invalid status');
      render(data);
    } catch { unavailable(); }
    finally { $('refresh').disabled = false; $('refresh').textContent = 'Refresh state ↻'; timer = setTimeout(refresh,10000); }
  }
  $('refresh').addEventListener('click', refresh);
  refresh();
})();
