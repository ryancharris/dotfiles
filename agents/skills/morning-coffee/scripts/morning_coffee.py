#!/usr/bin/env python3
"""Render the Morning Coffee report as one static HTML file. Standard library only.

The page keeps its styling and script inline (assets/static-report.css and
assets/static-report.js) so the file works from disk with no server.
"""
import argparse, html, json, shutil
from datetime import datetime, timedelta
from pathlib import Path

E = lambda v: html.escape(str(v if v is not None else ''), quote=True)
SAFE = ('https://', 'http://')
ASSETS = Path(__file__).resolve().parents[1] / 'assets'
DAY_START, DAY_END = 8 * 60, 19 * 60   # display window, local time
SECTIONS = ('reviews', 'authored', 'incidents', 'slack', 'notion')


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
    seen = {_key(s, i) for s in SECTIONS for i in previous.get(s, [])}
    return [(s, i) for s in SECTIONS for i in current.get(s, []) if _key(s, i) not in seen]


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


def minutes(value):
    dt = datetime.fromisoformat(value)
    return dt.hour * 60 + dt.minute


def link(url, text):
    return f'<a href="{E(url)}" target="_blank" rel="noopener">{E(text)}</a>' if str(url).startswith(SAFE) else E(text)


def event_key(ev):
    return 'cal:' + str(ev.get('id') or f"{ev.get('title', '')}|{ev.get('start', '')}")


def event_seed(ev):
    """Timed events carry minutes-from-midnight for the live timeline; all-day events do not."""
    out = {'id': str(ev.get('id') or event_key(ev)), 'title': ev.get('title', ''), 'all_day': bool(ev.get('all_day')),
           'tentative': bool(ev.get('tentative')), 'free': bool(ev.get('free')),
           'url': ev.get('url', ''), 'join_url': ev.get('join_url', '')}
    if not out['all_day']:
        out.update({'start_min': minutes(ev['start']), 'end_min': minutes(ev['end']),
                    'start_label': hhmm(ev['start']), 'end_label': hhmm(ev['end'])})
    return out


def _event_row(ev):
    key = event_key(ev)
    when = 'All day' if ev.get('all_day') else f"{hhmm(ev['start'])}–{hhmm(ev['end'])}"
    flags = ''.join(f'<span class="badge">{f}</span>' for f, on in (('tentative', ev.get('tentative')), ('free', ev.get('free'))) if on)
    join = f" {link(ev['join_url'], 'Join')}" if ev.get('join_url') else ''
    return (f'<li class="row" data-mark-key="{E(key)}"><span class="time">{E(when)}</span>'
            f'<span class="grow">{link(ev.get("url", ""), ev.get("title", ""))}{flags}{join}</span>'
            f'{_mark("Done", "Undo done")}</li>')


def _mark(off, on):
    """Done/dismiss control. State is kept in the browser (see static-report.js)."""
    return f'<button type="button" data-mark-toggle data-off="{E(off)}" data-on="{E(on)}">{E(off)}</button>'


def _pr(item, authored):
    tag = '<span class="badge">Draft</span>' if item.get('draft') else ''
    extra = item.get('state') if authored else f"@{item.get('author', '?')}"
    if not authored:
        tag = _request_badge(item.get('request')) + ' ' + tag
    key = ('mine:' if authored else 'rev:') + str(item.get('url', ''))
    return (f'<li class="row" data-mark-key="{E(key)}"><span class="grow"><span class="pr-title">{link(item["url"], item["title"])}</span>{tag}'
            f'<small class="pr-meta">{E(item.get("repo", ""))} · {E(extra)}</small></span>'
            f'{_mark("Mark done locally", "Undo local done")}</li>')


REQUEST_BADGES = {
    'Direct': ('👤', 'Direct', 'Review requested from you'),
    'Team': ('👥', 'Team', 'Review requested from your team'),
}


def _request_badge(request):
    icon, label, title = REQUEST_BADGES.get(request, ('❔', request or 'Unknown', 'Review request type unknown'))
    return f'<span class="req req-{E(label.lower())}" title="{E(title)}" aria-label="{E(title)}">{icon} {E(label)}</span>'


def _by_repo(items, row):
    """Group rows under their repository, busiest repo first, keeping each group's order."""
    groups = {}
    for item in items:
        groups.setdefault(item.get('repo') or 'unknown repository', []).append(item)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))
    return ''.join(
        f'<div class="repo-group"><h3 class="repo-head"><span>{E(repo)}</span>'
        f'<span class="count">{len(rows)}</span></h3><ul class="plain">'
        + ''.join(row(r) for r in rows) + '</ul></div>'
        for repo, rows in ordered) or '<p class="row muted">None</p>'


