/* A local occurrence override; provider calendar events remain read-only. */
(function () {
  'use strict';
  if (typeof document === 'undefined') return;
  const doc = document, view = doc.defaultView;
  let saving = false;
  doc.addEventListener('click', async event => {
    const button = event.target.closest?.('[data-calendar-remove]');
    if (!button || button.disabled || saving) return;
    const today = doc.querySelector('#today'), calendar = doc.querySelector('#focus-exercise');
    if (doc.querySelector('[data-plan-locked="true"],[data-calendar-saving="true"]')) return;
    const config = JSON.parse(today.querySelector('.calendar-interaction-data').textContent);
    const request = {key: button.dataset.eventKey, start: button.dataset.eventStart,
      end: button.dataset.eventEnd, base_removed: button.dataset.removed === 'true',
      removed: button.dataset.removed !== 'true'};
    const status = today.querySelector('.calendar-removal-status');
    const controls = Array.from(doc.querySelectorAll('#today button,#focus-exercise button,#focus-exercise input')).map(node => [node, node.disabled]);
    saving = true; today.dataset.calendarSaving = 'true';
    controls.forEach(([node]) => {node.disabled = true;});
    calendar?.dayPlanner?.setLocked(true); calendar?.scheduleEditor?.setLocked(true);
    doc.dispatchEvent(new view.CustomEvent('local-calendar-change'));
    status.textContent = request.removed ? 'Removing event from today…' : 'Restoring event to today…';
    const unlock = () => {
      saving = false; delete today.dataset.calendarSaving;
      controls.forEach(([node, disabled]) => {node.disabled = disabled;});
      calendar?.dayPlanner?.setLocked(false); calendar?.scheduleEditor?.setLocked(false);
      doc.dispatchEvent(new view.CustomEvent('local-calendar-change'));
    };
    try {
      const response = await view.fetch(config.endpoint.replace('/calendar/done', '/calendar/remove'), {
        method: 'POST', credentials: 'omit', cache: 'no-store', signal: AbortSignal.timeout(10000),
        headers: {'Content-Type': 'application/json', 'X-Brief-Token': config.token}, body: JSON.stringify(request)});
      const result = await response.json();
      if (!response.ok || result.ok !== true ||
          !['key', 'start', 'end', 'removed'].every(key => result.record?.[key] === request[key])) {
        throw Error(result.error || 'The calendar change was not acknowledged.');
      }
    } catch (error) {
      status.textContent = 'Change not confirmed: ' + error.message + ' The previous view is still shown.';
      unlock(); return;
    }
    const message = request.removed ? 'Removed from today; its time is available in this planner.' : 'Restored to today; its time is reserved again.';
    async function refresh() {
      try {
        await view.BriefUI.refreshPlanSurfaces(today, message, true);
        unlock();
      } catch (error) {
        status.textContent = 'Calendar change saved locally. The updated view could not load. ';
        const retry = doc.createElement('button'); retry.type = 'button'; retry.textContent = 'Refresh today';
        retry.addEventListener('click', async () => {retry.disabled = true; await refresh();});
        status.append(retry);
      }
    }
    await refresh();
  });
})();
