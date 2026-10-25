window.UAQS = window.UAQS || {};
window.UAQS.ui = (() => {
  let panel;
  function ensurePanel() {
    if (panel?.isConnected) return panel;
    panel = document.createElement('aside'); panel.id = 'uaqs-panel';
    panel.setAttribute('aria-live', 'polite');
    const heading = document.createElement('strong'); heading.textContent = 'Quiz suggestions';
    const clear = document.createElement('button'); clear.textContent = 'Clear'; clear.type = 'button';
    clear.addEventListener('click', clearAll);
    const list = document.createElement('div'); list.id = 'uaqs-results';
    panel.append(heading, clear, list); document.documentElement.append(panel);
    return panel;
  }
  function row(id) {
    ensurePanel();
    let el = [...panel.querySelectorAll('[data-question-id]')].find(item => item.dataset.questionId === id);
    if (!el) { el = document.createElement('section'); el.dataset.questionId = id; panel.querySelector('#uaqs-results').append(el); }
    el.replaceChildren(); return el;
  }
  function state(item, message) { row(item.question.id).textContent = message; }
  function render(item, answer, settings) {
    const el = row(item.question.id);
    const title = document.createElement('b'); title.textContent = item.question.text.slice(0, 110);
    const result = document.createElement('p');
    if (answer.status === 'error') result.textContent = `Error: ${answer.error || 'Unknown error'}`;
    else {
      const selected = item.question.options.filter(o => answer.selected_option_ids.includes(o.id)).map(o => o.text);
      result.textContent = `${answer.status === 'uncertain' ? 'Uncertain: ' : ''}${selected.join(', ') || answer.text_answer || 'No answer'} · estimate ${Math.round(answer.confidence * 100)}%`;
    }
    el.append(title, result);
    if (settings.explanations && answer.explanation) {
      const explanation = document.createElement('p'); explanation.textContent = answer.explanation; el.append(explanation);
    }
    if (settings.highlights && answer.status === 'solved') {
      item.optionElements.forEach((control, index) => {
        const option = item.question.options[index];
        const target = control.closest('label') || control;
        if (answer.selected_option_ids.includes(option?.id)) target.classList.add('uaqs-suggested');
      });
      if (item.optionElements[0]?.tagName === 'OPTION' && answer.selected_option_ids.length) {
        item.optionElements[0].parentElement.classList.add('uaqs-suggested');
      }
    }
    if (settings.autoSelect && settings.authorizedPractice && answer.status === 'solved') {
      if (item.optionElements[0]?.tagName === 'OPTION') {
        const selected = item.optionElements.find((_, index) => answer.selected_option_ids.includes(item.question.options[index]?.id));
        if (selected) {
          selected.parentElement.value = selected.value;
          selected.parentElement.dispatchEvent(new Event('input', {bubbles: true}));
          selected.parentElement.dispatchEvent(new Event('change', {bubbles: true}));
        }
      }
      item.optionElements.forEach((control, index) => {
        if (!answer.selected_option_ids.includes(item.question.options[index]?.id)) return;
        if (control.matches('input[type="radio"],input[type="checkbox"]')) {
          control.checked = true;
          control.dispatchEvent(new Event('input', {bubbles: true}));
          control.dispatchEvent(new Event('change', {bubbles: true}));
        } else if (control.matches('[role="radio"],[role="checkbox"]') && control.tagName !== 'BUTTON') control.click();
      });
    }
  }
  function clearAll() {
    document.querySelectorAll('.uaqs-suggested').forEach(el => el.classList.remove('uaqs-suggested'));
    panel?.remove(); panel = null;
  }
  return {state, render, clearAll};
})();
