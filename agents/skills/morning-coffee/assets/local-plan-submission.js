/* Saving changes only the local daily plan; it never creates calendar events. */
(function () {
  'use strict';
  const clock = n => String(Math.floor(n / 60)).padStart(2, '0') + ':' + String(n % 60).padStart(2, '0');
  const labels = {focus:'🔎 Focus', exercise:'👟 Exercise', dog_walk:'🐕 Dog walk', lunch:'🥪 Lunch'};
  function showSavedPlan(plan, doc) {
    if (!doc || typeof doc.querySelector !== 'function') return;
    const today = doc.querySelector('#today');
    const agenda = today && today.querySelector('.agenda');
    if (agenda) {
      agenda.querySelectorAll('[data-plan-source="local"]').forEach(row => row.remove());
      plan.blocks.forEach(block => {
        const row = doc.createElement('li');
        row.dataset.planSource = 'local'; row.dataset.start = String(block.start);
        const time = doc.createElement('span'); time.className = 'clock';
        time.textContent = clock(block.start) + '–' + clock(block.start + block.minutes);
        const title = doc.createElement('span'); title.textContent = labels[block.kind] || block.kind;
        const source = doc.createElement('span'); source.className = 'muted'; source.textContent = ' Local chosen plan';
        title.append(source);
        const join = doc.createElement('span'); join.className = 'join';
        row.append(time, title, join);
        const later = Array.from(agenda.children).find(item => Number(item.dataset.start) > block.start);
        agenda.insertBefore(row, later || null);
      });
      const empty = today.querySelector('.agenda-empty');
      if (empty) empty.hidden = agenda.children.length > 0;
    }
    const overview = doc.querySelector('[data-calendar-event-count]');
    if (overview) {
      const events = Number(overview.dataset.calendarEventCount);
      overview.querySelector('.status-value').textContent = String(events + plan.blocks.length);
      overview.querySelector('.status-note').textContent = events + ' event' + (events === 1 ? '' : 's') + ' from calendar · ' + plan.blocks.length + ' local plan block' + (plan.blocks.length === 1 ? '' : 's') + ' · ' + overview.dataset.agendaTimezone;
    }
  }
  function mount(root) {
    const configNode = root.querySelector('.plan-submit-data');
    if (!configNode) return;
    const config = JSON.parse(configNode.textContent);
    const opener = root.querySelector('.plan-submit-button');
    const review = root.querySelector('.plan-submit-review');
    const status = root.querySelector('.plan-submit-status');
    const calendar = root.closest('.day-calendar') || document.querySelector('.day-calendar');
    let submitting = false, pending = null;
    const lockPlanner = value => {
      if (calendar && calendar.dayPlanner && calendar.dayPlanner.setLocked) calendar.dayPlanner.setLocked(value);
    };
    const current = () => {
      if (!calendar || typeof calendar.getDayPlan !== 'function') throw Error('Reload the active Coffee submission session.');
      const data = calendar.getDayPlan();
      return {date: data.date, timezone: data.timezone, blocks: data.blocks.filter(b => Number.isFinite(b.start)).map(b => ({kind: b.kind, start: b.start, minutes: b.minutes}))};
    };
    const clear = () => {review.hidden = true; review.replaceChildren(); pending = null;};
    if (calendar) calendar.addEventListener('day-plan-change', () => {if (!submitting) clear();});
    opener.addEventListener('click', () => {
      if (submitting) return;
      try {
        pending = current(); review.replaceChildren();
        const heading = document.createElement('p');
        heading.textContent = pending.blocks.length ? 'Save these chosen blocks for today’s Tea?' : 'Save an empty plan for today’s Tea?';
        review.append(heading);
        const list = document.createElement('ul');
        pending.blocks.forEach(block => {
          const item = document.createElement('li');
          item.textContent = block.kind.replaceAll('_', ' ') + ' · ' + clock(block.start) + '–' + clock(block.start + block.minutes);
          list.append(item);
        });
        review.append(list);
        const details = document.createElement('p');
        details.textContent = pending.date + ' · ' + pending.timezone + ' · local plan only';
        review.append(details);
        const confirm = document.createElement('button');
        confirm.type = 'button'; confirm.textContent = 'Submit plan';
        const cancel = document.createElement('button');
        cancel.type = 'button'; cancel.textContent = 'Cancel'; cancel.addEventListener('click', () => {clear(); opener.focus();});
        review.append(confirm, cancel); review.hidden = false; status.textContent = ''; confirm.focus();
        confirm.addEventListener('click', async () => {
          if (submitting || !pending) return;
          const selected = pending;
          if (JSON.stringify(current()) !== JSON.stringify(selected)) {clear(); status.textContent = 'Your plan changed. Review the times again.'; return;}
          submitting = true; lockPlanner(true); opener.disabled = true; confirm.disabled = true; cancel.disabled = true;
          status.textContent = 'Saving your local plan…';
          try {
            const response = await fetch(config.endpoint, {method: 'POST', credentials: 'omit', headers: {'Content-Type': 'application/json', 'X-Brief-Token': config.token}, body: JSON.stringify(selected)});
            const result = await response.json();
            if (!response.ok || !result.ok) throw Error(result.error || 'The local plan could not be saved.');
            showSavedPlan({...selected, blocks:Array.isArray(result.blocks) ? result.blocks : selected.blocks}, document);
            status.textContent = result.message + ' You can adjust and resubmit anytime.';
            clear();
          } catch (error) {
            status.textContent = 'Plan not confirmed saved: ' + error.message + ' Retry to save the same choices.';
          } finally {
            lockPlanner(false); submitting = false; opener.disabled = false; confirm.disabled = false; cancel.disabled = false;
            status.tabIndex = -1; status.focus();
          }
        });
      } catch (error) {status.textContent = error.message;}
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {mount, showSavedPlan};
  if (typeof document !== 'undefined') document.querySelectorAll('.plan-submission').forEach(mount);
})();
