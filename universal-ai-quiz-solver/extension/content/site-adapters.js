window.UAQS = window.UAQS || {};
// Site adapters can add semantic selectors while the generic detector remains the fallback.
window.UAQS.adapters = [
  {name: 'moodle', host: /moodle/i, selectors: ['.que']},
  {name: 'canvas', host: /instructure\.com$/i, selectors: ['.question']},
  {name: 'google-forms', host: /docs\.google\.com$/i, selectors: ['[role="listitem"]']}
];
