const CLOUD_URL = 'https://universal-ai-quiz-solver.vercel.app';
const DEFAULTS = {
  enabled: true, clickMode: false, hoverMode: false, explanations: true,
  highlights: true, autoSelect: false, authorizedPractice: false, autoSolve: false,
  autoSites: [], backendUrl: CLOUD_URL, apiToken: '', imageConsent: false
};
const FILES = [
  'content/site-adapters.js', 'content/question-parser.js',
  'content/question-detector.js', 'content/answer-highlighter.js',
  'content/interaction-handler.js', 'content/content.js'
];
const pending = new Map();

function sitePattern(value) {
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname) throw new Error('Open a regular quiz website first.');
  return `${url.protocol}//${url.hostname}/*`;
}
function scriptId(pattern) {
  let hash = 2166136261;
  for (const char of pattern) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return `uaqs-auto-${(hash >>> 0).toString(16)}`;
}
async function registerSite(value) {
  const pattern = sitePattern(value);
  if (!await chrome.permissions.contains({origins: [pattern]})) throw new Error('Grant access to this quiz site first.');
  const id = scriptId(pattern);
  const existing = await chrome.scripting.getRegisteredContentScripts({ids: [id]});
  if (!existing.length) {
    await chrome.scripting.registerContentScripts([{
      id, matches: [pattern], js: FILES, css: ['styles/overlay.css'],
      runAt: 'document_idle', persistAcrossSessions: true
    }]);
  }
  return {ok: true, pattern};
}
async function unregisterSite(value) {
  const id = scriptId(sitePattern(value));
  const existing = await chrome.scripting.getRegisteredContentScripts({ids: [id]});
  if (existing.length) await chrome.scripting.unregisterContentScripts({ids: [id]});
  return {ok: true};
}
async function unregisterAllSites() {
  const scripts = await chrome.scripting.getRegisteredContentScripts();
  const ids = scripts.filter(script => script.id.startsWith('uaqs-auto-')).map(script => script.id);
  if (ids.length) await chrome.scripting.unregisterContentScripts({ids});
  return {ok: true};
}

async function settings() {
  const value = await chrome.storage.local.get(DEFAULTS);
  if (!value.cloudMigrationDone && /^http:\/\/(localhost|127\.0\.0\.1):8000\/?$/.test(value.backendUrl)) {
    value.backendUrl = CLOUD_URL;
    value.cloudMigrationDone = true;
    await chrome.storage.local.set({backendUrl: CLOUD_URL, cloudMigrationDone: true});
  }
  return value;
}
function baseUrl(value) {
  const url = new URL(value);
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname))) {
    throw new Error('Use HTTPS, or HTTP for localhost only.');
  }
  if (url.protocol === 'http:' && url.hostname === 'localhost') url.hostname = '127.0.0.1';
  return url.origin;
}
async function api(path, method = 'GET', body, requestId) {
  const config = await settings();
  if (!config.apiToken) throw new Error('Configure a backend token in Settings.');
  const controller = new AbortController();
  if (requestId) pending.set(requestId, controller);
  const timer = setTimeout(() => controller.abort(), 55000);
  try {
    const response = await fetch(baseUrl(config.backendUrl) + path, {
      method, signal: controller.signal,
      headers: {'Authorization': `Bearer ${config.apiToken}`, 'Content-Type': 'application/json'},
      ...(body ? {body: JSON.stringify(body)} : {})
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.error || `HTTP ${response.status}`);
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Backend request timed out.');
    if (error instanceof TypeError) throw new Error(`Backend unreachable at ${baseUrl(config.backendUrl)}. Start the Python server.`);
    throw error;
  } finally { clearTimeout(timer); if (requestId) pending.delete(requestId); }
}
async function ensureInjected(tabId) {
  try {
    await chrome.tabs.sendMessage(tabId, {type: 'PING'});
  } catch {
    await chrome.scripting.insertCSS({target: {tabId}, files: ['styles/overlay.css']});
    await chrome.scripting.executeScript({target: {tabId}, files: FILES});
  }
}
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    if (message.type === 'ENSURE') {
      await ensureInjected(message.tabId);
      return {ok: true};
    }
    if (message.type === 'REGISTER_SITE') return registerSite(message.origin);
    if (message.type === 'UNREGISTER_SITE') return unregisterSite(message.origin);
    if (message.type === 'UNREGISTER_ALL_SITES') return unregisterAllSites();
    if (message.type === 'CANCEL') { pending.get(message.requestId)?.abort(); return {ok: true}; }
    if (message.type === 'STATUS') return api('/api/v1/status');
    if (message.type === 'SOLVE') return api('/api/v1/solve', 'POST', message.question, message.requestId);
    if (message.type === 'BATCH') return api('/api/v1/solve/batch', 'POST', {questions: message.questions});
    throw new Error('Unknown message');
  })().then(sendResponse, error => sendResponse({error: error.message}));
  return true;
});
