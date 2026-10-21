(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) {
    root.BriefUI = root.BriefUI || {};
    Object.assign(root.BriefUI, api);
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function () {
  'use strict';

  const END_ATTRIBUTES = ['data-calendar-end', 'data-local-plan-end'];
  const mountedDocuments = new WeakSet();

  function endTime(element) {
    for (const name of END_ATTRIBUTES) {
      const value = element.getAttribute(name);
      if (value == null) continue;
      // Require an explicit UTC marker or numeric offset so interpretation never
      // depends on the viewer's machine timezone.
      if (!/T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) return null;
      const parsed = Date.parse(value);
      return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
  }

  function updateCalendarPast(container, now) {
    const scope = container || (typeof document !== 'undefined' ? document : null);
    if (!scope || typeof scope.querySelectorAll !== 'function') return 0;
    const currentTime = Number.isFinite(now) ? now : Date.now();
    const selector = '[data-calendar-end], [data-local-plan-end], [data-calendar-key]';
    const elements = Array.from(scope.querySelectorAll(selector));
    if (typeof scope.matches === 'function' && scope.matches(selector)) elements.unshift(scope);
    for (const element of elements) {
      const end = endTime(element);
      element.classList.toggle('calendar-past', end !== null && end <= currentTime);
      const override = element.getAttribute('data-calendar-done');
      const done = override === 'true' || (override !== 'false' && end !== null && end <= currentTime);
      element.classList.toggle('calendar-done', done);
      for (const button of element.querySelectorAll?.('[data-calendar-toggle]') || []) {
        button.textContent = done ? 'Undo done' : 'Done';
        button.setAttribute('aria-pressed', String(done));
        const label = button.getAttribute('aria-label')?.replace(/^(?:Mark done: |Undo done: )/, '') || 'calendar item';
        button.setAttribute('aria-label', (done ? 'Undo done: ' : 'Mark done: ') + label);
        button.setAttribute('title', (done ? 'Undo done: ' : 'Mark done: ') + label);
      }
    }
    return elements.length;
  }

  function mountCalendarPast(container, environment) {
    const doc = (environment && environment.document) ||
      (container && container.ownerDocument) ||
      (typeof document !== 'undefined' ? document : null);
    updateCalendarPast(container || doc);
    if (!doc || mountedDocuments.has(doc)) return;
    mountedDocuments.add(doc);
    const schedule = (environment && environment.setInterval) || setInterval;
    schedule(() => updateCalendarPast(doc), 60000);
    doc.addEventListener('visibilitychange', () => updateCalendarPast(doc));
  }

  const api = { mountCalendarPast, updateCalendarPast };
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => mountCalendarPast(document), { once: true });
    } else {
      mountCalendarPast(document);
    }
  }
  return api;
});
