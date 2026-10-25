window.UAQS = window.UAQS || {};
window.UAQS.interactions = (() => {
  let config = {enabled: true, clickMode: false, hoverMode: false, explanations: true, highlights: true, autoSelect: false, authorizedPractice: false, autoSolve: false, autoSites: [], imageConsent: false};
  let hoverTimer;
  let hoverRequest;
  let lastHoverId;
  let automaticTimer;
  let automaticBusy = false;
  let automaticPending = false;
  const cache = new Map();
  const inFlight = new Map();
  const failedAt = new Map();

  function sitePattern() { return `${location.protocol}//${location.hostname}/*`; }
  function automaticEnabled() {
    return config.enabled && config.authorizedPractice && config.autoSolve &&
      Array.isArray(config.autoSites) && config.autoSites.includes(sitePattern());
  }
  function update(next) {
    config = {...config, ...next};
    failedAt.clear();
    scheduleAutomatic();
  }
  function scheduleAutomatic() {
    if (!automaticEnabled()) return;
    clearTimeout(automaticTimer);
    automaticTimer = setTimeout(() => autoSolveVisible().catch(() => {}), 350);
  }
  async function captureImage(item) {
    if (!config.imageConsent || !item.image) return;
    try {
      const canvas = document.createElement('canvas');
      canvas.width = item.image.naturalWidth; canvas.height = item.image.naturalHeight;
      if (!canvas.width || !canvas.height || canvas.width * canvas.height > 4_000_000) return;
      canvas.getContext('2d').drawImage(item.image, 0, 0);
      item.question.image_data = canvas.toDataURL('image/png').split(',')[1];
      item.question.image_mime_type = 'image/png';
    } catch { /* Cross-origin images cannot be read without permission. */ }
  }
  async function solve(item, requestId) {
    if (!config.enabled) return;
    const id = item.question.id;
    if (cache.has(id)) { UAQS.ui.render(item, cache.get(id), config); return cache.get(id); }
    if (inFlight.has(id)) return inFlight.get(id);
    UAQS.ui.state(item, 'Solving…');
    const task = (async () => {
      try {
        await captureImage(item);
        const answer = await chrome.runtime.sendMessage({type: 'SOLVE', question: item.question, requestId});
        if (answer.error && !answer.status) throw new Error(answer.error);
        cache.set(id, answer); UAQS.ui.render(item, answer, config); return answer;
      } catch (error) { failedAt.set(id, Date.now()); UAQS.ui.state(item, `Error: ${error.message}`); throw error; }
      finally { inFlight.delete(id); }
    })();
    inFlight.set(id, task); return task;
  }
  function onClick(event) {
    if (!config.enabled || !config.clickMode || event.target.closest?.('#uaqs-panel')) return;
    const item = UAQS.detector.nearest(event.target);
    if (item) solve(item).catch(() => {});
  }
  function onMove(event) {
    if (!config.enabled || !config.hoverMode || !event.ctrlKey) return;
    const item = UAQS.detector.nearest(event.target);
    if (!item || item.question.id === lastHoverId) return;
    clearTimeout(hoverTimer);
    if (hoverRequest) chrome.runtime.sendMessage({type: 'CANCEL', requestId: hoverRequest}).catch(() => {});
    lastHoverId = item.question.id;
    hoverTimer = setTimeout(() => {
      hoverRequest = `hover-${Date.now()}-${Math.random()}`;
      solve(item, hoverRequest).catch(() => {});
    }, 350);
  }
  function onKey(event) {
    if (event.key === 'Control' && !event.ctrlKey) lastHoverId = null;
  }
  async function solveAll({automatic = false} = {}) {
    const items = UAQS.detector.detect().filter(item => {
      const rect = item.root.getBoundingClientRect();
      return rect.width && rect.height;
    }).slice(0, 20);
    if (!items.length) return automatic ? {count: 0, errors: 0} : {error: 'No supported questions found on this page.'};
    if (!automatic) items.filter(item => cache.has(item.question.id)).forEach(item => UAQS.ui.render(item, cache.get(item.question.id), config));
    const fresh = items.filter(item => !cache.has(item.question.id) && !inFlight.has(item.question.id) &&
      (!automatic || Date.now() - (failedAt.get(item.question.id) || 0) > 60000));
    const answers = [];
    for (let offset = 0; offset < fresh.length; offset += 5) {
      const group = fresh.slice(offset, offset + 5);
      group.forEach(item => UAQS.ui.state(item, 'Solving…'));
      await Promise.all(group.map(item => captureImage(item)));
      const response = await chrome.runtime.sendMessage({type: 'BATCH', questions: group.map(item => item.question)});
      if (response.error) {
        group.forEach(item => { failedAt.set(item.question.id, Date.now()); UAQS.ui.state(item, `Error: ${response.error}`); });
        return {error: response.error};
      }
      response.answers.forEach((answer, index) => {
        if (answer.status === 'error') failedAt.set(group[index].question.id, Date.now());
        else cache.set(group[index].question.id, answer);
        UAQS.ui.render(group[index], answer, config);
        answers.push(answer);
      });
    }
    return {count: automatic ? answers.length : items.length, errors: answers.filter(answer => answer.status === 'error').length};
  }
  async function autoSolveVisible() {
    if (!automaticEnabled()) return;
    if (automaticBusy) { automaticPending = true; return; }
    automaticBusy = true;
    try {
      const result = await solveAll({automatic: true});
      if (result.error || result.errors) setTimeout(scheduleAutomatic, 60000);
    } finally {
      automaticBusy = false;
      if (automaticPending) { automaticPending = false; scheduleAutomatic(); }
    }
  }
  document.addEventListener('click', onClick, true);
  document.addEventListener('mousemove', onMove, {passive: true});
  document.addEventListener('keyup', onKey);
  return {update, solveAll, scheduleAutomatic, cache};
})();
