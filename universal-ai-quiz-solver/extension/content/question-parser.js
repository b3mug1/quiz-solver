window.UAQS = window.UAQS || {};
window.UAQS.parser = (() => {
  const text = el => (el?.innerText || el?.textContent || '').trim().replace(/[ \t]+/g, ' ').slice(0, 12000);
  const hash = value => {
    let n = 2166136261;
    for (let i = 0; i < value.length; i++) n = Math.imul(n ^ value.charCodeAt(i), 16777619);
    return (n >>> 0).toString(16);
  };
  function controls(root) {
    return [...root.querySelectorAll('input[type="radio"],input[type="checkbox"],select,textarea,input[type="text"],input:not([type]),[role="radio"],[role="checkbox"],[role="option"]')];
  }
  function optionText(el, root) {
    if (el.tagName === 'OPTION') return text(el);
    const label = el.closest('label') || (el.id && root.querySelector(`label[for="${CSS.escape(el.id)}"]`));
    return text(label || el.closest('[role="option"],[role="radio"],[role="checkbox"]') || el.parentElement || el);
  }
  function questionText(root, optionElements) {
    const explicit = root.querySelector('legend,[data-question-text],.question-text,h1,h2,h3,h4,[role="heading"]');
    if (explicit && text(explicit)) return text(explicit);
    const clone = root.cloneNode(true);
    clone.querySelectorAll('label,input,button,select,textarea,[role="option"],[role="radio"],[role="checkbox"],script,style').forEach(el => el.remove());
    const remaining = text(clone);
    if (remaining) return remaining.slice(0, 12000);
    const first = optionElements[0];
    return text(first?.parentElement?.previousElementSibling);
  }
  function parse(root) {
    if (!root || root.closest?.('#uaqs-panel')) return null;
    const all = controls(root);
    const choice = all.filter(el => el.matches('input[type="radio"],input[type="checkbox"],[role="radio"],[role="checkbox"]'));
    const select = all.find(el => el.tagName === 'SELECT');
    let optionElements = choice;
    let type = choice.some(el => el.matches('input[type="checkbox"],[role="checkbox"]')) ? 'multiple_choice' : 'single_choice';
    if (select) { optionElements = [...select.options].filter(el => el.value); type = 'single_choice'; }
    if (!optionElements.length && all.some(el => el.matches('textarea,input[type="text"],input:not([type])'))) type = 'short_answer';
    if (!optionElements.length && !all.length) {
      const buttons = [...root.querySelectorAll('button,[role="button"]')].filter(el => text(el));
      if (buttons.length >= 2) optionElements = buttons;
      else return null;
    }
    const qText = questionText(root, optionElements);
    if (qText.length < 2) return null;
    const options = optionElements.map((el, i) => ({id: String(el.value || el.getAttribute('data-value') || i), text: optionText(el, root)}));
    if (optionElements.length && (options.length < 2 || options.some(o => !o.text))) return null;
    const ids = new Set();
    options.forEach((o, i) => { if (ids.has(o.id)) o.id = `${o.id}-${i}`; ids.add(o.id); });
    if (/^(true|false)$/i.test(options[0]?.text) && options.length === 2) type = 'true_false';
    if (!options.length && /\b(fill|blank|complete)\b/i.test(qText)) type = 'fill_blank';
    if (!options.length && /[=∫√∑]/.test(qText)) type = 'math';
    if (!options.length && root.querySelector('pre,code')) type = 'programming';
    const image = root.querySelector('img');
    if (image && !options.length) type = 'image';
    const fingerprint = JSON.stringify([qText, type, options]);
    const question = {
      id: `q-${hash(fingerprint)}`, text: qText, question_type: type, options,
      source_url: location.origin + location.pathname, extraction_confidence: root.matches('fieldset,[role="radiogroup"],[role="group"]') ? 0.95 : 0.7
    };
    return {root, question, optionElements, image};
  }
  return {parse, text};
})();
