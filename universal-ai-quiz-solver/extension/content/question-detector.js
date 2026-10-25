window.UAQS = window.UAQS || {};
window.UAQS.detector = (() => {
  let cached;
  function roots(node = document) {
    const result = [node];
    for (const el of node.querySelectorAll('*')) if (el.shadowRoot) result.push(...roots(el.shadowRoot));
    return result;
  }
  function detect() {
    if (cached) return cached;
    const candidates = new Set();
    for (const root of roots()) {
      const adapter = UAQS.adapters.find(item => item.host.test(location.hostname));
      for (const selector of [...(adapter?.selectors || []), 'fieldset', '[role="radiogroup"]', '[role="group"]', '[data-question]', 'form']) {
        root.querySelectorAll(selector).forEach(el => candidates.add(el));
      }
      root.querySelectorAll('input[type="radio"],input[type="checkbox"],select,textarea,input[type="text"],[role="radio"],[role="checkbox"]').forEach(el => {
        candidates.add(el.closest('fieldset,[role="radiogroup"],[role="group"],[data-question]') || el.closest('form') || el.parentElement?.parentElement);
      });
      root.querySelectorAll('button,[role="button"]').forEach(el => {
        const parent = el.parentElement;
        if (parent?.querySelectorAll('button,[role="button"]').length >= 2) candidates.add(parent.parentElement || parent);
      });
    }
    const parsed = [...candidates].map(el => UAQS.parser.parse(el)).filter(Boolean);
    parsed.sort((a, b) => a.root.querySelectorAll('*').length - b.root.querySelectorAll('*').length);
    const unique = new Map();
    for (const item of parsed) {
      if ([...unique.values()].some(chosen => item.root !== chosen.root && item.root.contains(chosen.root))) continue;
      if (!unique.has(item.question.id)) unique.set(item.question.id, item);
    }
    cached = [...unique.values()];
    return cached;
  }
  function nearest(target) {
    const items = detect();
    return items.find(item => item.root === target || item.root.contains(target)) || null;
  }
  return {detect, nearest, invalidate: () => { cached = null; }};
})();
