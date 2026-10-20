"""Local tasks shared by Morning Coffee and Tea Time, independent of providers."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import fcntl
from html import escape
import json
import os
from pathlib import Path
import re
import secrets
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class TodoError(ValueError):
    pass


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise TodoError('Choose a due date in YYYY-MM-DD format.')
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise TodoError('Choose a valid due date.') from error
    return value


def _title(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 500:
        raise TodoError('Enter a task title between 1 and 500 characters.')
    if any(ord(char) < 32 and char not in '\t\n\r' for char in value):
        raise TodoError('The task title contains unsupported characters.')
    return ' '.join(value.split())


def _valid_item(item):
    if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not re.fullmatch(r'[a-f0-9]{32}', item['id']):
        raise TodoError('Invalid local task identity.')
    if item.get('status') not in ('pending', 'completed', 'cancelled', 'removed'):
        raise TodoError('Invalid local task status.')
    _title(item.get('title'))
    _date(item.get('due_date'))
    parent_id = item.get('parent_id')
    if parent_id is not None and (not isinstance(parent_id, str) or not re.fullmatch(r'[a-f0-9]{32}', parent_id)):
        raise TodoError('Invalid local parent task identity.')
    item['parent_id'] = parent_id
    for key in ('created_at', 'updated_at'):
        try:
            stamp = datetime.fromisoformat(item[key].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('Missing timezone')
        except (KeyError, ValueError, TypeError, AttributeError) as error:
            raise TodoError('Invalid local task timestamp.') from error
    return item


def _validate_tree(items):
    active = {item['id']: item for item in items if item['status'] != 'removed'}
    checked = set()
    for item in active.values():
        path, current = set(), item
        while current['id'] not in checked:
            if current['id'] in path:
                raise TodoError('Local tasks contain a parent cycle.')
            path.add(current['id'])
            parent_id = current['parent_id']
            if parent_id is None:
                break
            if parent_id not in active:
                raise TodoError('A local subtask has no parent task.')
            current = active[parent_id]
        checked.update(path)


@contextmanager
def _locked_store(root, exclusive):
    folder = Path(root) / 'todos'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
    fd = os.open(folder / '.lock', os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield folder
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _read(folder):
    path = folder / 'state.json'
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        if data.get('version') != 1 or not isinstance(data.get('items'), list):
            raise TodoError('Invalid task store.')
        items = [_valid_item(item) for item in data['items']]
        if len({item['id'] for item in items}) != len(items):
            raise TodoError('Duplicate local task identity.')
        _validate_tree(items)
        return items
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise TodoError('The local to-do store could not be read. Existing tasks were preserved.') from error


def _visible(items):
    return sorted((dict(item) for item in items if item['status'] != 'removed'),
                  key=lambda item: (item['due_date'], item['created_at'], item['id']))


def load_todos(root, with_warnings=False):
    """Return all visible tasks, including completed/cancelled and future tasks."""
    warnings = []
    try:
        # A first read should not create a store in an otherwise read-only report run.
        if not (Path(root) / 'todos').exists():
            items = []
        else:
            with _locked_store(root, False) as folder:
                items = _read(folder)
    except (OSError, TodoError) as error:
        items = []
        warnings.append(str(error))
    todos = _visible(items)
    return {'todos': todos, 'warnings': warnings} if with_warnings else todos


def save_todo_action(root, request, now=None):
    """Apply one explicit action atomically; return the acknowledged item and list."""
    if not isinstance(request, dict):
        raise TodoError('Send a task action.')
    action = request.get('action')
    required = {'add': {'action', 'title', 'due_date'},
                'reschedule': {'action', 'id', 'due_date'},
                'complete': {'action', 'id'}, 'cancel': {'action', 'id'},
                'reopen': {'action', 'id'}, 'remove': {'action', 'id'}}
    if not isinstance(action, str) or action not in required or (set(request) - ({'parent_id'} if action == 'add' else set())) != required[action]:
        raise TodoError('Send a supported task action and its required fields.')
    if action == 'add':
        title, due_date = _title(request['title']), _date(request['due_date'])
        parent_id = request.get('parent_id')
        if parent_id is not None and (not isinstance(parent_id, str) or not re.fullmatch(r'[a-f0-9]{32}', parent_id)):
            raise TodoError('Choose an existing parent task.')
    else:
        if not isinstance(request['id'], str) or not re.fullmatch(r'[a-f0-9]{32}', request['id']):
            raise TodoError('Choose an existing task.')
        if action == 'reschedule':
            due_date = _date(request['due_date'])
    instant = now or datetime.now(timezone.utc)
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise TodoError('Task time must include a timezone.')
    stamp = instant.astimezone(timezone.utc).isoformat()
    with _locked_store(root, True) as folder:
        items = _read(folder)
        if action == 'add':
            if parent_id is not None and not any(entry['id'] == parent_id and entry['status'] != 'removed' for entry in items):
                raise TodoError('The parent task was removed. Choose another task or add a root task.')
            item = {'id': secrets.token_hex(16), 'title': title, 'status': 'pending',
                    'due_date': due_date, 'parent_id': parent_id, 'created_at': stamp, 'updated_at': stamp}
            items.append(item)
        else:
            item = next((entry for entry in items if entry['id'] == request['id'] and entry['status'] != 'removed'), None)
            if item is None:
                raise TodoError('This task was removed or is no longer available. Reopen the report to refresh.')
            item['status'] = {'complete': 'completed', 'cancel': 'cancelled', 'reopen': 'pending',
                              'reschedule': 'pending', 'remove': 'removed'}[action]
            if action == 'reschedule':
                item['due_date'] = due_date
            if action == 'remove':
                for child in items:
                    if child['parent_id'] == item['id'] and child['status'] != 'removed':
                        child['parent_id'] = item['parent_id']
                        child['updated_at'] = stamp
            item['updated_at'] = stamp
        temporary = folder / ('.state-' + secrets.token_hex(8) + '.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'w') as handle:
                json.dump({'version': 1, 'items': items}, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, folder / 'state.json')
        finally:
            temporary.unlink(missing_ok=True)
        return {'ok': True, 'item': dict(item), 'todos': _visible(items)}


def report_date(snapshot):
    report = snapshot.get('report') or {}
    try:
        return _date(report.get('date'))
    except TodoError:
        try:
            zone = ZoneInfo(report.get('timezone') or 'America/Toronto')
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            zone = timezone.utc
        return datetime.now(zone).date().isoformat()


def todo_summary(snapshot):
    """Separate local pending work from provider facts for either brief."""
    today = report_date(snapshot)
    pending = [item for item in snapshot.get('todos', []) if item.get('status') == 'pending']
    return {'date': today, 'overdue': [item for item in pending if item['due_date'] < today],
            'due_today': [item for item in pending if item['due_date'] == today],
            'upcoming': [item for item in pending if item['due_date'] > today]}


def _row(item, today, enabled, children=''):
    item_id = escape(str(item['id']), quote=True)
    pending = item['status'] == 'pending'
    group = ('overdue' if item['due_date'] < today else 'today' if item['due_date'] == today else 'upcoming') if pending else item['status']
    label = {'overdue': 'Overdue', 'today': 'Due today', 'upcoming': 'Upcoming',
             'completed': 'Completed', 'cancelled': 'Cancelled'}[group]
    disabled = '' if enabled else ' disabled'
    action, action_label = ('complete', 'Complete') if pending else ('reopen', 'Reopen')
    return (f'<li class="todo-row" data-todo-id="{item_id}" data-todo-group="{group}"><div class="todo-entry">'
            f'<div class="todo-copy"><b class="todo-title">{escape(item["title"])}</b>'
            f'<span class="todo-meta">{label} · <time datetime="{item["due_date"]}">{item["due_date"]}</time></span></div>'
            f'<div class="todo-actions"><button type="button" data-todo-action="{action}"{disabled}>{action_label}</button>'
            f'<button type="button" data-todo-action="subtask"{disabled}>Add subtask</button>'
            '<details><summary>Manage</summary><div class="todo-manage">'
            f'<form data-todo-reschedule><label for="todo-date-{item_id}">New due date</label>'
            f'<input id="todo-date-{item_id}" type="date" name="due_date" value="{item["due_date"]}" required{disabled}>'
            f'<button type="submit"{disabled}>Reschedule</button></form>'
            + (f'<button type="button" data-todo-action="cancel"{disabled}>Cancel task</button>' if item['status'] != 'cancelled' else '')
            + f'<button type="button" data-todo-action="remove"{disabled}>Remove task (keep subtasks)</button>'
            '</div></details></div></div>' + children + '</li>')


def render_todos(snapshot):
    """Render a local-only widget; live bridge capability enables its controls."""
    today = report_date(snapshot)
    items = [item for item in snapshot.get('todos', []) if item.get('status') in ('pending', 'completed', 'cancelled')]
    config = snapshot.get('todo_interaction') or {}
    enabled = bool(config.get('endpoint') and config.get('token'))
    disabled = '' if enabled else ' disabled'
    summary = todo_summary({'report': {'date': today}, 'todos': items})
    counts = f'{len(summary["overdue"])} overdue · {len(summary["due_today"])} due today · {len(summary["upcoming"])} upcoming'
    initial = dict(config, today=today, todos=items)
    encoded = json.dumps(initial, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    # Build nested markup bottom-up so task depth is not tied to Python's recursion limit.
    by_id = {item['id']: item for item in items}
    children, depths = {}, {}
    for item in items:
        parent_id = item.get('parent_id')
        children.setdefault(parent_id if parent_id in by_id and parent_id != item['id'] else None, []).append(item)
        seen, ancestor = {item['id']}, parent_id
        while ancestor in by_id and ancestor not in seen:
            seen.add(ancestor)
            ancestor = by_id[ancestor].get('parent_id')
        depths[item['id']] = len(seen)
    rendered = {}
    for item in sorted(items, key=lambda entry: depths[entry['id']], reverse=True):
        nested = ''.join(rendered.get(child['id'], '') for child in children.get(item['id'], []))
        rendered[item['id']] = _row(item, today, enabled, '<ul class="todo-children">' + nested + '</ul>' if nested else '')
    rows = ''.join(rendered[item['id']] for item in children.get(None, []))
    return ('<section id="todos" class="todo-section"><div class="section-head"><h2>To do</h2>'
            '<span class="muted">Saved locally · shared by Coffee and Tea</span></div>'
            f'<p class="todo-counts">{counts}</p>'
            '<form class="todo-add"><label for="todo-title">New task</label>'
            f'<p class="todo-add-context" hidden><span></span> <button type="button" data-todo-root{disabled}>Add as a root task</button></p>'
            '<div class="todo-add-fields">'
            f'<input id="todo-title" name="title" maxlength="500" placeholder="What needs doing?" required{disabled}>'
            '<label class="todo-date-label" for="todo-due-date">Due date</label>'
            f'<input id="todo-due-date" type="date" name="due_date" value="{today}" required{disabled}>'
            f'<button type="submit"{disabled}>Add task</button></div></form>'
            '<label class="todo-filter-label" for="todo-filter">Show</label> '
            '<select id="todo-filter"><option value="due">Due today + overdue</option>'
            '<option value="upcoming">Upcoming</option><option value="completed">Completed</option>'
            '<option value="cancelled">Cancelled</option><option value="all" selected>All tasks</option></select>'
            f'<ul class="todo-list">{rows}</ul><p class="todo-empty"' + (' hidden' if items else '') + '>No tasks here.</p>'
            '<p class="todo-status" role="status" aria-live="polite">'
            + ('' if enabled else 'Open a live Coffee or Tea report to change tasks.') + '</p>'
            f'<script type="application/json" id="todo-config">{encoded}</script></section>')
