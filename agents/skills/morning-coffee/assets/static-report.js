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
      slot.appendChild(el('b', null, b.title));
      slot.appendChild(el('span', null, clock(b.start) + '–' + clock(b.start + b.duration)));
      items.push({ start: it.start, end: it.end, node: slot, label: b.title });
    });
    items.forEach(function (it) {
      var top = (Math.max(it.start, START) - START) * PX;
      var height = Math.max((Math.min(it.end, END) - Math.max(it.start, START)) * PX, 18);
      it.node.style.top = top + 'px';
      it.node.style.height = height + 'px';
      items.forEach(function (other) {
        if (other !== it && overlaps(it, other)) it.node.classList.add('overlap');
      });
      tl.appendChild(it.node);
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
      var text = el('span', 'grow', b.title + ' · ' + clock(b.start) + '–' + clock(b.start + b.duration) + ' (' + b.duration + ' min)');
      li.appendChild(text);
      var controls = el('span', 'controls');
      [['earlier', 'Earlier 15m'], ['later', 'Later 15m'], ['shorter', 'Shorter'], ['longer', 'Longer'], ['delete', 'Delete']].forEach(function (pair) {
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
      var start = parseClock(blockForm.elements.start.value);
      var duration = Number(durationSelect.value);
      var title = titleInput.value.trim() || KINDS[kind].label;
      var message = null;
      if (start === null) message = 'Choose a start time.';
      else if (start < START || start + duration > END) message = 'Blocks must fit between ' + clock(START) + ' and ' + clock(END) + '.';
      if (message) { if (error) error.textContent = message; return; }
      counter += 1;
      blocks.push({ id: 'b' + Date.now() + '-' + counter, kind: kind, title: title, start: start, duration: duration });
      saveBlocks();
      if (error) error.textContent = '';
      titleInput.value = kind === 'custom' ? '' : KINDS[kind].label;
      renderToday();
    });
    blockForm.hidden = false;
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

  document.addEventListener('click', function (event) {
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
      changeBlock(blockButton.closest('[data-block-id]').dataset.blockId, blockButton.dataset.blockAction);
      return;
    }
    var slot = close('[data-event-toggle]');
    if (slot) { toggleMark(slot.dataset.markKey); return; }
    var mark = close('[data-mark-toggle]');
    if (mark) { toggleMark(mark.closest('[data-mark-key]').dataset.markKey); return; }
    if (close('#todo-export')) exportTasks();
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
