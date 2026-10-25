const $ = id => document.getElementById(id);
chrome.storage.local.get({backendUrl:'http://127.0.0.1:8000',apiToken:'',imageConsent:false}).then(settings => {
  $('backendUrl').value = settings.backendUrl; $('apiToken').value = settings.apiToken;
  $('imageConsent').checked = settings.imageConsent;
});
$('save').addEventListener('click', async () => {
  try {
    const url = new URL($('backendUrl').value);
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost','127.0.0.1'].includes(url.hostname))) throw new Error('Use HTTPS, or HTTP for localhost.');
    if (url.protocol === 'https:') {
      const granted = await chrome.permissions.request({origins:[`${url.origin}/*`]});
      if (!granted) throw new Error('Backend host permission was declined.');
    }
    await chrome.storage.local.set({backendUrl:url.origin,apiToken:$('apiToken').value,imageConsent:$('imageConsent').checked});
    const status = await chrome.runtime.sendMessage({type:'STATUS'});
    $('message').textContent = status.error ? `Saved; connection failed: ${status.error}` : `Connected: ${status.model}`;
  } catch (error) { $('message').textContent = error.message; }
});