def _dates(now):
    return f"{now.strftime('%A')}, {now.day} {now.strftime('%B %Y')}"


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
    open_tasks = [t for t in tasks if not t[0]]

    out = ['<!doctype html><html lang="en"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           f"<title>Morning Coffee · {E(snapshot['date'])}</title>",
           f'<style>{(ASSETS / "static-report.css").read_text()}</style></head><body><main class="page">',
           f'<header class="masthead"><p class="kicker">Morning Coffee</p><h1>{E(_dates(now))}</h1>'
           f'<p class="meta">Collected {E(hhmm(snapshot["collected_at"]))} · {E(snapshot.get("timezone", ""))}</p></header>']
    out.append('<ul class="stats plain">'
               f'<li><b>{len(events)}</b> events</li><li><b>{len(open_tasks)}</b> open tasks</li>'
               f'<li><b>{len(reviews)}</b> reviews waiting</li><li><b>{len(mine)}</b> my open PRs</li>'
               + (f'<li><b>{len(fresh)}</b> new</li>' if previous is not None else '') + '</ul>')
    if gaps:
        out.append(f"<p class=\"notice\" id=\"coverage\">Coverage limits: {E('; '.join(gaps))}</p>")
    if alert:
        label, shift = alert
        out.append(f'<p class="notice alert" id="oncall"><b>{E(label)}</b> {E(hhmm(shift["start"]))} → {E(hhmm(shift["end"]))}</p>')

    # Today: the live timeline, custom blocks and agenda are drawn by the script from the seed.
    fallback = ''.join(_event_row(e) for e in events) or '<li class="row muted">None</li>'
    out.append('<section class="card" id="today"><header><h2>Today</h2>'
               '<p class="muted">08:00–19:00 · blocks and done marks are saved in this browser</p></header>'
               '<div id="today-all-day" class="all-day"></div>'
               '<div class="today-grid">'
               '<div><div class="timeline" id="timeline"></div></div>'
               '<div>'
               '<h3 class="side-h">Agenda</h3><ul class="plain" id="today-agenda"></ul>'
               '<ul class="plain agenda-fallback">' + fallback + '</ul>'
               '<h3 class="side-h">Your blocks</h3>'
               '<ul class="plain blocks" id="block-list"></ul>'
               '<form id="block-form" class="block-form" hidden>'
               '<label>Type<select name="kind">'
               '<option value="focus">Focus</option><option value="exercise">Exercise</option>'
               '<option value="dog-walk">Dog walk</option><option value="lunch">Lunch</option>'
               '<option value="learning">Learning</option><option value="custom">Custom</option></select></label>'
               '<label>Title<input name="title" value="Focus" maxlength="80"></label>'
               '<label>Start<input type="time" name="start" value="13:00" required></label>'
               '<label>Length<select name="duration">'
               + ''.join(f'<option value="{m}"{" selected" if m == 120 else ""}>{m} min</option>' for m in range(15, 241, 15))
               + '</select></label>'
               '<button type="submit" class="primary">Add block</button>'
               '<p class="form-error wide" id="block-error" role="alert"></p>'
               '</form>'
               '</div></div></section>')

    todo_items = ''.join(f'<li class="row" data-todo-id="s{i}"><span class="grow">{"☑" if d else "☐"} {E(t)}</span></li>'
                         for i, (d, t) in enumerate(tasks)) or '<li class="row muted">None — add a task below</li>'
    out.append('<section class="card" id="todo-card"><header><h2>To do</h2><p class="muted">Saved in this browser · export to keep</p></header>'
               f'<ul class="plain" id="todo">{todo_items}</ul>' +
               '<form id="todo-add" class="todo-add" hidden><input name="text" maxlength="200" required placeholder="Add a task" aria-label="Add a task">'
               '<button type="submit" class="primary">Add</button></form>'
               '<p><button type="button" id="todo-export" hidden>Download tasks.md</button></p></section>')

    review_rows = _by_repo(reviews, lambda r: _pr(r, False))
    mine_rows = _by_repo(mine, lambda r: _pr(r, True))
    out.append(f'<section class="card" id="reviews"><header><h2>Reviews waiting ({len(reviews)})</h2></header>'
               f'{review_rows}</section>')
    out.append(f'<section class="card" id="mine"><header><h2>My open PRs ({len(mine)})</h2></header>'
               f'{mine_rows}</section>')
    if previous is not None:
        rows = ''.join(
            f'<li class="row" data-mark-key="{E("new:" + s + ":" + str(i.get("url") or i.get("id") or i.get("title", "")))}">'
            f'<span class="grow">{E(s)}: {link(i.get("url", ""), i.get("title", ""))}</span>{_mark("Dismiss", "Restore")}</li>'
            for s, i in fresh) or '<li class="row muted">Nothing new</li>'
        out.append(f'<section class="card" id="new"><header><h2>New since last run ({len(fresh)})</h2></header>'
                   f'<ul class="plain">{rows}</ul></section>')

    out.append('<p id="mc-status" role="status"></p>')
    out.append('<p class="footnote">Private to this browser. Nothing is sent anywhere; export tasks.md to carry todos into the next run.</p>')
    seed = {'date': snapshot['date'], 'window': [DAY_START, DAY_END],
            'tasks': [{'text': t, 'done': d} for d, t in tasks],
            'events': [event_seed(e) for e in events]}
    out.append('<script id="mc-seed" type="application/json">' + json.dumps(seed).replace('<', '\\u003c') + '</script>')
    out.append(f'<script>{(ASSETS / "static-report.js").read_text()}</script>')
    out.append('</main></body></html>')
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
