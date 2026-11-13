#!/usr/bin/env python3
"""Render the Morning Coffee report. Standard library only."""
import argparse, html, json, shutil
from datetime import datetime, timedelta
from pathlib import Path

E = lambda v: html.escape(str(v if v is not None else ''), quote=True)
SAFE = ('https://', 'http://')


SCRIPT = r"""
(function () {
  var seedNode = document.getElementById('mc-seed');
  if (!seedNode) return;
  var seed = JSON.parse(seedNode.textContent);
  var TODO_KEY = 'morning-coffee:todos';
  var MARK_KEY = 'morning-coffee:marks:' + seed.date;
  var status = document.getElementById('mc-status');
  var todoList = document.getElementById('todo');

  function read(key, fallback) {
    try { var raw = localStorage.getItem(key); return raw === null ? fallback : JSON.parse(raw); }
    catch (e) { return fallback; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; }
    catch (e) { return false; }
  }
  function say(message) { if (status) status.textContent = message; }

  var todos = read(TODO_KEY, null);
  if (!Array.isArray(todos)) {
    todos = seed.tasks.map(function (t, i) { return { id: 't' + i, text: t.text, done: t.done }; });
  }
  var marks = read(MARK_KEY, {});
  if (!marks || typeof marks !== 'object') marks = {};
  var counter = 0;

  function saveTodos() {
    if (!write(TODO_KEY, todos)) say('This browser would not save the change. Download tasks.md to keep it.');
  }

  function renderTodos() {
    if (!todoList) return;
    todoList.textContent = '';
    if (!todos.length) {
      var empty = document.createElement('li');
      empty.textContent = 'None — add a task below';
      todoList.appendChild(empty);
    }
    todos.forEach(function (t) {
      var li = document.createElement('li');
      li.dataset.todoId = t.id;
      var box = document.createElement('input');
      box.type = 'checkbox';
      box.checked = !!t.done;
      box.dataset.todoToggle = '';
      box.setAttribute('aria-label', 'Done: ' + t.text);
      var label = document.createElement('span');
      label.textContent = ' ' + t.text;
      if (t.done) label.className = 'done';
      var del = document.createElement('button');
      del.type = 'button';
      del.textContent = 'Delete';
      del.dataset.todoDelete = '';
      li.appendChild(box);
      li.appendChild(label);
      li.appendChild(document.createTextNode(' '));
      li.appendChild(del);
      todoList.appendChild(li);
    });
  }

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
    say('Downloaded tasks.md. Replace ~/daily-briefs/coffee/tasks.md with it to keep these tasks in the next run.');
  }

  document.addEventListener('change', function (event) {
    var box = event.target.closest && event.target.closest('[data-todo-toggle]');
    if (!box) return;
    var id = box.closest('li').dataset.todoId;
    todos.forEach(function (t) { if (t.id === id) t.done = box.checked; });
    saveTodos();
    renderTodos();
  });

  document.addEventListener('click', function (event) {
    var target = event.target;
    var del = target.closest && target.closest('[data-todo-delete]');
    if (del) {
      var id = del.closest('li').dataset.todoId;
      todos = todos.filter(function (t) { return t.id !== id; });
      saveTodos();
      renderTodos();
      return;
    }
    var mark = target.closest && target.closest('[data-mark-toggle]');
    if (mark) {
      var key = mark.closest('[data-mark-key]').dataset.markKey;
      if (marks[key]) delete marks[key]; else marks[key] = true;
      if (!write(MARK_KEY, marks)) say('This browser would not save the change.');
      applyMarks();
      return;
    }
    if (target.closest && target.closest('#todo-export')) exportTasks();
  });

  var addForm = document.getElementById('todo-add');
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

  // Progressive enhancement: reveal controls only once the script runs.
  ['todo-add', 'todo-export'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.hidden = false;
  });
  renderTodos();
  applyMarks();
})();
"""

def parse_tasks(text):
    """`- [ ] x` / `- [x] x` lines -> [(done, text)]; other lines are ignored."""
    tasks = []
    for line in text.splitlines():
        s = line.strip()
        if s[:5].lower() in ('- [ ]', '- [x]') and s[5:6] in ('', ' '):
            tasks.append((s[3].lower() == 'x', s[5:].strip()))
    return tasks


def _key(section, item):
    ident = item.get('url') or item.get('id') or item.get('title', '')
    return (section, ident, item.get('state', ''))


def new_items(previous, current):
    """Items in `current` whose (section, identity, state) is absent from `previous`."""
    if previous is None:
        return []
    seen = {_key(s, i) for s in ('reviews', 'authored', 'incidents', 'slack', 'notion')
            for i in previous.get(s, [])}
    return [(s, i) for s in ('reviews', 'authored', 'incidents', 'slack', 'notion')
            for i in current.get(s, []) if _key(s, i) not in seen]


def oncall_alert(oncall, now):
    """Return (label, shift) when `now` is inside a shift or <24h before the next one."""
    for name in ('current_shift', 'next_shift'):
        shift = (oncall or {}).get(name)
        if not shift or not shift.get('start') or not shift.get('end'):
            continue
        start, end = datetime.fromisoformat(shift['start']), datetime.fromisoformat(shift['end'])
        if start <= now < end:
            return 'On call now', shift
        if start - timedelta(hours=24) <= now < start:
            return 'On call soon', shift
    return None


def hhmm(value, tz_of=None):
    return datetime.fromisoformat(value).strftime('%H:%M')


def link(url, text):
    return f'<a href="{E(url)}" target="_blank" rel="noopener">{E(text)}</a>' if str(url).startswith(SAFE) else E(text)


