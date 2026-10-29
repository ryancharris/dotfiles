/* Saving changes only the local daily plan; it never creates calendar events. */
(function () {
  'use strict';
  const clock = n => String(Math.floor(n / 60)).padStart(2, '0') + ':' + String(n % 60).padStart(2, '0');
  const labels = {focus:'🔎 Focus', exercise:'👟 Exercise', dog_walk:'🐕 Dog walk', lunch:'🥪 Lunch', learning:'📚 Reading / learning'};
  const label = block => block.kind==='focus' && block.name ? '🔎 '+block.name : labels[block.kind] || block.kind;
  const sameBlock = (left,right) => ['kind','start','minutes'].every(key=>left[key]===right[key]) && left.name===right.name;
  function showSavedPlan(plan, doc) {
    if (!doc || typeof doc.querySelector !== 'function') return;
    const today = doc.querySelector('#today');
    const agenda = today && today.querySelector('.agenda');
    if (agenda) {
      agenda.querySelectorAll('[data-plan-source="local"]').forEach(row => row.remove());
      plan.blocks.forEach(block => {
        const row = doc.createElement('li');
        row.dataset.planSource = 'local'; row.dataset.start = String(block.start);
        if(plan.end_times?.[block.kind])row.dataset.localPlanEnd=plan.end_times[block.kind];
        const time = doc.createElement('span'); time.className = 'clock';
        time.textContent = clock(block.start) + '–' + clock(block.start + block.minutes);
        const title = doc.createElement('span'); title.textContent = label(block);
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
  function scheduleEditor(calendar, doc) {
    if (!calendar || !doc || typeof doc.querySelector !== 'function') return null;
    const edit = doc.querySelector('[data-edit-schedule]');
    if (!edit) return null;
    if (calendar.scheduleEditor && calendar.scheduleEditor.edit === edit) return calendar.scheduleEditor;
    const cancel = calendar.querySelector('.day-cancel');
    const todayRead = doc.querySelector('[data-today-read]');
    const capture = () => calendar.dayPlanner && calendar.dayPlanner.getState ? calendar.dayPlanner.getState() : null;
    let baseline = capture(), locked = false;
    const editor = {
      edit,
      setVisible(visible) {
        calendar.hidden = !visible;
        if(todayRead)todayRead.hidden = visible;
        edit.hidden = visible;
        edit.setAttribute('aria-expanded', String(visible));
      },
      setLocked(value) {locked = Boolean(value); edit.disabled = locked; if (cancel) cancel.disabled = locked;},
      confirmSaved() {baseline = capture();},
      getBaseline() {return baseline;},
      restoreBaseline(value) {baseline = value;},
      onCancel: null
    };
    edit.addEventListener('click', () => {
      if (locked || !calendar.hidden) return;
      baseline = capture();
      editor.setVisible(true);
      const heading = calendar.querySelector('#day-calendar-title');
      if (heading) {heading.tabIndex = -1; heading.focus();}
      if (calendar.scrollIntoView) calendar.scrollIntoView({block:'start',behavior:'smooth'});
    });
    if (cancel) cancel.addEventListener('click', () => {
      if (locked) return;
      if (baseline && calendar.dayPlanner && calendar.dayPlanner.restoreState) calendar.dayPlanner.restoreState(baseline);
      if (editor.onCancel) editor.onCancel();
      editor.setVisible(false);
      edit.focus();
    });
    calendar.scheduleEditor = editor;
    editor.setVisible(!calendar.hidden);
    return editor;
  }
  function mount(root) {
    if(root.submissionMounted)return;
    root.submissionMounted=true;
    const calendar = root.closest('.day-calendar') || document.querySelector('.day-calendar');
    const editor = scheduleEditor(calendar, document);
    const configNode = root.querySelector('.plan-submit-data');
    if (!configNode) return;
    const config = JSON.parse(configNode.textContent);
    let baseRevision = config.base_revision ?? null;
    if(calendar)calendar.planSubmission={getBaseRevision:()=>baseRevision,restoreBaseRevision:value=>{baseRevision=value;}};
    const opener = root.querySelector('.plan-submit-button');
    const review = root.querySelector('.plan-submit-review');
    const status = root.querySelector('.plan-submit-status');
    let submitting = false, pending = null;
    const lockPlanner = value => {
      if (editor) editor.setLocked(value);
      if (calendar && calendar.dayPlanner && calendar.dayPlanner.setLocked) calendar.dayPlanner.setLocked(value);
    };
    const current = () => {
      if (!calendar || typeof calendar.getDayPlan !== 'function') throw Error('Reload the active Coffee submission session.');
      const data = calendar.getDayPlan();
      return {date: data.date, timezone: data.timezone, base_revision: baseRevision, blocks: data.blocks.filter(b => Number.isFinite(b.start)).map(b => ({kind: b.kind, start: b.start, minutes: b.minutes, ...(b.kind==='focus' && b.name ? {name:b.name} : {})}))};
    };
    const clear = () => {review.hidden = true; review.replaceChildren(); pending = null;};
    if (editor) editor.onCancel = () => {clear(); status.textContent = '';};
    if (calendar) calendar.addEventListener('day-plan-change', () => {if (!submitting) clear();});
    opener.addEventListener('click', () => {
      if (submitting) return;
      try {
        pending = current(); review.replaceChildren();
        const heading = document.createElement('p');
        heading.textContent = pending.blocks.length ? 'Save these chosen blocks for today?' : 'Save an empty plan for today?';
        review.append(heading);
        const list = document.createElement('ul');
        pending.blocks.forEach(block => {
          const item = document.createElement('li');
          item.textContent = (block.kind==='focus' && block.name ? block.name : block.kind==='learning' ? 'Reading / learning' : block.kind.replaceAll('_', ' ')) + ' · ' + clock(block.start) + '–' + clock(block.start + block.minutes);
          list.append(item);
        });
        review.append(list);
        const details = document.createElement('p');
        details.textContent = pending.date + ' · ' + pending.timezone + ' · local plan only';
        review.append(details);
        const confirm = document.createElement('button');
        confirm.type = 'button'; confirm.id = 'plan-submit-confirm'; confirm.textContent = 'Submit plan';
        const cancel = document.createElement('button');
        cancel.type = 'button'; cancel.id = 'plan-submit-cancel'; cancel.textContent = 'Cancel'; cancel.addEventListener('click', () => {clear(); opener.focus();});
        review.append(confirm, cancel); review.hidden = false; status.textContent = ''; confirm.focus();
        confirm.addEventListener('click', async () => {
          if (submitting || !pending) return;
          const selected = pending;
          let saved = false;
          if (JSON.stringify(current()) !== JSON.stringify(selected)) {clear(); status.textContent = 'Your plan changed. Review the times again.'; return;}
          submitting = true; lockPlanner(true); opener.disabled = true; confirm.disabled = true; cancel.disabled = true;
          status.textContent = 'Saving your local plan…';
          try {
            const response = await fetch(config.endpoint, {method: 'POST', credentials: 'omit', signal:AbortSignal.timeout(10000), headers: {'Content-Type': 'application/json', 'X-Brief-Token': config.token}, body: JSON.stringify(selected)});
            const result = await response.json();
            if (!response.ok || !result.ok) throw Error(result.error || 'The local plan could not be saved.');
            if(!Array.isArray(result.blocks) || result.blocks.length!==selected.blocks.length ||
              !selected.blocks.every(block=>result.blocks.filter(row=>sameBlock(block,row)).length===1))throw Error('The local plan was not acknowledged with the expected blocks and names.');
            if(typeof result.revision==='string')baseRevision=result.revision;
            if(typeof window!=='undefined' && typeof window.CustomEvent==='function')document.dispatchEvent(new window.CustomEvent('local-plan-saved'));
            showSavedPlan({...selected, blocks:Array.isArray(result.blocks) ? result.blocks : selected.blocks,end_times:result.end_times}, document);
            if(typeof window!=='undefined')window.BriefUI?.updateCalendarPast?.(document);
            status.textContent = result.message + ' Choose Edit schedule in Today to make changes.';
            clear();
            saved = true;
            if (editor) {editor.confirmSaved(); editor.setVisible(false);}
            if(typeof window!=='undefined' && window.BriefUI?.refreshPlanSurfaces) {
              try {await window.BriefUI.refreshPlanSurfaces(calendar,'Plan saved locally.');}
              catch(error) {status.textContent='Plan saved locally. Reload the workspace to update its removal controls.';}
            }
            const readStatus=document.querySelector('#today .day-read-status');
            if(readStatus)readStatus.textContent=status.textContent;
            const removalStatus=document.querySelector('#today .day-remove-status');
            if(removalStatus && readStatus)removalStatus.textContent='';
          } catch (error) {
            status.textContent = 'Plan not confirmed saved: ' + error.message + ' Retry to save the same choices.';
          } finally {
            lockPlanner(false); submitting = false; opener.disabled = false; confirm.disabled = false; cancel.disabled = false;
            if (saved && editor) (document.querySelector('[data-edit-schedule]') || editor.edit).focus();
            else {status.tabIndex = -1; status.focus();}
          }
        });
      } catch (error) {status.textContent = error.message;}
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {mount, showSavedPlan, scheduleEditor};
  if(typeof window!=='undefined'){window.BriefUI=window.BriefUI||{};window.BriefUI.mountSubmission=mount;}
  if (typeof document !== 'undefined') document.querySelectorAll('.plan-submission').forEach(mount);
})();
