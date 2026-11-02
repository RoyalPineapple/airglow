'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const units = {'shairport-sync':'AirPlay receiver', nqptp:'AirPlay timing', pulseaudio:'PulseAudio', ledfx:'LedFX'};
  const ledfxUrl = $('main').dataset.ledfxUrl;
  let timer, lastCheck, downloading = false, guidanceKey;
  function text(id, value) { if ($(id).textContent !== value) $(id).textContent = value; }
  function status(id, label, state = 'unknown') { text(id, label); $(id).dataset.state = state; }
  function rows(id, values) {
    $(id).replaceChildren(...values.map(([label, value, state]) => {
      const row = document.createElement('div'), term = document.createElement('dt'), detail = document.createElement('dd');
      term.textContent = label; detail.textContent = value; if (state) detail.dataset.state = state;
      row.append(term, detail); return row;
    }));
  }
  function summary(title, description, state, action) {
    text('check-title', title); text('check-description', description); $('check-summary').dataset.state = state;
    $('recovery-link').hidden = !action;
    if (action) {
      text('recovery-link', action[0]); $('recovery-link').href = action[1];
      if (action[1] === ledfxUrl) { $('recovery-link').target = '_blank'; $('recovery-link').rel = 'noopener'; }
      else { $('recovery-link').removeAttribute('target'); $('recovery-link').removeAttribute('rel'); }
    }
  }
  function guidance(issues) {
    $('recovery-guidance').hidden = !issues.length;
    const key = JSON.stringify(issues);
    if (key === guidanceKey) return;
    guidanceKey = key;
    $('issue-list').replaceChildren(...issues.map(issue => {
      const item = document.createElement('li'); item.textContent = issues.length > 1 ? issue.title || issue.help : issue.help;
      if (issue.action && ($('recovery-link').hidden || issue.action[1] !== $('recovery-link').getAttribute('href'))) {
        const link = document.createElement('a'); link.textContent = issue.action[0]; link.href = issue.action[1];
        if (issue.action[1] === ledfxUrl) { link.target = '_blank'; link.rel = 'noopener'; }
        item.append(link);
      }
      return item;
    }));
    const logUnits = [...new Set(issues.map(issue => issue.unit).filter(Boolean))];
    $('command-label').hidden = !logUnits.length; $('command-row').hidden = !logUnits.length;
    text('log-command', logUnits.length ? `journalctl ${logUnits.map(unit => '-u ' + unit).join(' ')} --since "10 minutes ago"` : ''); text('copy-result', '');
  }
  function render(data) {
    const services = data.services || {}, airplay = data.airplay || {}, audio = data.audio || {};
    const engine = data.ledfx?.connected, pulse = audio.pulseaudio?.available, advertising = airplay.advertising;
    const worker = data.diagnostics?.actions_worker_running, actionState = data.session_action?.state;
    const actionsOff = actionState === 'disabled', actionFailed = ['failed','partial_failure'].includes(actionState);
    const devices = engine === true && data.devices?.connected === true ? Object.values(data.devices.devices || {}) : null;
    const offline = devices?.filter(device => device.online === false) || [], unchecked = devices?.filter(device => typeof device.online !== 'boolean') || [];
    const issues = [];
    const issue = (title, help, unit, action) => issues.push({title,help,unit,action});
    const stopped = key => services[key]?.running === false;
    const serviceRows = Object.entries(units).map(([key,label]) => {
      const running = services[key]?.running;
      return [label, running === true ? 'Running' : running === false ? services[key].state === 'failed' ? 'Failed' : 'Stopped' : 'Not checked', running === true ? 'good' : running === false ? 'attention' : 'unknown'];
    });
    const stoppedCount = serviceRows.filter(row => row[2] === 'attention').length, unknownCount = serviceRows.filter(row => row[2] === 'unknown').length;
    status('services-summary', stoppedCount ? stoppedCount + ' stopped' : unknownCount ? unknownCount + ' not checked' : 'All running', stoppedCount ? 'attention' : unknownCount ? 'unknown' : 'good');
    rows('service-list', serviceRows);

    status('discovery-check', stopped('shairport-sync') ? 'Stopped' : advertising === true ? 'Confirmed' : advertising === false ? 'Not discovered' : 'Not checked', stopped('shairport-sync') || advertising === false ? 'attention' : advertising === true ? 'good' : 'unknown');
    text('discovery-description', advertising === true ? 'AirPlay and RAOP broadcast names match' : 'AirPlay and RAOP broadcast names');
    status('bridge-check', stopped('pulseaudio') ? 'Stopped' : pulse === true ? 'Available' : pulse === false ? 'Unavailable' : 'Not checked', stopped('pulseaudio') || pulse === false ? 'attention' : pulse === true ? 'good' : 'unknown');
    status('ledfx-check', stopped('ledfx') ? 'Stopped' : engine === true ? 'Reachable' : engine === false ? 'Unreachable' : 'Not checked', stopped('ledfx') || engine === false ? 'attention' : engine === true ? 'good' : 'unknown');
    status('devices-check', !devices ? 'Not checked' : !devices.length ? 'Not configured' : offline.length ? offline.length + ' reported offline' : unchecked.length ? unchecked.length + ' not checked' : devices.length + ' reported online', !devices || unchecked.length && !offline.length ? 'unknown' : !devices.length || offline.length ? 'attention' : 'good');
    status('actions-check', actionsOff ? 'Off' : worker === false ? 'Unavailable' : actionFailed ? 'Needs attention' : worker === true ? 'Running' : 'Not checked', actionsOff ? 'idle' : worker === false || actionFailed ? 'attention' : worker === true ? 'good' : 'unknown');

    if (data.configuration_error) issue('Saved configuration needs recovery', 'Restore a valid Airglow backup. Current saved settings could not be validated.', null, ['Backup & restore','/config#backup']);
    for (const [key,label] of Object.entries(units)) {
      if (stopped(key)) issue(label + ' is stopped', 'Check the ' + label + ' service and its recent logs.', key, ['View services','#native-services']);
    }
    if (airplay.configuration_state === 'failed') issue('Receiver settings could not be applied', 'Check the receiver logs, then retry the saved settings.', 'shairport-sync', ['AirPlay settings','/config#receiver']);
    else if (airplay.configuration_state === 'mismatch') issue('Receiver names do not match', 'Compare the saved and broadcast names below, then retry the saved settings.', 'shairport-sync', ['AirPlay settings','/config#receiver']);
    else if (airplay.configuration_state === 'pending') issue('Receiver settings are awaiting confirmation', 'A restart may still be in progress. Refresh checks; if this continues, retry the saved settings.', 'shairport-sync', ['AirPlay settings','/config#receiver']);
    if (advertising === false && !stopped('shairport-sync') && !data.configuration_error && !['mismatch','pending','failed'].includes(airplay.configuration_state)) issue('AirPlay discovery is not confirmed', 'Check the receiver, its configured network interface and LAN discovery.', 'shairport-sync', ['AirPlay settings','/config#receiver']);
    if (pulse === false && !stopped('pulseaudio')) issue('Audio bridge is unavailable', 'Check the PulseAudio service and its recent logs.', 'pulseaudio', ['View services','#native-services']);
    if (engine === false && !stopped('ledfx')) issue('LedFX is unreachable', 'Check the LedFX service and its recent logs.', 'ledfx', ['Open LedFX',ledfxUrl]);
    if (devices && !devices.length) issue('Lighting devices are not configured', 'Add a device and select an effect in LedFX.', null, ['Open LedFX',ledfxUrl]);
    else if (offline.length) issue(offline.length + (offline.length === 1 ? ' device is reported offline' : ' devices are reported offline'), 'LedFX reports ' + offline.slice(0,3).map(device => device.name || 'an unnamed device').join(', ') + ' offline. Check device settings and network connectivity in LedFX.', 'ledfx', ['Open LedFX',ledfxUrl]);
    if (!actionsOff && worker === false) issue('Playback action worker is unavailable', 'Check the action worker. Its failure does not require changing the audio receiver.', 'airglow-actions', ['Playback actions','/config#playback']);
    else if (!actionsOff && actionFailed) issue(actionState === 'partial_failure' ? 'Some playback commands failed' : 'A playback action failed', 'Check the selected outputs or scene in LedFX, then test the action again.', 'airglow-actions', ['Playback actions','/config#playback']);

    const settingLabels = {applied:'Applied · broadcasts confirmed', pending:'Awaiting confirmation', mismatch:'Broadcast names differ', failed:'Apply failed', unknown:'Not checked'};
    const applied = airplay.configuration_state === 'applied';
    const names = service => airplay.observed_names?.[service]?.join(', ') || 'Not confirmed';
    status('receiver-summary', settingLabels[airplay.configuration_state] || 'Not checked', applied ? 'good' : ['pending','mismatch','failed'].includes(airplay.configuration_state) ? 'attention' : 'unknown');
    const connected = audio.shairport_connected, corked = audio.shairport_corked;
    const stream = connected === false ? 'No active stream' : connected === true && corked === false ? 'Active' : connected === true && corked === true ? 'Inactive · connected' : 'Not checked';
    rows('receiver-list', [['Saved AirPlay name', airplay.desired_name || 'Not checked'], ['AirPlay broadcast',names('_airplay._tcp')], ['RAOP broadcast',names('_raop._tcp')], ['Receiver stream',stream],
      ...[['shairport','Shairport Sync'],['nqptp','NQPTP'],['pulseaudio','PulseAudio'],['ledfx','LedFX']].map(([key,label]) => [label + ' version', data.release?.versions?.[key] || 'Not reported'])]);
    const incomplete = !devices || unchecked.length > 0 || unknownCount > 0 || data.diagnostics?.available !== true || ![advertising,pulse,engine].every(value => typeof value === 'boolean') || !applied || !actionsOff && typeof worker !== 'boolean';
    if (issues.length) {
      const receiverAvailable = advertising === true && pulse === true && services['shairport-sync']?.running === true && services.nqptp?.running === true;
      const description = issues.length > 1 ? 'Start with the first issue below. Other results remain visible.' : issues[0].title === 'LedFX is unreachable' && receiverAvailable ? 'The audio receiver is available. Check LedFX before changing AirPlay settings.' : issues[0].help;
      summary(issues.length === 1 ? issues[0].title : issues.length + ' issues need attention', description, 'attention', issues[0].action);
    } else if (incomplete) {
      summary('Some checks are incomplete', 'Missing observations are not confirmation that the connection works.', 'unknown', ['View services','#native-services']);
      issue('Incomplete observations', engine === true && (!devices || unchecked.length) ? 'LedFX has not confirmed every device status. Check its device details before assuming output works.' : 'Refresh checks. If results remain unavailable, inspect the Airglow service logs.', engine === true && (!devices || unchecked.length) ? 'ledfx' : 'airglow', engine === true && (!devices || unchecked.length) ? ['Open LedFX',ledfxUrl] : null);
    } else summary('Connections confirmed', 'Services and connection checks passed. Physical lighting output is not verified.', 'good');
    guidance(issues);
    lastCheck = new Date(); text('checked-at', 'Checked ' + lastCheck.toLocaleTimeString()); text('updated-at', 'Updated ' + lastCheck.toLocaleTimeString());
  }
  function unavailable() {
    for (const id of ['discovery-check','bridge-check','ledfx-check','actions-check','devices-check','services-summary','receiver-summary']) status(id, 'Not checked');
    text('discovery-description', 'AirPlay and RAOP broadcast names');
    rows('service-list', Object.values(units).map(label => [label,'Not checked']));
    rows('receiver-list', [['Receiver observations','Not checked'],['Versions','Not checked']]);
    summary('Checks unavailable', lastCheck ? 'Previous results are stale. Try refreshing or read the Airglow service logs.' : 'No current connection results are available. Try refreshing or read the Airglow service logs.', 'unknown');
    guidance([{help:'Check the Airglow web service if diagnostics remain unavailable.',unit:'airglow'}]);
    text('checked-at', 'Update failed'); text('updated-at', lastCheck ? 'Last successful check ' + lastCheck.toLocaleTimeString() + ' · stale' : 'No successful checks');
  }
  async function refresh() {
    clearTimeout(timer); $('refresh-checks').disabled = true; text('refresh-checks', 'Checking…');
    try {
      const response = await fetch('/api/status', {cache:'no-store',signal:AbortSignal.timeout(15000)});
      if (!response.ok) throw new Error('Status unavailable');
      const data = await response.json();
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Invalid observations');
      render(data);
    } catch { unavailable(); }
    finally { $('refresh-checks').disabled = false; text('refresh-checks', 'Refresh checks'); timer = setTimeout(refresh, 10000); }
  }
  $('refresh-checks').addEventListener('click', refresh);
  document.addEventListener('click', event => {
    if (event.target.closest('a[href="#native-services"]')) {
      $('native-services').open = true; $('native-services').querySelector('summary').focus();
    }
  });
  $('copy-command').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText($('log-command').textContent); text('copy-result', 'Copied');
    } catch {
      const selection = window.getSelection(), range = document.createRange(); range.selectNodeContents($('log-command'));
      selection.removeAllRanges(); selection.addRange(range); text('copy-result', 'Command selected. Copy it with your keyboard or selection menu.');
    }
  });
  $('download-diagnostics').addEventListener('click', async event => {
    event.preventDefault(); if (downloading) return;
    downloading = true; $('download-diagnostics').setAttribute('aria-disabled','true'); text('download-diagnostics','Downloading…'); text('download-result','');
    try {
      const response = await fetch('/api/diagnostics/download', {cache:'no-store',signal:AbortSignal.timeout(15000)});
      if (!response.ok) throw new Error('Download failed');
      const blob = new Blob([JSON.stringify(await response.json(), null, 2)], {type:'application/json'});
      const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = 'airglow-diagnostics.json';
      document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { text('download-result','Diagnostics could not be downloaded. Refresh checks or read the service logs on the host.'); }
    finally { downloading = false; $('download-diagnostics').removeAttribute('aria-disabled'); text('download-diagnostics','Download diagnostics'); }
  });
  refresh();
})();
