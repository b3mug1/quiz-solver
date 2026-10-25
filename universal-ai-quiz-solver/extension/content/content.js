if (!window.UAQS.initialized) {
  window.UAQS.initialized = true;
  chrome.storage.local.get(null).then(settings => UAQS.interactions.update(settings));
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'local') return;
    chrome.storage.local.get(null).then(settings => UAQS.interactions.update(settings));
  });
  const observer = new MutationObserver(records => {
    if (records.every(record => record.target.closest?.('#uaqs-panel'))) return;
    UAQS.detector.invalidate();
    UAQS.interactions.scheduleAutomatic();
  });
  observer.observe(document.documentElement, {childList: true, subtree: true});
  chrome.runtime.onMessage.addListener((message, _sender, respond) => {
    if (message.type === 'PING') { respond({ok: true}); return; }
    if (message.type === 'CLEAR') { UAQS.ui.clearAll(); respond({ok: true}); return; }
    if (message.type === 'COUNT') { respond({count: UAQS.detector.detect().length}); return; }
    if (message.type === 'SOLVE_ALL') {
      UAQS.interactions.solveAll().then(respond, error => respond({error: error.message}));
      return true;
    }
  });
}
