'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const keys = ['start', 'end'];
  let catalog, receiverBaseline, actionsBaseline, testing = false;
  async function api(path, data) {
    const response = await fetch(path, {method:data ? 'POST' : 'GET', headers:data ? {'Content-Type':'application/json'} : {}, body:data ? JSON.stringify(data) : undefined, signal:AbortSignal.timeout(15000)});
    const result = await response.json();
    if (!response.ok || result.error) throw new Error(result.error || 'The request failed.');
    return result;
  }
  function message(id, text, error = false) { $(id).textContent = text; $(id).dataset.result = error ? 'error' : 'success'; }
  function receiverValue() {
    return {name:$('receiver-name').value, fixed_volume:$('fixed-volume').checked,
      password:$('receiver-password').value, clear_password:$('clear-password').checked};
  }
  function receiverChanged() {
    $('save-receiver').disabled = JSON.stringify(receiverValue()) === receiverBaseline;
    $('effective-name').textContent = 'Appears in AirPlay as “' + ($('receiver-name').value.trim() || $('receiver-name').placeholder) + '”.';
  }
  function receiver(data) {
    $('receiver-name').value = data.name;
    $('receiver-name').placeholder = data.default_name;
    $('fixed-volume').checked = data.fixed_volume;
    $('receiver-password').value = '';
    $('clear-password').checked = false;
    $('clear-password-row').hidden = !data.password_set;
    $('password-help').textContent = data.password_set ? 'A password is saved. Leave this field empty to keep it, or choose removal below.' : 'No password is set. Leave this empty to allow AirPlay connections without a password.';
    receiverBaseline = JSON.stringify(receiverValue()); receiverChanged();
  }
  const outputName = id => catalog.virtual_details?.[id]?.name || id;
  const sceneName = id => catalog.scene_details?.[id]?.name || id;
  function action(key) {
    const option = $(key + '-scenes').selectedOptions[0];
    return {mode:$(key + '-mode').value, all_virtuals:$(key + '-all').checked,
      virtuals:Array.from($(key + '-virtuals').querySelectorAll('.target')).filter(row => row.querySelector('input[type=checkbox]').checked).map(row => ({id:row.querySelector('input[type=checkbox]').value})),
      scenes:option ? JSON.parse(option.dataset.scenes || '[]') : []};
  }
  function values() {
    return {start_enabled:$('start-enabled').checked, end_enabled:$('end-enabled').checked, start_hook:action('start'), end_hook:action('end')};
  }
  function hasTarget(a) { return a.mode === 'scene' ? a.scenes.length > 0 : a.all_virtuals ? catalog.available_virtuals.length > 0 : a.virtuals.length > 0; }
  function update() {
    if (!catalog) return;
    const dirty = JSON.stringify(values()) !== actionsBaseline;
    $('save-actions').disabled = !dirty || testing;
    for (const key of keys) {
      const enabled = $(key + '-enabled').checked, a = action(key), scene = a.mode === 'scene';
      $(key + '-fields').disabled = !enabled || testing;
      $(key + '-toggle').hidden = scene; $(key + '-scene').hidden = !scene;
      for (const row of $(key + '-virtuals').querySelectorAll('.target')) {
        row.querySelector('input[type=checkbox]').disabled = a.all_virtuals;
      }
      const prefix = key === 'start' ? 'Playback starts → ' : 'Playback ends → wait 10 seconds, then ';
      let description = 'do nothing.';
      if (enabled) {
        if (!hasTarget(a)) description = 'choose an output or scene to finish setup.';
        else if (scene) description = 'activate ' + a.scenes.map(sceneName).join(', then ') + '.';
        else description = (key === 'start' ? 'resume saved effects on ' : 'stop sending lighting updates to ') +
          (a.all_virtuals ? 'every output, including future outputs' : a.virtuals.map(v => outputName(v.id)).join(', ')) + '.';
      }
      $(key + '-summary').textContent = prefix + description;
      $(key + '-test').disabled = dirty || testing || !enabled || !hasTarget(a) || !catalog.ledfx_connected;
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
    $('connection-note').textContent = !catalog.ledfx_connected ? 'LedFX is unavailable. Saved choices are retained; reconnect before saving or testing targets.' : dirty ? 'Preview of unsaved changes. Save playback actions before testing.' : 'Saved playback plan. Tests below change lighting output.';
  }
  function hook(key, config) {
    $(key + '-enabled').checked = config.enabled;
    $(key + '-mode').value = config.mode;
    $(key + '-all').checked = config.all_virtuals;
    const selected = new Set(config.virtuals.filter(v => (v.repeats ?? 1) > 0).map(v => v.id));
    for (const id of new Set([...catalog.available_virtuals, ...selected.keys()])) {
      const row = document.createElement('div'); row.className = 'target';
      const label = document.createElement('label'); label.className = 'check';
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = id; checkbox.checked = selected.has(id) || (config.all_virtuals && catalog.available_virtuals.includes(id));
      const text = document.createElement('span'); text.textContent = outputName(id);
      const detail = document.createElement('small'); detail.textContent = id + (!catalog.available_virtuals.includes(id) ? ' · unavailable' : ''); text.append(detail);
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
    $(key + '-all').addEventListener('change', () => {
      if ($(key + '-all').checked) for (const box of $(key + '-virtuals').querySelectorAll('input[type=checkbox]')) box.checked = true;
      update();
    });
    $(key + '-test').addEventListener('click', () => test(key));
  }
  async function test(key) {
    testing = true; update();
    message(key + '-result', 'Queuing saved action…');
    try {
      const queued = await api('/api/actions/test', {hook:key});
      message(key + '-result', 'Running saved action…');
      const deadline = Date.now() + 14000;
      let matched = false;
      while (Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 500));
        const result = await api('/api/actions/test');
        if (result.event?.id !== queued.event.id) continue;
        matched = true;
        if (result.state === 'success') message(key + '-result', 'LedFX accepted the command. Check the lights to confirm the result.');
        else if (result.state === 'superseded') message(key + '-result', 'A newer playback event replaced this test.');
        else if (result.state === 'skipped') message(key + '-result', 'No commands ran. Check the saved action and its targets.', true);
        else message(key + '-result', 'The action failed. Check LedFX and Troubleshooting.', true);
        break;
      }
      if (!matched) message(key + '-result', 'No result received. The test may have been replaced by a playback event; lighting state is unconfirmed.', true);
    } catch (error) { message(key + '-result', error.message, true); }
    finally { testing = false; update(); }
  }
  $('receiver-form').addEventListener('input', receiverChanged);
  $('receiver-form').addEventListener('submit', async event => {
    event.preventDefault(); $('receiver-fields').disabled = true;
    try {
      const result = await api('/api/receiver', receiverValue());
      receiver(result.receiver); message('receiver-result', result.receiver.restart_requested ? 'Saved. The receiver will restart. Reconnect AirPlay if playback stops.' : 'No changes to apply. The receiver was not restarted.');
    } catch (error) { message('receiver-result', error.message, true); }
    finally { $('receiver-fields').disabled = false; receiverChanged(); }
  });
  $('receiver-password').addEventListener('input', () => { $('clear-password').checked = false; receiverChanged(); });
  $('clear-password').addEventListener('change', () => { if ($('clear-password').checked) $('receiver-password').value = ''; receiverChanged(); });
  $('actions-form').addEventListener('input', update);
  $('actions-form').addEventListener('change', update);
  $('actions-form').addEventListener('submit', async event => {
    event.preventDefault();
    const data = values();
    for (const key of keys) if (data[key + '_enabled'] && !hasTarget(data[key + '_hook'])) { message('actions-result', 'Choose an output or scene for the ' + key + ' action.', true); return; }
    $('actions-fields').disabled = true;
    try {
      await api('/api/config', data); actionsBaseline = JSON.stringify(values());
      message('actions-result', 'Playback actions saved. Audio playback was not restarted.');
    } catch (error) { message('actions-result', error.message, true); }
    finally { $('actions-fields').disabled = false; update(); }
  });
  Promise.all([api('/api/receiver'), api('/api/config')]).then(([settings, config]) => {
    catalog = config; receiver(settings); keys.forEach(key => hook(key, config.virtuals.hooks[key]));
    actionsBaseline = JSON.stringify(values());
    $('receiver-fields').disabled = false; $('actions-fields').disabled = false; update();
    $('load-status').textContent = 'Saved settings loaded.';
  }).catch(error => message('load-status', error.message + ' Reload this page to try again.', true));
})();
