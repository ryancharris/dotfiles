/* Personal completion marks never modify provider events or scheduling bounds. */
(function () {
  'use strict';
  const mounted = new WeakSet();
  function mountCalendarCompletion(doc) {
    if (!doc || mounted.has(doc)) return;
    mounted.add(doc);
    const view = doc.defaultView;
    doc.addEventListener('click', async event => {
      const button = event.target.closest?.('[data-calendar-toggle]');
      if (!button || button.disabled) return;
      const row = button.closest('[data-calendar-key]');
      const configNode = doc.querySelector('.calendar-interaction-data');
      if (!row || !configNode || row.dataset.calendarSaving === 'true') return;
      const key = row.dataset.calendarKey;
      const peers = () => Array.from(doc.querySelectorAll('[data-calendar-key]')).filter(item => item.dataset.calendarKey === key);
      const show = message => {const status = doc.querySelector('.calendar-completion-status'); if (status) status.textContent = message;};
      const changed = () => doc.dispatchEvent(new view.CustomEvent('local-calendar-change'));
      view.BriefUI.updateCalendarPast(doc);
      const done = !row.classList.contains('calendar-done');
      const controls = peers().flatMap(item => Array.from(item.querySelectorAll('[data-calendar-toggle]')));
      peers().forEach(item => {item.dataset.calendarSaving = 'true';});
      controls.forEach(control => {control.disabled = true;});
      changed(); show('Saving calendar mark locally…');
      try {
        const config = JSON.parse(configNode.textContent);
        const response = await view.fetch(config.endpoint, {method: 'POST', credentials: 'omit', cache: 'no-store',
          signal: AbortSignal.timeout(10000), headers: {'Content-Type': 'application/json', 'X-Brief-Token': config.token},
          body: JSON.stringify({key, done})});
        const result = await response.json();
        if (!response.ok || result.ok !== true || result.record?.key !== key || result.record?.done !== done) {
          throw Error(result.error || 'The calendar mark was not acknowledged.');
        }
        peers().forEach(item => {item.dataset.calendarDone = String(done);});
        view.BriefUI.updateCalendarPast(doc);
        show(done ? 'Marked done locally.' : 'Marked not done locally.');
      } catch (error) {
        show('Calendar mark not confirmed: ' + error.message + ' Your previous mark is still shown.');
      } finally {
        peers().forEach(item => {delete item.dataset.calendarSaving;});
        controls.forEach(control => {control.disabled = false;});
        changed();
      }
    });
  }
  if (typeof document !== 'undefined') mountCalendarCompletion(document);
})();
