'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let timer, lastObservation = null;
  const known = value => typeof value === 'boolean';
  function text(id, value) { if ($(id).textContent !== value) $(id).textContent = value; }
  function show(id, value, state = 'unknown') { text(id, value); $(id).dataset.state = state; }
  function attention(message, label = 'Troubleshoot', href = '/status') {
    $('attention').hidden = !message;
    text('next-step', message || '');
    text('next-link', label + ' ↗');
    $('next-link').href = href;
  }
  function unavailable() {
    text('state', 'Unknown'); text('explanation', 'Receiver status could not be refreshed.');
    $('overall-dot').dataset.state = 'unknown';
    show('health', 'Update failed');
    for (const id of ['receiver','pulse','ledfx','output']) show(id, 'Not checked');
    text('receiver-name', '');
    $('device-list').replaceChildren(); $('device-details').open = false;
    text('updated', lastObservation ? 'Last updated ' + lastObservation.toLocaleTimeString() + ' · stale' : 'No successful checks');
    attention('The latest state is unavailable. Check the services or try refreshing.');
  }
  function render(data) {
    const receiver = data.airplay?.advertising, pulse = data.audio?.pulseaudio?.available, engine = data.ledfx?.connected;
    const connected = data.audio?.shairport_connected, corked = data.audio?.shairport_corked;
    const streamKnown = known(connected) && (!connected || known(corked));
    const active = streamKnown && connected && !corked;
    text('state', !streamKnown ? 'Unknown' : active ? 'Receiving' : 'Idle');
    text('explanation', !streamKnown ? 'Receiver activity has not been confirmed.' : active ? 'The receiver audio stream is active.' : 'No active audio stream.');
    $('overall-dot').dataset.state = !streamKnown ? 'unknown' : active ? 'good' : 'idle';
    text('receiver-name', data.airplay?.device_name || '');
    show('receiver', !known(receiver) ? 'Not checked' : receiver ? 'Discoverable' : 'Not discovered', !known(receiver) ? 'unknown' : receiver ? 'good' : 'attention');
    show('pulse', !known(pulse) ? 'Not checked' : pulse ? 'Available' : 'Unavailable', !known(pulse) ? 'unknown' : pulse ? 'good' : 'attention');
    show('ledfx', !known(engine) ? 'Not checked' : engine ? 'Reachable' : 'Unreachable', !known(engine) ? 'unknown' : engine ? 'good' : 'attention');
    const devices = data.devices?.connected === true ? Object.values(data.devices.devices || {}) : null;
    const offline = devices?.filter(d => d.online === false) || [], unchecked = devices?.filter(d => !known(d.online)) || [];
    show('output', !devices ? 'Not checked' : !devices.length ? 'Not configured' : offline.length ? offline.length + ' offline' + (unchecked.length ? ' · ' + unchecked.length + ' unchecked' : '') : unchecked.length ? unchecked.length + ' unchecked' : devices.length + ' reported online', !devices || unchecked.length && !offline.length ? 'unknown' : !devices.length || offline.length ? 'attention' : 'good');
    const rows = (devices || []).map(device => {
      const li = document.createElement('li'), name = document.createElement('span'), status = document.createElement('span');
      name.textContent = device.name || 'Unnamed device';
      status.textContent = !known(device.online) ? 'Not checked' : device.online ? 'Reported online' : 'Reported offline';
      status.dataset.state = !known(device.online) ? 'unknown' : device.online ? 'good' : 'attention';
      li.append(name, status); return li;
    });
    $('device-list').replaceChildren(...rows);
    const services = data.services || {}, stopped = Object.values(services).some(service => service.running === false);
    const servicesKnown = ['shairport-sync','nqptp','pulseaudio','ledfx'].every(unit => services[unit]?.running === true);
    const ledFxUrl = data.ledfx_browser_url || document.querySelector('main').dataset.ledfxUrl;
    let message = '', label = 'Troubleshoot', href = '/status', health = 'Connections ready', state = 'good';
    if (stopped) message = 'A required service is stopped. Open connection details to identify it.';
    else if (engine === false) message = 'LedFX is unreachable. Check that its service is running.';
    else if (pulse === false) message = 'The audio bridge is unavailable. Check PulseAudio and the LedFX input.';
    else if (receiver === false) message = 'AirPlay discovery has not been confirmed. Check the receiver and LAN connection.';
    else if (![receiver,pulse,engine].every(value => value === true) || !servicesKnown || data.diagnostics?.available === false || !streamKnown || !devices) {
      message = 'Some checks are incomplete. Open connection details for the missing results.';
      health = 'Checks incomplete'; state = 'unknown';
    } else if (!devices.length) {
      message = 'Add a lighting device and select an effect in LedFX.'; label = 'Open LedFX'; href = ledFxUrl;
    } else if (offline.length) {
      message = offline.length + ' lighting ' + (offline.length === 1 ? 'device is' : 'devices are') + ' reported offline by LedFX.'; label = 'Open LedFX'; href = ledFxUrl;
    } else if (unchecked.length) {
      message = unchecked.length + ' device ' + (unchecked.length === 1 ? 'status has' : 'statuses have') + ' not been confirmed by LedFX.';
      health = 'Checks incomplete'; state = 'unknown';
    } else if (data.session_action?.state === 'failed') {
      message = 'The last playback action failed. Check the selected outputs or scene.'; label = 'Playback settings'; href = '/config';
    }
    if (message && state !== 'unknown') { health = 'Needs attention'; state = 'attention'; }
    show('health', health, state); attention(message, label, href);
    lastObservation = new Date(); text('updated', 'Updated ' + lastObservation.toLocaleTimeString());
  }
  async function refresh() {
    clearTimeout(timer); $('refresh').disabled = true; text('refresh', 'Checking…');
    try {
      const response = await fetch('/api/status', {signal:AbortSignal.timeout(15000), cache:'no-store'});
      if (!response.ok) throw new Error('Status request failed');
      const data = await response.json();
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Invalid status');
      render(data);
    } catch { unavailable(); }
    finally { $('refresh').disabled = false; text('refresh', 'Refresh ↻'); timer = setTimeout(refresh,10000); }
  }
  $('refresh').addEventListener('click', refresh);
  refresh();
})();
