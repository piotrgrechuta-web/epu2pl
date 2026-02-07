const API = 'http://127.0.0.1:8765';

const ids = [
  'provider','model','input_epub','output_epub','prompt','glossary','cache','ollama_host','google_api_key',
  'source_lang','target_lang','timeout','attempts','backoff','batch_max_segs','batch_max_chars','sleep',
  'temperature','num_ctx','num_predict','tags','use_cache','use_glossary'
];

const verEl = document.getElementById('ver');
const msgEl = document.getElementById('msg');
const statusEl = document.getElementById('status');
const logEl = document.getElementById('log');

verEl.textContent = `${window.appInfo.name} v${window.appInfo.version}`;

function val(id) {
  const el = document.getElementById(id);
  if (el.type === 'checkbox') return !!el.checked;
  return el.value;
}

function setVal(id, v) {
  const el = document.getElementById(id);
  if (el.type === 'checkbox') el.checked = !!v;
  else el.value = v ?? '';
}

function collectState() {
  const out = {};
  for (const id of ids) out[id] = val(id);
  out.debug_dir = 'debug';
  out.checkpoint = '0';
  out.tm_db = 'translator_studio.db';
  out.tm_project_id = null;
  return out;
}

async function api(path, opts = {}) {
  const r = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  const body = await r.text();
  let data = {};
  try { data = JSON.parse(body); } catch {}
  if (!r.ok) {
    throw new Error(data.detail || body || `HTTP ${r.status}`);
  }
  return data;
}

function message(text, isErr = false) {
  msgEl.textContent = text;
  msgEl.className = isErr ? 'msg err' : 'msg ok';
}

async function loadConfig() {
  try {
    const cfg = await api('/config');
    for (const id of ids) setVal(id, cfg[id]);
    message('Config załadowany.');
  } catch (e) {
    message(`Błąd load config: ${e.message}`, true);
  }
}

async function saveConfig() {
  try {
    await api('/config', { method: 'POST', body: JSON.stringify(collectState()) });
    message('Config zapisany.');
  } catch (e) {
    message(`Błąd save config: ${e.message}`, true);
  }
}

async function startRun() {
  try {
    await api('/run/start', { method: 'POST', body: JSON.stringify({ state: collectState() }) });
    message('Start run OK.');
  } catch (e) {
    message(`Błąd start: ${e.message}`, true);
  }
}

async function validateRun() {
  const epub = val('output_epub') || val('input_epub');
  if (!epub) {
    message('Podaj output_epub lub input_epub.', true);
    return;
  }
  try {
    await api('/run/validate', { method: 'POST', body: JSON.stringify({ epub_path: epub, tags: val('tags') }) });
    message('Start walidacji OK.');
  } catch (e) {
    message(`Błąd walidacji: ${e.message}`, true);
  }
}

async function stopRun() {
  try {
    await api('/run/stop', { method: 'POST', body: '{}' });
    message('Stop wysłany.');
  } catch (e) {
    message(`Błąd stop: ${e.message}`, true);
  }
}

async function fetchModels() {
  try {
    const provider = val('provider');
    if (provider === 'ollama') {
      const data = await api(`/models/ollama?host=${encodeURIComponent(val('ollama_host'))}`);
      if (data.models && data.models.length) {
        setVal('model', data.models[0]);
      }
      message(`Modele ollama: ${data.models.length}`);
      return;
    }
    const key = val('google_api_key');
    const data = await api(`/models/google?api_key=${encodeURIComponent(key)}`);
    if (data.models && data.models.length) {
      setVal('model', data.models[0]);
    }
    message(`Modele google: ${data.models.length}`);
  } catch (e) {
    message(`Błąd modeli: ${e.message}`, true);
  }
}

async function pollStatus() {
  try {
    const s = await api('/run/status');
    statusEl.textContent = `Status: ${s.running ? 'RUNNING' : 'IDLE'} | mode=${s.mode} | exit=${s.exit_code ?? '--'}`;
    logEl.textContent = s.log || '';
    logEl.scrollTop = logEl.scrollHeight;
  } catch (e) {
    statusEl.textContent = `Status: backend offline (${e.message})`;
  }
}

document.getElementById('save-btn').addEventListener('click', saveConfig);
document.getElementById('start-btn').addEventListener('click', startRun);
document.getElementById('validate-btn').addEventListener('click', validateRun);
document.getElementById('stop-btn').addEventListener('click', stopRun);
document.getElementById('models-btn').addEventListener('click', fetchModels);

loadConfig();
pollStatus();
setInterval(pollStatus, 1200);
