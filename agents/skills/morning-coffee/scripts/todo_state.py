"""Local tasks shared by Morning Coffee and Tea Time, independent of providers."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from html import escape
import json
import os
from pathlib import Path
import re
import secrets


class TodoError(ValueError):
    pass


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
    parent_id = item.get('parent_id')
    if parent_id is not None and (not isinstance(parent_id, str) or not re.fullmatch(r'[a-f0-9]{32}', parent_id)):
        raise TodoError('Invalid local parent task identity.')
    item['parent_id'] = parent_id
    if type(item.get('important', False)) is not bool:
        raise TodoError('Invalid local task importance.')
    item['important'] = item.get('important', False)
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


def ordered_todos(items, matching_ids=None):
    """Put important tasks and their ancestor groups first, preserving task nesting."""
    visible = [dict(item, important=item.get('important', False)) for item in items if item['status'] != 'removed']
    by_id = {item['id']: item for item in visible}
    children, important_groups = {}, set()
    for item in visible:
        parent_id = item.get('parent_id')
        children.setdefault(parent_id if parent_id in by_id and parent_id != item['id'] else None, []).append(item)
        if item['important'] and (matching_ids is None or item['id'] in matching_ids):
            current, seen = item['id'], set()
            while current in by_id and current not in seen:
                seen.add(current)
                important_groups.add(current)
                current = by_id[current].get('parent_id')
    for siblings in children.values():
        siblings.sort(key=lambda item: (item['id'] not in important_groups, item.get('created_at', ''), item['id']))
    ordered, stack, visited = [], list(reversed(children.get(None, []))), set()
    while stack:
        item = stack.pop()
        if item['id'] in visited:
            continue
        visited.add(item['id'])
        ordered.append(item)
        stack.extend(reversed(children.get(item['id'], [])))
    return ordered


def _visible(items):
    return ordered_todos(items)


def load_todos(root, with_warnings=False):
    """Return all visible tasks, including completed and cancelled tasks."""
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
    required = {'add': {'action', 'title'},
                'set_importance': {'action', 'id', 'important'},
                'complete': {'action', 'id'}, 'cancel': {'action', 'id'},
                'reopen': {'action', 'id'}, 'remove': {'action', 'id'}}
    if not isinstance(action, str) or action not in required or (set(request) - ({'parent_id', 'important', 'due_date'} if action == 'add' else set())) != required[action]:
        raise TodoError('Send a supported task action and its required fields.')
    if (action == 'set_importance' or 'important' in request) and type(request['important']) is not bool:
        raise TodoError('Task importance must be true or false.')
    if action == 'add':
        title = _title(request['title'])
        parent_id = request.get('parent_id')
        if parent_id is not None and (not isinstance(parent_id, str) or not re.fullmatch(r'[a-f0-9]{32}', parent_id)):
            raise TodoError('Choose an existing parent task.')
    else:
        if not isinstance(request['id'], str) or not re.fullmatch(r'[a-f0-9]{32}', request['id']):
            raise TodoError('Choose an existing task.')
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
                    'parent_id': parent_id, 'important': request.get('important', False),
                    'created_at': stamp, 'updated_at': stamp}
            items.append(item)
        else:
            item = next((entry for entry in items if entry['id'] == request['id'] and entry['status'] != 'removed'), None)
            if item is None:
                raise TodoError('This task was removed or is no longer available. Reopen the report to refresh.')
            if action == 'set_importance':
                item['important'] = request['important']
            else:
                item['status'] = {'complete': 'completed', 'cancel': 'cancelled', 'reopen': 'pending',
                                  'remove': 'removed'}[action]
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


def todo_summary(snapshot):
    """Group local work by status, independently of a brief's date."""
    items = ordered_todos(snapshot.get('todos', []))
    return {status: [item for item in items if item['status'] == status]
            for status in ('pending', 'completed', 'cancelled')}


def _row(item, enabled, children=''):
    item_id = escape(str(item['id']), quote=True)
    pending = item['status'] == 'pending'
    group = item['status']
    label = {'pending': 'Open', 'completed': 'Completed', 'cancelled': 'Cancelled'}[group]
    disabled = '' if enabled else ' disabled'
    action, action_label = ('complete', 'Complete') if pending else ('reopen', 'Reopen')
    important = item.get('important', False)
    star_label = 'Remove high importance' if important else 'Mark high importance'
    return (f'<li class="todo-row" data-todo-id="{item_id}" data-todo-group="{group}" data-todo-important="{str(important).lower()}"><div class="todo-entry">'
            f'<div class="todo-copy"><b class="todo-title">{escape(item["title"])}</b>'
            f'<span class="todo-meta">{label}</span></div>'
            f'<div class="todo-actions"><button type="button" class="todo-star" data-todo-action="set_importance" aria-pressed="{str(important).lower()}" aria-label="{star_label}" title="{star_label}"{disabled}>{"⭐️" if important else "☆"}</button>'
            f'<button type="button" data-todo-action="{action}"{disabled}>{action_label}</button>'
            f'<button type="button" data-todo-action="subtask"{disabled}>Add subtask</button>'
            '<details><summary>Manage</summary><div class="todo-manage">'
            + (f'<button type="button" data-todo-action="cancel"{disabled}>Cancel task</button>' if item['status'] != 'cancelled' else '')
            + f'<button type="button" data-todo-action="remove"{disabled}>Remove task (keep subtasks)</button>'
            '</div></details></div></div>' + children + '</li>')


def render_todos(snapshot):
    """Render a local-only widget; live bridge capability enables its controls."""
    items = ordered_todos([item for item in snapshot.get('todos', []) if item.get('status') in ('pending', 'completed', 'cancelled')])
    config = snapshot.get('todo_interaction') or {}
    enabled = bool(config.get('endpoint') and config.get('token'))
    disabled = '' if enabled else ' disabled'
    summary = todo_summary({'todos': items})
    counts = f'{len(summary["pending"])} open · {len(summary["completed"])} completed · {len(summary["cancelled"])} cancelled'
    initial = dict(config, todos=items)
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
        rendered[item['id']] = _row(item, enabled, '<ul class="todo-children">' + nested + '</ul>' if nested else '')
    rows = ''.join(rendered[item['id']] for item in children.get(None, []))
    return ('<section id="todos" class="todo-section"><div class="section-head"><h2>To do</h2>'
            '<span class="muted">Saved locally · shared by Coffee and Tea</span></div>'
            f'<p class="todo-counts">{counts}</p>'
            '<form class="todo-add"><label for="todo-title">New task</label>'
            f'<p class="todo-add-context" hidden><span></span> <button type="button" data-todo-root{disabled}>Add as a root task</button></p>'
            '<div class="todo-add-fields">'
            f'<input id="todo-title" name="title" maxlength="500" placeholder="What needs doing?" required{disabled}>'
            f'<button type="submit"{disabled}>Add task</button></div></form>'
            '<label class="todo-filter-label" for="todo-filter">Show</label> '
            '<select id="todo-filter"><option value="pending">Open</option>'
            '<option value="completed">Completed</option>'
            '<option value="cancelled">Cancelled</option><option value="all" selected>All tasks</option></select>'
            f'<ul class="todo-list">{rows}</ul><p class="todo-empty"' + (' hidden' if items else '') + '>No tasks here.</p>'
            '<p class="todo-status" role="status" aria-live="polite">'
            + ('' if enabled else 'Open a live Coffee or Tea report to change tasks.') + '</p>'
            f'<script type="application/json" id="todo-config">{encoded}</script></section>')
