(function () {
  'use strict';
  document.documentElement.classList.add('js');
  var seedNode = document.getElementById('mc-seed');
  if (!seedNode) return;
  var seed = JSON.parse(seedNode.textContent);
  var START = seed.window[0];
  var END = seed.window[1];
  var PX = 1; // one pixel per minute: the 08:00–19:00 window is 660px tall
  var KINDS = {
    'focus': { label: 'Focus', minutes: 120 },
    'exercise': { label: 'Exercise', minutes: 60 },
    'dog-walk': { label: 'Dog walk', minutes: 30 },
    'lunch': { label: 'Lunch', minutes: 30 },
    'learning': { label: 'Learning', minutes: 30 },
    'custom': { label: 'Custom', minutes: 30 }
  };
  var TODO_KEY = 'morning-coffee:todos';
  var MARK_KEY = 'morning-coffee:marks:' + seed.date;
  var BLOCK_KEY = 'morning-coffee:blocks:' + seed.date;
  var status = document.getElementById('mc-status');

  function $(id) { return document.getElementById(id); }
  function read(key, fallback) {
    try { var raw = localStorage.getItem(key); return raw === null ? fallback : JSON.parse(raw); }
    catch (e) { return fallback; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; }
    catch (e) { return false; }
  }
  function say(message) { if (status) status.textContent = message; }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function clock(min) { return pad(Math.floor(min / 60)) + ':' + pad(min % 60); }
  function parseClock(value) {
    var m = /^(\d{1,2}):(\d{2})$/.exec(value || '');
    return m ? Number(m[1]) * 60 + Number(m[2]) : null;
  }
  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function overlaps(a, b) { return a.start < b.end && b.start < a.end; }

  var todos = read(TODO_KEY, null);
  if (!Array.isArray(todos)) {
    todos = seed.tasks.map(function (t, i) { return { id: 't' + i, text: t.text, done: t.done }; });
  }
  var marks = read(MARK_KEY, {});
  if (!marks || typeof marks !== 'object') marks = {};
  var blocks = read(BLOCK_KEY, []);
  if (!Array.isArray(blocks)) blocks = [];
  var counter = 0;
  var editingId = null;
  var drag = null;
  var suppressClick = false;

  function saveTodos() {
    if (!write(TODO_KEY, todos)) say('This browser would not save the change. Download tasks.md to keep it.');
  }
  function saveBlocks() {
    if (!write(BLOCK_KEY, blocks)) say('This browser would not save the block. Blocks stay until the page closes.');
  }

  /* ---------- To do ---------- */
  function renderTodos() {
    var list = $('todo');
    if (!list) return;
    list.textContent = '';
    if (!todos.length) list.appendChild(el('li', 'row muted', 'None — add a task below'));
    todos.forEach(function (t) {
      var li = el('li', 'row');
      li.dataset.todoId = t.id;
      var box = el('input');
      box.type = 'checkbox';
      box.checked = !!t.done;
      box.dataset.todoToggle = '';
      box.setAttribute('aria-label', 'Done: ' + t.text);
      var label = el('span', 'grow' + (t.done ? ' done' : ''), t.text);
      var del = el('button', null, 'Delete');
      del.type = 'button';
      del.dataset.todoDelete = '';
      li.appendChild(box);
      li.appendChild(label);
      li.appendChild(del);
      list.appendChild(li);
    });
  }

  /* ---------- Marks (done / dismissed) ---------- */
  function applyMarks() {
    document.querySelectorAll('[data-mark-key]').forEach(function (row) {
      var done = !!marks[row.dataset.markKey];
      row.classList.toggle('is-done', done);
      var button = row.querySelector('[data-mark-toggle]');
      if (button) {
        button.textContent = done ? button.dataset.on : button.dataset.off;
        button.setAttribute('aria-pressed', String(done));
      }
    });
  }
  function toggleMark(key) {
    if (marks[key]) delete marks[key]; else marks[key] = true;
    if (!write(MARK_KEY, marks)) say('This browser would not save the change.');
    applyMarks();
  }

  /* ---------- Today: timeline, agenda, custom blocks ---------- */
  function timedEvents() {
    return seed.events.filter(function (e) { return !e.all_day; });
  }

  function blockItems() {
    return blocks.map(function (b) {
      return { id: b.id, start: b.start, end: b.start + b.duration, block: b };
    });
  }

  function renderTimeline() {
    var tl = $('timeline');
    if (!tl) return;
    tl.textContent = '';
    tl.style.height = ((END - START) * PX) + 'px';
    for (var h = START / 60; h * 60 <= END; h++) {
      var top = (h * 60 - START) * PX;
      var tick = el('div', 'tick', clock(h * 60));
      tick.style.top = top + 'px';
      var line = el('div', 'tick-line');
      line.style.top = top + 'px';
      tl.appendChild(tick);
      tl.appendChild(line);
    }
    var items = [];
    timedEvents().forEach(function (e) {
      var s = Math.max(e.start_min, START), en = Math.min(e.end_min, END);
      if (en <= s) return;
      var slot = el('div', 'slot event');
      slot.dataset.markKey = 'cal:' + e.id;
      slot.dataset.eventToggle = '';
      slot.setAttribute('role', 'button');
      slot.tabIndex = 0;
      slot.title = 'Click to mark done: ' + e.title;
      slot.appendChild(el('b', null, e.title));
      slot.appendChild(el('span', null, e.start_label + '–' + e.end_label));
      items.push({ start: s, end: en, node: slot, label: e.title });
    });
    blockItems().forEach(function (it) {
      var b = it.block;
      var slot = el('div', 'slot block kind-' + b.kind);
      slot.dataset.blockId = b.id;
      slot.dataset.blockStart = String(b.start);
      slot.dataset.blockDuration = String(b.duration);
      slot.title = 'Drag to move, or use Earlier and Later in the list';
      slot.appendChild(el('b', null, b.title));
      slot.appendChild(el('span', null, clock(b.start) + '–' + clock(b.start + b.duration)));
      items.push({ start: it.start, end: it.end, node: slot, label: b.title });
    });
    // Overlapping items share a cluster and sit side by side in lanes, so no title is hidden.
    items.sort(function (a, b) { return a.start - b.start || b.end - a.end; });
    var clusters = [], current = null;
    items.forEach(function (it) {
      if (current && it.start < current.end) {
        current.items.push(it);
        current.end = Math.max(current.end, it.end);
      } else {
        current = { end: it.end, items: [it] };
        clusters.push(current);
      }
    });
    clusters.forEach(function (cluster) {
      var laneEnds = [];
      cluster.items.forEach(function (it) {
        var lane = laneEnds.findIndex(function (end) { return end <= it.start; });
        if (lane === -1) { lane = laneEnds.length; laneEnds.push(it.end); } else { laneEnds[lane] = it.end; }
        it.lane = lane;
      });
      cluster.items.forEach(function (it) {
        var top = (Math.max(it.start, START) - START) * PX;
        var height = Math.max((Math.min(it.end, END) - Math.max(it.start, START)) * PX, 18);
        var width = 100 / laneEnds.length;
        it.node.style.top = top + 'px';
        it.node.style.height = height + 'px';
        it.node.style.left = 'calc(' + (it.lane * width) + '% + .4rem)';
        it.node.style.right = 'auto';
        it.node.style.width = 'calc(' + width + '% - .5rem)';
        if (laneEnds.length > 1) it.node.classList.add('overlap');
        tl.appendChild(it.node);
      });
    });
  }

  function renderAgenda() {
    var list = $('today-agenda');
    if (!list) return;
    list.textContent = '';
    if (!seed.events.length) list.appendChild(el('li', 'row muted', 'No calendar events'));
    seed.events.forEach(function (e) {
      var li = el('li', 'row');
      li.dataset.markKey = 'cal:' + e.id;
      li.appendChild(el('span', 'time', e.all_day ? 'All day' : e.start_label + '–' + e.end_label));
      var body = el('span', 'grow');
      if (e.url) {
        var a = el('a', null, e.title);
        a.href = e.url; a.target = '_blank'; a.rel = 'noopener';
        body.appendChild(a);
      } else {
        body.appendChild(document.createTextNode(e.title));
      }
      if (e.tentative) body.appendChild(el('span', 'badge', 'tentative'));
      if (e.free) body.appendChild(el('span', 'badge', 'free'));
      if (e.join_url) {
        var j = el('a', null, 'Join'); j.href = e.join_url; j.target = '_blank'; j.rel = 'noopener';
        body.appendChild(document.createTextNode(' ')); body.appendChild(j);
      }
      li.appendChild(body);
      var mark = el('button', null, 'Done');
      mark.type = 'button'; mark.dataset.markToggle = ''; mark.dataset.off = 'Done'; mark.dataset.on = 'Undo done';
      li.appendChild(mark);
      list.appendChild(li);
    });
  }

  function lengthOptions(selected) {
    var select = el('select');
    for (var m = 15; m <= 240; m += 15) {
      var option = el('option', null, m + ' min');
      option.value = String(m);
      if (m === selected) option.selected = true;
      select.appendChild(option);
    }
    return select;
  }

  function labelled(text, control) {
    var label = el('label', 'edit-field');
    label.appendChild(el('span', null, text));
    label.appendChild(control);
    return label;
  }

  function editForm(b) {
    var form = el('form', 'block-edit');
    form.dataset.blockEditForm = b.id;
    var title = el('input');
    title.type = 'text'; title.maxLength = 80; title.value = b.title; title.dataset.editTitle = '';
    var start = el('input');
    start.type = 'time'; start.value = clock(b.start); start.required = true; start.dataset.editStart = '';
    var length = lengthOptions(b.duration); length.dataset.editDuration = '';
    var save = el('button', 'primary', 'Save'); save.type = 'submit';
    var cancel = el('button', null, 'Cancel'); cancel.type = 'button'; cancel.dataset.blockCancel = '';
    form.appendChild(labelled('Title', title));
    form.appendChild(labelled('Start', start));
    form.appendChild(labelled('Length', length));
    var actions = el('span', 'controls');
    actions.appendChild(save); actions.appendChild(cancel);
    form.appendChild(actions);
    return form;
  }

  // Shared by the preset buttons and the custom form. Returns an error message, or null when added.
  function addBlock(kind, start, duration, title) {
    if (start === null) return 'Choose a start time.';
    if (start < START || start + duration > END) return 'Blocks must fit between ' + clock(START) + ' and ' + clock(END) + '.';
    counter += 1;
    blocks.push({ id: 'b' + Date.now() + '-' + counter, kind: kind, title: (title || '').trim() || KINDS[kind].label, start: start, duration: duration });
    saveBlocks();
    renderToday();
    return null;
  }

  function renderBlocks() {
    var list = $('block-list');
    if (!list) return;
    list.textContent = '';
    var all = blockItems().concat(timedEvents().map(function (e) {
      return { id: 'e' + e.id, start: e.start_min, end: e.end_min, title: e.title };
    }));
    if (!blocks.length) list.appendChild(el('li', 'muted', 'No blocks yet. Add focus time, exercise or a walk above.'));
    blocks.slice().sort(function (a, b) { return a.start - b.start; }).forEach(function (b) {
      var li = el('li', 'block-row');
      li.dataset.blockId = b.id;
      li.appendChild(el('span', 'swatch kind-' + b.kind));
      if (b.id === editingId) {
        li.appendChild(editForm(b));
        list.appendChild(li);
        return;
      }
      var text = el('span', 'grow', b.title + ' · ' + clock(b.start) + '–' + clock(b.start + b.duration) + ' (' + b.duration + ' min)');
      li.appendChild(text);
      var controls = el('span', 'controls');
      [['edit', 'Edit'], ['earlier', 'Earlier 15m'], ['later', 'Later 15m'], ['shorter', 'Shorter'], ['longer', 'Longer'], ['delete', 'Delete']].forEach(function (pair) {
        var btn = el('button', null, pair[1]);
        btn.type = 'button';
        btn.dataset.blockAction = pair[0];
        controls.appendChild(btn);
      });
      li.appendChild(controls);
      var conflicts = all.filter(function (other) {
        return other.id !== b.id && overlaps({ start: b.start, end: b.start + b.duration }, other);
      }).map(function (other) { return other.title || other.block && other.block.title || 'an item'; });
      if (conflicts.length) li.appendChild(el('span', 'warn', 'Overlaps ' + conflicts.join(', ')));
      list.appendChild(li);
    });
  }

  function renderToday() {
    renderTimeline();
    renderAgenda();
    renderBlocks();
    applyMarks();
  }

  function findBlock(id) {
    for (var i = 0; i < blocks.length; i++) if (blocks[i].id === id) return blocks[i];
    return null;
  }

  function changeBlock(id, action) {
    var b = findBlock(id);
    if (!b) return;
    var error = null;
    if (action === 'delete') {
      blocks = blocks.filter(function (x) { return x.id !== id; });
    } else if (action === 'earlier' || action === 'later') {
      var next = b.start + (action === 'later' ? 15 : -15);
      if (next < START || next + b.duration > END) error = 'That block must stay between ' + clock(START) + ' and ' + clock(END) + '.';
      else b.start = next;
    } else if (action === 'shorter') {
      if (b.duration <= 15) error = 'A block is at least 15 minutes.';
      else b.duration -= 15;
    } else if (action === 'longer') {
      if (b.start + b.duration + 15 > END) error = 'That block would run past ' + clock(END) + '.';
      else b.duration += 15;
    }
    if (error) { say(error); return; }
    saveBlocks();
    renderToday();
  }

  var blockForm = $('block-form');
  if (blockForm) {
    var kindSelect = blockForm.elements.kind;
    var titleInput = blockForm.elements.title;
    var durationSelect = blockForm.elements.duration;
    kindSelect.addEventListener('change', function () {
      var kind = KINDS[kindSelect.value] || KINDS.custom;
      durationSelect.value = String(kind.minutes);
      if (kindSelect.value !== 'custom') titleInput.value = kind.label;
    });
    blockForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var error = $('block-error');
      var kind = kindSelect.value;
      var message = addBlock(kind, parseClock(blockForm.elements.start.value), Number(durationSelect.value), titleInput.value);
      if (message) { if (error) error.textContent = message; return; }
      if (error) error.textContent = '';
      titleInput.value = kind === 'custom' ? '' : KINDS[kind].label;
    });
    blockForm.hidden = false;
  }

  document.querySelectorAll('[data-preset]').forEach(function (button) {
    button.hidden = false;
  });
  var presetsNode = $('block-presets');
  if (presetsNode) presetsNode.hidden = false;

  function presetClick(button) {
    var error = $('block-error');
    var kind = button.dataset.preset;
    var start = blockForm ? parseClock(blockForm.elements.start.value) : null;
    var message = addBlock(kind, start, KINDS[kind].minutes, KINDS[kind].label);
    if (error) error.textContent = message || '';
    if (message) say(message);
  }

  function saveEdit(form) {
    var id = form.dataset.blockEditForm;
    var b = findBlock(id);
    if (!b) return;
    var start = parseClock(form.querySelector('[data-edit-start]').value);
    var duration = Number(form.querySelector('[data-edit-duration]').value);
    var title = form.querySelector('[data-edit-title]').value.trim() || KINDS[b.kind].label;
    if (start === null || start < START || start + duration > END) {
      say('Blocks must fit between ' + clock(START) + ' and ' + clock(END) + '.');
      return;
    }
    b.title = title; b.start = start; b.duration = duration;
    editingId = null;
    saveBlocks();
    renderToday();
  }

  /* ---------- Export ---------- */
  function exportTasks() {
    var text = todos.map(function (t) { return '- [' + (t.done ? 'x' : ' ') + '] ' + t.text; }).join('\n') + '\n';
    var url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }));
    var a = document.createElement('a');
    a.href = url;
    a.download = 'tasks.md';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    say('Downloaded tasks.md. Replace your tasks.md with it to keep these tasks in the next run.');
  }

  /* ---------- Events ---------- */
  document.addEventListener('change', function (event) {
    var box = event.target.closest && event.target.closest('[data-todo-toggle]');
    if (!box) return;
    var id = box.closest('[data-todo-id]').dataset.todoId;
    todos.forEach(function (t) { if (t.id === id) t.done = box.checked; });
    saveTodos();
    renderTodos();
  });

  function dragMinutes(dy) { return Math.round(dy / PX / 15) * 15; }

  function beginDrag(event, slot) {
    var b = findBlock(slot.dataset.blockId);
    if (!b) return;
    drag = { id: b.id, node: slot, pointer: event.pointerId, startY: event.clientY, origin: b.start,
           duration: b.duration, current: b.start, moved: false };
    slot.setPointerCapture(event.pointerId);
    slot.classList.add('dragging');
  }

  function moveDrag(event) {
    var dy = event.clientY - drag.startY;
    if (Math.abs(dy) > 4) drag.moved = true;
    var next = Math.min(END - drag.duration, Math.max(START, drag.origin + dragMinutes(dy)));
    if (next === drag.current) return;
    drag.current = next;
    drag.node.style.top = ((next - START) * PX) + 'px';
    say('Moving ' + drag.node.querySelector('b').textContent + ' to ' + clock(next));
  }

  function endDrag(cancelled) {
    if (!drag) return;
    var finished = drag;
    drag = null;
    finished.node.classList.remove('dragging');
    try { finished.node.releasePointerCapture(finished.pointer); } catch (e) { /* already released */ }
    if (finished.moved) suppressClick = true;
    if (cancelled || finished.current === finished.origin) { renderToday(); return; }
    var b = findBlock(finished.id);
    if (b) { b.start = finished.current; saveBlocks(); }
    renderToday();
    say('Moved to ' + clock(finished.current) + '.');
  }

  var timelineNode = $('timeline');
  if (timelineNode) {
    timelineNode.addEventListener('pointerdown', function (event) {
      if (event.button !== 0) return;
      var slot = event.target.closest && event.target.closest('.slot.block');
      if (slot) beginDrag(event, slot);
    });
    timelineNode.addEventListener('pointermove', function (event) {
      if (drag && event.pointerId === drag.pointer) moveDrag(event);
    });
    timelineNode.addEventListener('pointerup', function (event) {
      if (drag && event.pointerId === drag.pointer) endDrag(false);
    });
    timelineNode.addEventListener('pointercancel', function (event) {
      if (drag && event.pointerId === drag.pointer) endDrag(true);
    });
  }

  document.addEventListener('click', function (event) {
    if (suppressClick) { suppressClick = false; event.stopPropagation(); event.preventDefault(); return; }
    var target = event.target;
    var close = function (sel) { return target.closest && target.closest(sel); };
    var del = close('[data-todo-delete]');
    if (del) {
      var id = del.closest('[data-todo-id]').dataset.todoId;
      todos = todos.filter(function (t) { return t.id !== id; });
      saveTodos();
      renderTodos();
      return;
    }
    var blockButton = close('[data-block-action]');
    if (blockButton) {
      var blockId = blockButton.closest('[data-block-id]').dataset.blockId;
      if (blockButton.dataset.blockAction === 'edit') { editingId = blockId; renderToday(); return; }
      changeBlock(blockId, blockButton.dataset.blockAction);
      return;
    }
    if (close('[data-block-cancel]')) { editingId = null; renderToday(); return; }
    var preset = close('[data-preset]');
    if (preset) { presetClick(preset); return; }
    var slot = close('[data-event-toggle]');
    if (slot) { toggleMark(slot.dataset.markKey); return; }
    var mark = close('[data-mark-toggle]');
    if (mark) { toggleMark(mark.closest('[data-mark-key]').dataset.markKey); return; }
    if (close('#todo-export')) exportTasks();
  });

  document.addEventListener('submit', function (event) {
    var form = event.target.closest && event.target.closest('[data-block-edit-form]');
    if (!form) return;
    event.preventDefault();
    saveEdit(form);
  });

  document.addEventListener('keydown', function (event) {
    if ((event.key === 'Enter' || event.key === ' ') && event.target.matches && event.target.matches('[data-event-toggle]')) {
      event.preventDefault();
      toggleMark(event.target.dataset.markKey);
    }
  });

  var addForm = $('todo-add');
  if (addForm) {
    addForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var input = addForm.elements.text;
      var text = input.value.trim();
      if (!text) return;
      counter += 1;
      todos.push({ id: 'n' + Date.now() + '-' + counter, text: text, done: false });
      saveTodos();
      renderTodos();
      input.value = '';
      input.focus();
    });
  }

  ['todo-add', 'todo-export'].forEach(function (id) {
    var node = $(id);
    if (node) node.hidden = false;
  });
  renderTodos();
  renderToday();
})();