def _mark(off, on):
    """Done/dismiss control. The static report keeps its state in the browser (see SCRIPT)."""
    return f' <button type=button data-mark-toggle data-off="{E(off)}" data-on="{E(on)}">{E(off)}</button>'


def _event(ev):
    key = 'cal:' + str(ev.get('id') or f"{ev.get('title', '')}|{ev.get('start', '')}")
    if ev.get('all_day'):
        when = 'All day'
    else:
        when = f"{hhmm(ev['start'])}–{hhmm(ev['end'])}"
    flags = ''.join(f' <i>{f}</i>' for f, on in (('tentative', ev.get('tentative')), ('free', ev.get('free'))) if on)
    join = f" {link(ev['join_url'], 'Join')}" if ev.get('join_url') else ''
    return (f'<li data-mark-key="{E(key)}"><b>{E(when)}</b> {link(ev.get("url", ""), ev.get("title", ""))}{flags}{join}'
            f'{_mark("Done", "Undo done")}</li>')


def _pr(item, authored):
    tag = ' <i>Draft</i>' if item.get('draft') else ''
    extra = item.get('state') if authored else f"@{item.get('author', '?')} · {item.get('request', '')}"
    key = ('mine:' if authored else 'rev:') + str(item.get('url', ''))
    return (f'<li data-mark-key="{E(key)}">{link(item["url"], item["title"])}{tag} <small>{E(item.get("repo", ""))} · {E(extra)}</small>'
            f'{_mark("Mark done locally", "Undo local done")}</li>')


def render(snapshot, previous, tasks_text, now=None):
    now = now or datetime.fromisoformat(snapshot['collected_at'])
    events = sorted(snapshot.get('calendar', []), key=lambda e: (not e.get('all_day'), e.get('start', '')))
    reviews = sorted(snapshot.get('reviews', []), key=lambda r: r.get('updated_at') or '9999')
    mine = snapshot.get('authored', [])
    tasks = parse_tasks(tasks_text)
    fresh = new_items(previous, snapshot)
    alert = oncall_alert(snapshot.get('oncall'), now)
    gaps = [f"{k}: {v.get('status')}{' — ' + v['note'] if v.get('note') else ''}"
            for k, v in snapshot.get('sources', {}).items() if v.get('status') != 'complete']
    out = [f"<!doctype html><meta charset=utf-8><title>Morning Coffee {E(snapshot['date'])}</title>",
           '<style>body{font:16px system-ui;max-width:52rem;margin:2rem auto;padding:0 1rem}'
           'h2{margin-top:2rem}li{margin:.3rem 0}.alert{background:#fde;padding:.5rem 1rem}'
           '.done,.is-done{text-decoration:line-through;opacity:.55}button{font:inherit}</style>',
           f"<h1>Morning Coffee · {E(snapshot['date'])}</h1>"]
    if gaps:
        out.append(f"<p id=coverage>Coverage limits: {E('; '.join(gaps))}</p>")
    if alert:
        label, shift = alert
        out.append(f"<p class=alert id=oncall><b>{E(label)}</b> {E(hhmm(shift['start']))} → {E(hhmm(shift['end']))}</p>")
    out.append('<h2>Today</h2><ul id=today>' + (''.join(_event(e) for e in events) or '<li>None</li>') + '</ul>')
    out.append('<h2>To do</h2><ul id=todo>' + (''.join(
        f"<li>{'☑' if d else '☐'} {E(t)}</li>" for d, t in tasks) or '<li>None — add lines to tasks.md</li>') + '</ul>'
               + '<form id=todo-add hidden><input name=text maxlength=200 required placeholder="Add a task" aria-label="Add a task"> '
               + '<button type=submit>Add</button></form>'
               + '<p><button type=button id=todo-export hidden>Download tasks.md</button></p>')
    out.append(f'<h2>Reviews waiting ({len(reviews)})</h2><ul id=reviews>' + (''.join(_pr(r, False) for r in reviews) or '<li>None</li>') + '</ul>')
    out.append(f'<h2>My open PRs ({len(mine)})</h2><ul id=mine>' + (''.join(_pr(r, True) for r in mine) or '<li>None</li>') + '</ul>')
    if previous is not None:
        out.append(f'<h2>New since last run ({len(fresh)})</h2><ul id=new>' + (''.join(
            f'<li data-mark-key="{E("new:" + s + ":" + str(i.get("url") or i.get("id") or i.get("title", "")))}">{E(s)}: {link(i.get("url", ""), i.get("title", ""))}'
            f'{_mark("Dismiss", "Restore")}</li>' for s, i in fresh) or '<li>Nothing new</li>') + '</ul>')
    out.append('<p id=mc-status role=status></p>')
    seed = {'date': snapshot['date'], 'tasks': [{'text': t, 'done': d} for d, t in tasks]}
    out.append('<script id=mc-seed type=application/json>' + json.dumps(seed).replace('<', '\\u003c') + '</script>')
    out.append('<script>' + SCRIPT + '</script>')
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('snapshot')
    ap.add_argument('--dir', required=True)
    a = ap.parse_args()
    d = Path(a.dir).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    snap = json.loads(Path(a.snapshot).read_text())
    prev_path, tasks_path = d / 'previous.json', d / 'tasks.md'
    previous = json.loads(prev_path.read_text()) if prev_path.exists() else None
    tasks_path.touch(exist_ok=True)
    (d / 'report.html').write_text(render(snap, previous, tasks_path.read_text()))
    shutil.copyfile(a.snapshot, prev_path)
    print(f"report: {d / 'report.html'} · new: {len(new_items(previous, snap))}")


if __name__ == '__main__':
    main()
