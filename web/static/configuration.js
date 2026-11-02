'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const keys = ['start', 'end'];
  const tabs = ['playback', 'receiver', 'backup'];
  let catalog, receiverBaseline, actionsBaseline, receiverRevision, actionsRevision, testing = false;
  async function api(path, data) {
    const response = await fetch(path, {method:data ? 'POST' : 'GET', headers:data ? {'Content-Type':'application/json'} : {}, body:data ? JSON.stringify(data) : undefined, signal:AbortSignal.timeout(15000)});
    const result = await response.json();
    if (!response.ok || result.error) throw new Error(result.error || 'The request failed.');
    return result;
  }
  function message(id, text, error = false) { $(id).textContent = text; $(id).dataset.result = error ? 'error' : 'success'; }
  function dirtyStatus(id, dirty) {
    if ($(id).dataset.result === 'error') return;
    if (dirty || $(id).textContent === 'Unsaved changes') {
      $(id).textContent = dirty ? 'Unsaved changes' : 'No unsaved changes';
      delete $(id).dataset.result;
    }
  }
  function receiverValue() {
    return {name:$('receiver-name').value, fixed_volume:$('fixed-volume').checked,
      password:$('receiver-password').value, clear_password:$('clear-password').checked, idle_timeout:Number($('idle-timeout').value)};
  }
  function receiverChanged() {
    const dirty = JSON.stringify(receiverValue()) !== receiverBaseline;
    $('save-receiver').disabled = !dirty;
    if (dirty) $('retry-receiver').hidden = true;
    $('discard-receiver').hidden = !dirty;
    $('fixed-volume-label').textContent = $('fixed-volume').checked ? 'Enabled' : 'Disabled';
    dirtyStatus('receiver-result', dirty);
    $('effective-name').textContent = 'Broadcast name after saving: “' + ($('receiver-name').value.trim() || $('receiver-name').placeholder) + '”.';
  }
  function receiver(data) {
    receiverRevision = data.revision;
    $('receiver-name').value = data.name;
    $('receiver-name').placeholder = data.default_name;
    $('fixed-volume').checked = data.fixed_volume;
    $('idle-timeout').value = data.idle_timeout ?? 10;
    $('receiver-password').value = '';
    $('clear-password').checked = false;
    $('clear-password-row').hidden = !data.password_set;
    $('password-help').textContent = data.password_set ? 'A password is saved. Leave this field empty to keep it, or choose removal below.' : 'No password is set. Leave this empty to allow AirPlay connections without a password.';
    receiverBaseline = JSON.stringify(receiverValue()); receiverChanged();
  }
  const outputName = id => catalog.virtual_details?.[id]?.name || id;
  const sceneName = id => catalog.scene_details?.[id]?.name || id;
  const mode = key => document.querySelector('input[name="' + key + '-mode"]:checked').value;
  function setMode(key, value) { $(key + '-mode-' + value).checked = true; }
  function action(key) {
    const option = $(key + '-scenes').selectedOptions[0];
    return {mode:mode(key), all_virtuals:$(key + '-all').checked,
      virtuals:Array.from($(key + '-virtuals').querySelectorAll('.target')).filter(row => row.querySelector('input[type=checkbox]').checked).map(row => ({id:row.querySelector('input[type=checkbox]').value})),
      scenes:option ? JSON.parse(option.dataset.scenes || '[]') : []};
  }
  function values() {
    return {start_enabled:$('start-enabled').checked, end_enabled:$('end-enabled').checked, start_hook:action('start'), end_hook:action('end')};
  }
  function hasTarget(a) { return a.mode === 'scene' ? a.scenes.length > 0 : a.all_virtuals ? true : a.virtuals.length > 0; }
  function update() {
    if (!catalog) return;
    const dirty = JSON.stringify(values()) !== actionsBaseline;
    $('save-actions').disabled = !dirty || testing;
    $('discard-actions').hidden = !dirty;
    dirtyStatus('actions-result', dirty);
    for (const key of keys) {
      const enabled = $(key + '-enabled').checked, a = action(key), scene = a.mode === 'scene';
      $(key + '-fields').disabled = !enabled || testing;
      $(key + '-toggle').hidden = scene; $(key + '-scene').hidden = !scene;
      for (const row of $(key + '-virtuals').querySelectorAll('.target')) {
        row.querySelector('input[type=checkbox]').disabled = a.all_virtuals;
      }
      $(key + '-enabled-label').textContent = enabled ? 'On' : 'Off';
      $(key + '-selection').textContent = a.all_virtuals ? 'All outputs (' + catalog.available_virtuals.length + ')' : a.virtuals.length === 1 ? outputName(a.virtuals[0].id) : a.virtuals.length ? a.virtuals.length + ' outputs selected' : 'Choose outputs…';
      $(key + '-scope').textContent = a.all_virtuals ? 'Includes newly added outputs' : 'Only the selected outputs';
      $(key + '-test').disabled = testing || !enabled || !hasTarget(a) || !catalog.ledfx_connected;
      const previews = [];
      for (const id of a.scenes) {
        const sceneData = catalog.scene_details?.[id];
        if (!sceneData) { previews.push(sceneName(id) + ': unavailable'); continue; }
        for (const [vid, cfg] of Object.entries(sceneData.virtuals || {})) {
          const kind = cfg.action || (cfg.type ? 'activate' : 'ignore');
          const text = {ignore:'leave unchanged', stop:'clear effect and stop', forceblack:'keep sending black', activate:'apply ' + (cfg.type || 'effect') + (cfg.preset ? ' / ' + cfg.preset : '')}[kind] || 'unknown action';
          previews.push(outputName(vid) + ': ' + text);
        }
      }
      $(key + '-scene-preview').textContent = previews.join(' · ');
      $(key + '-scene-help').textContent = a.scenes.length > 1 ? 'Your existing scene sequence is preserved. Choosing one scene replaces that sequence.' : catalog.available_scenes.length ? 'This scene controls only the outputs and actions saved in LedFX.' : 'No saved scenes. Create one in LedFX, then reload this page.';
    }
    $('connection-note').hidden = catalog.ledfx_connected;
    $('connection-note').textContent = !catalog.ledfx_connected ? 'LedFX unavailable. Saved choices are retained; reconnect before testing.' : '';
  }
  function hook(key, config) {
    $(key + '-virtuals').replaceChildren(); $(key + '-scenes').replaceChildren();
    $(key + '-enabled').checked = config.enabled;
    setMode(key, config.mode);
    $(key + '-all').checked = config.all_virtuals;
    const selected = new Set(config.virtuals.filter(v => (v.repeats ?? 1) > 0).map(v => v.id));
    for (const id of new Set([...catalog.available_virtuals, ...selected.keys()])) {
      const row = document.createElement('div'); row.className = 'target';
      const label = document.createElement('label'); label.className = 'check';
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = id; checkbox.checked = selected.has(id) || (config.all_virtuals && catalog.available_virtuals.includes(id));
      const text = document.createElement('span'); text.textContent = outputName(id);
      const detail = document.createElement('small'); detail.textContent = 'Unavailable'; if (!catalog.available_virtuals.includes(id)) text.append(detail);
      label.append(checkbox, text); row.append(label);
      $(key + '-virtuals').append(row);
    }
    if (!$(key + '-virtuals').children.length) $(key + '-virtuals').textContent = 'No outputs available. Configure an output in LedFX first.';
    function option(label, ids) { const opt = document.createElement('option'); opt.textContent = label; opt.dataset.scenes = JSON.stringify(ids); $(key + '-scenes').append(opt); return opt; }
    option('Choose a scene…', []);
    if (config.scenes.length > 1) option('Keep saved sequence: ' + config.scenes.map(sceneName).join(' → '), config.scenes).selected = true;
    for (const id of new Set([...catalog.available_scenes, ...config.scenes])) {
      const opt = option(sceneName(id) + (catalog.available_scenes.includes(id) ? '' : ' · unavailable'), [id]);
      if (config.scenes.length === 1 && config.scenes[0] === id) opt.selected = true;
    }
  }
  for (const key of keys) {
    $(key + '-all').addEventListener('change', () => {
      if ($(key + '-all').checked) for (const box of $(key + '-virtuals').querySelectorAll('input[type=checkbox]')) box.checked = true;
      update();
    });
    $(key + '-test').addEventListener('click', () => test(key));
  }
  async function test(key) {
    testing = true; keys.forEach(k => $(k + '-picker').open = false); update();
    message(key + '-result', 'Queuing…');
    try {
      const queued = await api('/api/actions/test', {hook:key, settings:action(key)});
      message(key + '-result', 'Running…');
      const deadline = Date.now() + 14000;
      let matched = false;
      while (Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 500));
        const result = await api('/api/actions/test');
        if (result.event?.id !== queued.event.id) continue;
        matched = true;
        if (result.state === 'success') message(key + '-result', 'Command accepted · just now');
        else if (result.state === 'superseded') message(key + '-result', 'A newer playback event replaced this test.');
        else if (result.state === 'skipped') message(key + '-result', 'No commands ran. Check the saved action and its targets.', true);
        else message(key + '-result', result.message || (result.state === 'partial_failure' ? 'Some commands failed. Check the selected outputs in LedFX.' : 'The action failed. Check LedFX and Troubleshooting.'), true);
        break;
      }
      if (!matched) message(key + '-result', 'No result received. The test may have been replaced by a playback event; lighting state is unconfirmed.', true);
    } catch (error) { message(key + '-result', error.message, true); }
    finally { testing = false; update(); }
  }
  $('receiver-form').addEventListener('input', () => { delete $('receiver-result').dataset.result; receiverChanged(); });
  $('receiver-form').addEventListener('submit', async event => {
    event.preventDefault(); $('receiver-fields').disabled = true;
    try {
      const result = await api('/api/receiver', {...receiverValue(), revision:receiverRevision});
      receiver(result.receiver); message('receiver-result', result.receiver.restart_requested ? 'Saved. Restart requested; checking the broadcast…' : 'Saved. Checking the broadcast…');
      confirmReceiver();
    } catch (error) { message('receiver-result', error.message, true); }
    finally { $('receiver-fields').disabled = false; receiverChanged(); }
  });
  $('receiver-password').addEventListener('input', () => { $('clear-password').checked = false; receiverChanged(); });
  $('clear-password').addEventListener('change', () => { if ($('clear-password').checked) $('receiver-password').value = ''; receiverChanged(); });
  for (const event of ['input', 'change']) $('actions-form').addEventListener(event, () => { delete $('actions-result').dataset.result; update(); });
  $('actions-form').addEventListener('submit', async event => {
    event.preventDefault();
    const data = values();
    for (const key of keys) if (data[key + '_enabled'] && !hasTarget(data[key + '_hook'])) { message('actions-result', 'Choose an output or scene for the ' + key + ' action.', true); return; }
    $('actions-fields').disabled = true;
    try {
      const result = await api('/api/config', {...data, revision:actionsRevision}); actionsRevision = result.revision; actionsBaseline = JSON.stringify(values());
      message('actions-result', 'Saved');
    } catch (error) { message('actions-result', error.message, true); }
    finally { $('actions-fields').disabled = false; update(); }
  });
  function showTab(key, focus = false) {
    keys.forEach(name => $(name + '-picker').open = false);
    for (const name of tabs) {
      const selected = name === key;
      $(name + '-tab').setAttribute('aria-selected', String(selected));
      $(name + '-tab').tabIndex = selected ? 0 : -1;
      $(name + '-panel').hidden = !selected;
    }
    if (focus) $(key + '-tab').focus();
  }
  for (const key of tabs) {
    $(key + '-tab').addEventListener('click', () => showTab(key));
    $(key + '-tab').addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const index = tabs.indexOf(key);
      showTab(event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[tabs.length - 1] : tabs[(index + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length], true);
    });
  }
  $('discard-actions').addEventListener('click', () => {
    const data = JSON.parse(actionsBaseline);
    for (const key of keys) {
      const hook = data[key + '_hook'];
      $(key + '-enabled').checked = data[key + '_enabled'];
      setMode(key, hook.mode);
      $(key + '-all').checked = hook.all_virtuals;
      const selected = new Set(hook.virtuals.map(v => v.id));
      for (const input of $(key + '-virtuals').querySelectorAll('input')) input.checked = selected.has(input.value);
      for (const option of $(key + '-scenes').options) option.selected = JSON.stringify(JSON.parse(option.dataset.scenes || '[]')) === JSON.stringify(hook.scenes);
    }
    $('actions-result').textContent = 'No unsaved changes';
    delete $('actions-result').dataset.result;
    keys.forEach(key => $(key + '-picker').open = false);
    update();
  });
  $('discard-receiver').addEventListener('click', () => {
    const data = JSON.parse(receiverBaseline);
    $('receiver-name').value = data.name;
    $('fixed-volume').checked = data.fixed_volume;
    $('idle-timeout').value = data.idle_timeout ?? 10;
    $('receiver-password').value = data.password;
    $('clear-password').checked = data.clear_password;
    $('receiver-result').textContent = 'No unsaved changes';
    delete $('receiver-result').dataset.result;
    receiverChanged();
  });
  let restoreCandidate = null, restoreSelection = 0;
  $('backup-file').addEventListener('change', async () => {
    const selection = ++restoreSelection;
    restoreCandidate = null; $('restore-review').hidden = true;
    $('backup-result').textContent = '';
    const file = $('backup-file').files[0];
    if (!file) return;
    message('backup-result', 'Checking configuration…');
    try {
      if (file.size > 1024 * 1024) throw new Error('Configuration files must be smaller than 1 MB.');
      const candidate = JSON.parse(await file.text());
      const preview = await api('/api/settings/restore', {config:candidate, preview:true});
      if (selection !== restoreSelection) return;
      const rows = [ ['Receiver', preview.receiver.effective_name],
        ['Fixed audio level', preview.receiver.fixed_volume ? 'Enabled' : 'Disabled'],
        ['AirPlay password', preview.receiver.password_set ? 'Included' : 'Not set'],
        ['Idle delay', preview.receiver.idle_timeout + ' seconds'] ];
      for (const key of keys) {
        const hook = preview.hooks[key];
        rows.push([key === 'start' ? 'Playback starts' : 'Playback ends', !hook.enabled ? 'Off' : hook.mode === 'scene' ? 'Scenes: ' + hook.scenes.join(', ') : (key === 'start' ? 'Resume effects · ' : 'Stop output · ') + (hook.all_virtuals ? 'All current and future outputs' : hook.output_count + ' selected outputs')]);
      }
      $('restore-summary').replaceChildren(...rows.map(([name,value]) => {
        const row = document.createElement('div'), term = document.createElement('dt'), detail = document.createElement('dd');
        term.textContent = name; detail.textContent = value; row.append(term,detail); return row;
      }));
      restoreCandidate = candidate; $('restore-review').hidden = false;
      message('backup-result', 'Valid configuration. Review the settings before restoring.');
    } catch (error) { if (selection !== restoreSelection) return; message('backup-result', error instanceof SyntaxError ? 'This file is not valid JSON.' : error.message, true); }
  });
  $('restore-config').addEventListener('click', async () => {
    if (!restoreCandidate) return;
    $('restore-config').disabled = true; $('backup-file').disabled = true;
    try {
      const result = await api('/api/settings/restore', {config:restoreCandidate});
      restoreCandidate = null;
      message('backup-result', result.restart_requested ? 'Configuration restored. AirPlay restart requested. Reloading…' : 'Configuration restored. Reloading…');
      setTimeout(() => window.location.reload(), 1200);
    } catch (error) { message('backup-result', error.message, true); $('restore-config').disabled = false; $('backup-file').disabled = false; }
  });
  async function confirmReceiver() {
    $('retry-receiver').hidden = true;
    for (let attempt = 0; attempt < 8; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 1500));
      try {
        const status = await api('/api/status');
        if (JSON.stringify(receiverValue()) !== receiverBaseline) return;
        if (status.airplay?.configuration_state === 'applied' && status.airplay.revision === receiverRevision) { message('receiver-result', 'Applied · broadcast confirmed'); return; }
      } catch { break; }
    }
    if (JSON.stringify(receiverValue()) !== receiverBaseline || $('receiver-result').dataset.result === 'error') return;
    $('retry-receiver').hidden = false;
    message('receiver-result', 'Saved; application has not been confirmed. Check Troubleshooting.', true);
  }
  $('retry-receiver').addEventListener('click', async () => {
    $('retry-receiver').disabled = true;
    try {
      await api('/api/shairport/restart', {});
      message('receiver-result', 'Restart requested; checking the broadcast…');
      confirmReceiver();
    } catch (error) { message('receiver-result', error.message, true); }
    finally { $('retry-receiver').disabled = false; }
  });
  api('/api/receiver').then(settings => {
    receiver(settings); $('receiver-fields').disabled = false; confirmReceiver();
  }).catch(error => message('receiver-result', error.message, true));
  api('/api/config?catalog=0').then(async config => {
    catalog = config; actionsRevision = config.revision;
    keys.forEach(key => hook(key, config.virtuals.hooks[key]));
    actionsBaseline = JSON.stringify(values());
    $('actions-fields').disabled = false; update(); $('load-status').hidden = true;
    try {
      const details = await api('/api/catalog');
      const draft = values(), dirty = JSON.stringify(draft) !== actionsBaseline;
      catalog = details;
      keys.forEach(key => hook(key, {...draft[key + '_hook'], enabled:draft[key + '_enabled']}));
      if (!dirty) actionsBaseline = JSON.stringify(values());
      $('engine-state').textContent = details.ledfx_connected ? 'LedFX connected' : 'LedFX unavailable';
      $('engine-state').dataset.connected = String(details.ledfx_connected); update();
    } catch (error) { message('connection-note', 'LedFX catalog unavailable. Saved settings can still be edited.', true); $('connection-note').hidden = false; }
  }).catch(error => message('load-status', error.message + ' Use Backup to restore a valid configuration.', true));
})();
