#!/usr/bin/env python3
"""Render the Morning Coffee report. Standard library only."""
import argparse, html, json, shutil
from datetime import datetime, timedelta
from pathlib import Path

E = lambda v: html.escape(str(v if v is not None else ''), quote=True)
SAFE = ('https://', 'http://')


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


def _event(ev):
    if ev.get('all_day'):
        when = 'All day'
    else:
        when = f"{hhmm(ev['start'])}–{hhmm(ev['end'])}"
    flags = ''.join(f' <i>{f}</i>' for f, on in (('tentative', ev.get('tentative')), ('free', ev.get('free'))) if on)
    join = f" {link(ev['join_url'], 'Join')}" if ev.get('join_url') else ''
    return f"<li><b>{E(when)}</b> {link(ev.get('url', ''), ev.get('title', ''))}{flags}{join}</li>"


def _pr(item, authored):
    tag = ' <i>Draft</i>' if item.get('draft') else ''
    extra = item.get('state') if authored else f"@{item.get('author', '?')} · {item.get('request', '')}"
    return f"<li>{link(item['url'], item['title'])}{tag} <small>{E(item.get('repo', ''))} · {E(extra)}</small></li>"


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
           'h2{margin-top:2rem}li{margin:.3rem 0}.alert{background:#fde;padding:.5rem 1rem}</style>',
           f"<h1>Morning Coffee · {E(snapshot['date'])}</h1>"]
    if gaps:
        out.append(f"<p id=coverage>Coverage limits: {E('; '.join(gaps))}</p>")
    if alert:
        label, shift = alert
        out.append(f"<p class=alert id=oncall><b>{E(label)}</b> {E(hhmm(shift['start']))} → {E(hhmm(shift['end']))}</p>")
    out.append('<h2>Today</h2><ul id=today>' + (''.join(_event(e) for e in events) or '<li>None</li>') + '</ul>')
    out.append('<h2>To do</h2><ul id=todo>' + (''.join(
        f"<li>{'☑' if d else '☐'} {E(t)}</li>" for d, t in tasks) or '<li>None — add lines to tasks.md</li>') + '</ul>')
    out.append(f'<h2>Reviews waiting ({len(reviews)})</h2><ul id=reviews>' + (''.join(_pr(r, False) for r in reviews) or '<li>None</li>') + '</ul>')
    out.append(f'<h2>My open PRs ({len(mine)})</h2><ul id=mine>' + (''.join(_pr(r, True) for r in mine) or '<li>None</li>') + '</ul>')
    if previous is not None:
        out.append(f'<h2>New since last run ({len(fresh)})</h2><ul id=new>' + (''.join(
            f"<li>{E(s)}: {link(i.get('url', ''), i.get('title', ''))}</li>" for s, i in fresh) or '<li>Nothing new</li>') + '</ul>')
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
