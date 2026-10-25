const keys = ['enabled','clickMode','hoverMode','explanations','highlights','authorizedPractice','autoSelect'];
const defaults = {enabled:true,clickMode:false,hoverMode:false,explanations:true,highlights:true,authorizedPractice:false,autoSelect:false,autoSolve:false,autoSites:[]};
const $ = id => document.getElementById(id);
async function activeTab() { return (await chrome.tabs.query({active:true,currentWindow:true}))[0]; }
function sitePattern(tab) {
  if (!tab?.url) return null;
  const url = new URL(tab.url);
  return ['http:','https:'].includes(url.protocol) ? `${url.protocol}//${url.hostname}/*` : null;
}
async function ensure() {
  const tab = await activeTab();
  if (!sitePattern(tab)) throw new Error('Open the quiz website tab, then open this popup. Chrome internal pages cannot be scanned.');
  const result = await chrome.runtime.sendMessage({type:'ENSURE',tabId:tab.id});
  if (result.error) throw new Error(result.error);
  return tab;
}
async function init() {
  const settings = await chrome.storage.local.get(defaults);
  const tab = await activeTab();
  const pattern = sitePattern(tab);
  $('autoSite').disabled = !pattern;
  $('autoSite').checked = Boolean(pattern && settings.autoSites.includes(pattern));
  keys.forEach(key => {
    $(key).checked = settings[key];
    $(key).addEventListener('change', async () => {
      if (key === 'autoSelect' && $(key).checked && !$('authorizedPractice').checked) {
        $(key).checked = false; $('message').textContent = 'Confirm authorized practice first.'; return;
      }
      if (key === 'authorizedPractice' && !$(key).checked) {
        $('autoSelect').checked = false; $('autoSite').checked = false;
        await chrome.runtime.sendMessage({type:'UNREGISTER_ALL_SITES'});
        await chrome.storage.local.set({autoSelect:false,autoSolve:false,autoSites:[]});
      }
      await chrome.storage.local.set({[key]:$(key).checked});
    });
  });
  $('autoSite').addEventListener('change', async () => {
    const checked = $('autoSite').checked;
    try {
      if (!pattern) throw new Error('Open a quiz website tab first.');
      const current = await chrome.storage.local.get(defaults);
      if (checked) {
        if (!$('authorizedPractice').checked) throw new Error('Confirm authorized practice first.');
        const granted = await chrome.permissions.request({origins:[pattern]});
        if (!granted) throw new Error('Site access was not granted.');
        const registration = await chrome.runtime.sendMessage({type:'REGISTER_SITE',origin:tab.url});
        if (registration.error) throw new Error(registration.error);
        $('autoSelect').checked = true;
        await chrome.storage.local.set({autoSites:[...new Set([...current.autoSites,pattern])],autoSolve:true,autoSelect:true});
        await ensure();
        $('message').textContent = 'Automatic solving enabled for this site. Reload the quiz page to test it.';
      } else {
        const result = await chrome.runtime.sendMessage({type:'UNREGISTER_SITE',origin:tab.url});
        if (result.error) throw new Error(result.error);
        const sites = current.autoSites.filter(site => site !== pattern);
        await chrome.storage.local.set({autoSites:sites,autoSolve:sites.length > 0});
        $('message').textContent = 'Automatic solving disabled for this site.';
      }
    } catch (error) { $('autoSite').checked = !checked; $('message').textContent = error.message; }
  });
  try { await ensure(); } catch (error) { $('message').textContent = `Page access: ${error.message}`; }
  const status = await chrome.runtime.sendMessage({type:'STATUS'});
  $('status').textContent = status.error ? `Offline: ${status.error}` : `${status.status} · ${status.model}`;
}
$('solveAll').addEventListener('click', async () => {
  $('solveAll').disabled = true; $('message').textContent = 'Solving…';
  try {
    const tab = await ensure();
    const result = await chrome.tabs.sendMessage(tab.id,{type:'SOLVE_ALL'});
    $('message').textContent = result.error || `Processed ${result.count} questions; ${result.errors} errors.`;
  } catch (error) { $('message').textContent = error.message; }
  finally { $('solveAll').disabled = false; }
});
$('clear').addEventListener('click', async () => {
  try { const tab = await ensure(); await chrome.tabs.sendMessage(tab.id,{type:'CLEAR'}); $('message').textContent = 'Highlights cleared.'; }
  catch (error) { $('message').textContent = error.message; }
});
$('settings').addEventListener('click', () => chrome.runtime.openOptionsPage());
init().catch(error => { $('status').textContent = error.message; });
