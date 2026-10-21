"""Persistent local Morning Coffee tasks, independent of provider state."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from html import escape
import json
import os
from pathlib import Path
import re
import secrets
import unicodedata


class TodoError(ValueError):
    pass


class StaleTodoError(TodoError):
    pass


def _title(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 500:
        raise TodoError('Enter a task title between 1 and 500 characters.')
    if any(ord(char) < 32 and char not in '\t\n\r' for char in value):
        raise TodoError('The task title contains unsupported characters.')
    return ' '.join(value.split())


def _project_tags(value):
    if not isinstance(value, list):
        raise TodoError('Project tags must be a list of names.')
    tags, seen = [], set()
    for tag in value:
        if (not isinstance(tag, str) or ',' in tag or
                any(unicodedata.category(char) == 'Cc' for char in tag)):
            raise TodoError('Each project tag must be plain text without commas or control characters.')
        normalized = ' '.join(tag.split())
        if not normalized:
            raise TodoError('Project tags cannot be blank.')
        if len(normalized) > 60:
            raise TodoError('Project tags must be 60 characters or fewer.')
        folded = normalized.lower()
        if folded not in seen:
            seen.add(folded)
            tags.append(normalized)
    if len(tags) > 10:
        raise TodoError('A task can have at most 10 project tags.')
    return tags


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
    item['project_tags'] = _project_tags(item.get('project_tags', []))
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
        return {'items': [], 'archive': []}
    try:
        data = json.loads(path.read_text())
        if data.get('version') != 1 or not isinstance(data.get('items'), list):
            raise TodoError('Invalid task store.')
        items = [_valid_item(item) for item in data['items']]
        if len({item['id'] for item in items}) != len(items):
            raise TodoError('Duplicate local task identity.')
        _validate_tree(items)
        archive = data.get('archive', [])
        if not isinstance(archive, list):
            raise TodoError('Invalid task archive.')
        identities = {item['id'] for item in items}
        batches = set()
        for batch in archive:
            if (not isinstance(batch, dict) or not isinstance(batch.get('id'), str) or
                    not re.fullmatch(r'[a-f0-9]{32}', batch['id']) or batch['id'] in batches or
                    not isinstance(batch.get('items'), list) or not batch['items'] or
                    not isinstance(batch.get('promotions'), list)):
                raise TodoError('Invalid task archive batch.')
            batches.add(batch['id'])
            cleared = datetime.fromisoformat(batch['cleared_at'])
            if cleared.tzinfo is None:
                raise TodoError('Invalid archive timestamp.')
            for archived in batch['items']:
                _valid_item(archived)
                if archived['status'] == 'removed' or archived['id'] in identities:
                    raise TodoError('Duplicate or invalid archived task.')
                identities.add(archived['id'])
            for promotion in batch['promotions']:
                if (not isinstance(promotion, dict) or
                        set(promotion) != {'id', 'from_parent_id', 'to_parent_id', 'updated_at'} or
                        any(value is not None and (not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value))
                            for value in (promotion['id'], promotion['from_parent_id'], promotion['to_parent_id'])) or
                        promotion['id'] is None or promotion['from_parent_id'] is None or
                        not isinstance(promotion['updated_at'], str)):
                    raise TodoError('Invalid archived task relationship.')
        return {'items': items, 'archive': archive}
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
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
            state = {'items': [], 'archive': []}
        else:
            with _locked_store(root, False) as folder:
                state = _read(folder)
    except (OSError, TodoError) as error:
        state = {'items': [], 'archive': []}
        warnings.append(str(error))
    todos = _visible(state['items'])
    return {'todos': todos, 'todo_archive': _archive_view(state['archive']), 'warnings': warnings} if with_warnings else todos


def _archive_view(archive):
    return [dict(item, batch_id=batch['id'], cleared_at=batch['cleared_at'])
            for batch in reversed(archive) for item in batch['items']]


def save_todo_action(root, request, now=None, task_id=None):
    """Apply one explicit action atomically; return the acknowledged item and list."""
    if not isinstance(request, dict):
        raise TodoError('Send a task action.')
    action = request.get('action')
    required = {'add': {'action', 'title'},
                'edit': {'action', 'id', 'title', 'base_title'},
                'set_importance': {'action', 'id', 'important'},
                'set_project_tags': {'action', 'id', 'project_tags'},
                'complete': {'action', 'id'}, 'cancel': {'action', 'id'},
                'reopen': {'action', 'id'}, 'remove': {'action', 'id'},
                'clear': {'action', 'ids', 'status'},
                'restore': {'action', 'id'}, 'undo': {'action', 'id'}}
    if not isinstance(action, str) or action not in required or (set(request) - ({'parent_id', 'important', 'due_date', 'project_tags'} if action == 'add' else set())) != required[action]:
        raise TodoError('Send a supported task action and its required fields.')
    if (action == 'set_importance' or 'important' in request) and type(request['important']) is not bool:
        raise TodoError('Task importance must be true or false.')
    if action == 'edit':
        title = _title(request['title'])
        _title(request['base_title'])
    if action == 'add':
        title = _title(request['title'])
        project_tags = _project_tags(request['project_tags']) if 'project_tags' in request else None
        parent_id = request.get('parent_id')
        if parent_id is not None and (not isinstance(parent_id, str) or not re.fullmatch(r'[a-f0-9]{32}', parent_id)):
            raise TodoError('Choose an existing parent task.')
    elif action == 'set_project_tags':
        project_tags = _project_tags(request['project_tags'])
    elif action == 'clear':
        ids = request['ids']
        if (request['status'] not in ('all', 'pending', 'completed', 'cancelled') or
                not isinstance(ids, list) or not ids or
                not all(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{32}', value) for value in ids) or
                len(set(ids)) != len(ids)):
            raise TodoError('Choose the tasks in a supported tab to clear.')
    else:
        if not isinstance(request['id'], str) or not re.fullmatch(r'[a-f0-9]{32}', request['id']):
            raise TodoError('Choose an existing task.')
    if task_id is not None and (action != 'add' or not isinstance(task_id, str) or not re.fullmatch(r'[a-f0-9]{32}', task_id)):
        raise TodoError('An internal task identity must be 32 hexadecimal characters for an add action.')
    instant = now or datetime.now(timezone.utc)
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise TodoError('Task time must include a timezone.')
    stamp = instant.astimezone(timezone.utc).isoformat()
    with _locked_store(root, True) as folder:
        state = _read(folder)
        items, archive = state['items'], state['archive']
        batch = None
        if action == 'add':
            if task_id is not None:
                # Internal callers can recover a committed task after their own save fails.
                # Archived/completed choices remain authoritative; retries never recreate them.
                existing = next((entry for entry in items + [task for batch in archive for task in batch['items']] if entry['id'] == task_id), None)
                if existing is not None:
                    return {'ok': True, 'item': dict(existing), 'todos': _visible(items), 'archive': _archive_view(archive)}
            if parent_id is not None and not any(entry['id'] == parent_id and entry['status'] != 'removed' for entry in items):
                raise TodoError('The parent task was removed. Choose another task or add a root task.')
            item = {'id': task_id or secrets.token_hex(16), 'title': title, 'status': 'pending',
                    'parent_id': parent_id, 'important': request.get('important', False),
                    'project_tags': (project_tags if project_tags is not None else
                                     next((entry['project_tags'] for entry in items if entry['id'] == parent_id), [])),
                    'created_at': stamp, 'updated_at': stamp}
            items.append(item)
        elif action in ('clear', 'remove'):
            by_id = {entry['id']: entry for entry in items if entry['status'] != 'removed'}
            ids = request['ids'] if action == 'clear' else [request['id']]
            removed_ids = set(ids)
            if any(value not in by_id or (action == 'clear' and request['status'] != 'all' and
                   by_id[value]['status'] != request['status']) for value in ids):
                raise TodoError('The selected tasks changed. Reopen the report before clearing them.')
            batch = {'id': secrets.token_hex(16), 'cleared_at': stamp,
                     'items': [dict(by_id[value]) for value in ids], 'promotions': []}
            for entry in items:
                if entry['id'] in removed_ids or entry['status'] == 'removed':
                    continue
                parent_id = entry['parent_id']
                while parent_id in removed_ids:
                    parent_id = by_id[parent_id]['parent_id']
                if entry['parent_id'] != parent_id:
                    batch['promotions'].append({'id': entry['id'], 'from_parent_id': entry['parent_id'],
                                                'to_parent_id': parent_id, 'updated_at': stamp})
                    entry['parent_id'] = parent_id
                    entry['updated_at'] = stamp
            if action == 'remove':
                item = dict(by_id[request['id']], status='removed', updated_at=stamp)
            items = [entry for entry in items if entry['id'] not in removed_ids]
            archive.append(batch)
        elif action in ('restore', 'undo'):
            batch = next((entry for entry in archive if
                          (entry['id'] == request['id'] if action == 'undo' else
                           any(task['id'] == request['id'] for task in entry['items']))), None)
            if batch is None:
                raise TodoError('These tasks were already restored or are no longer archived. Reopen the report to refresh.')
            restored = [dict(entry) for entry in batch['items']
                        if action == 'undo' or entry['id'] == request['id']]
            restored_ids = {entry['id'] for entry in restored}
            active_ids = {entry['id'] for entry in items} | restored_ids
            for entry in restored:
                # A separately restored subtask becomes a root if its parent is still archived.
                if entry['parent_id'] not in active_ids:
                    original_parent = entry['parent_id']
                    parent_batch = next((group for group in archive if any(task['id'] == original_parent for task in group['items'])), None)
                    if parent_batch:
                        parent_batch['promotions'].append({'id': entry['id'], 'from_parent_id': original_parent,
                                                           'to_parent_id': None, 'updated_at': stamp})
                    entry['parent_id'] = None
                entry['updated_at'] = stamp
            items.extend(restored)
            for promotion in batch['promotions']:
                child = next((entry for entry in items if entry['id'] == promotion['id']), None)
                if (child and promotion['from_parent_id'] in restored_ids and
                        child['parent_id'] == promotion['to_parent_id'] and
                        child['updated_at'] == promotion['updated_at']):
                    child['parent_id'] = promotion['from_parent_id']
                    child['updated_at'] = stamp
            batch['items'] = [entry for entry in batch['items'] if entry['id'] not in restored_ids]
            archive = [entry for entry in archive if entry['items']]
        else:
            item = next((entry for entry in items if entry['id'] == request['id'] and entry['status'] != 'removed'), None)
            if item is None:
                raise TodoError('This task was cleared or is no longer available. Reopen the report to refresh.')
            if action == 'edit':
                if item['title'] not in (request['base_title'], title):
                    raise StaleTodoError('This task title changed in another session. Reload the workspace before editing its latest title.')
                item['title'] = title
            elif action == 'set_importance':
                item['important'] = request['important']
            elif action == 'set_project_tags':
                item['project_tags'] = project_tags
            else:
                item['status'] = {'complete': 'completed', 'cancel': 'cancelled', 'reopen': 'pending'}[action]
            item['updated_at'] = stamp
        # Active tasks and their archive commit together; discard legacy tombstones.
        items = [entry for entry in items if entry['status'] != 'removed']
        _validate_tree(items)
        temporary = folder / ('.state-' + secrets.token_hex(8) + '.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'w') as handle:
                json.dump({'version': 1, 'items': items, 'archive': archive}, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, folder / 'state.json')
        finally:
            temporary.unlink(missing_ok=True)
        result = {'ok': True, 'todos': _visible(items), 'archive': _archive_view(archive)}
        if action in ('restore', 'undo'):
            return dict(result, restored_ids=[entry['id'] for entry in restored], batch_id=batch['id'])
        if action == 'clear':
            return dict(result, removed_ids=ids, status=request['status'], batch_id=batch['id'])
        if action == 'remove':
            return dict(result, item=dict(item), batch_id=batch['id'])
        return dict(result, item=dict(item))


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
            + (f'<span class="todo-cancel-slot"><button type="button" data-todo-action="cancel"{disabled}>Cancel</button></span>' if item['status'] != 'cancelled' else '<span class="todo-cancel-slot" aria-hidden="true"></span>')
            + f'<details class="todo-more"><summary title="More task actions" aria-label="More actions for {escape(item["title"], quote=True)}">⋯</summary><div class="todo-more-panel">'
            + f'<button type="button" data-todo-action="edit" aria-expanded="false" aria-label="Edit task: {escape(item["title"], quote=True)}"{disabled}>Edit task</button>'
            + f'<button type="button" data-todo-action="subtask"{disabled}>Add subtask</button>'
            + f'<button type="button" data-todo-action="projects" aria-expanded="false" aria-label="Edit project tags for {escape(item["title"], quote=True)}"{disabled}>Project tags</button>'
            f'<button type="button" data-todo-action="remove" title="Move this task to Archived; keep its subtasks" aria-label="Clear task: {escape(item["title"], quote=True)}"{disabled}>Clear task</button>'
            + '</div></details></div></div>'
            + ('<span class="todo-project-tags">' + ''.join(
                f'<span class="todo-project-tag">{escape(tag)}</span>' for tag in item.get('project_tags', [])) + '</span>'
               if item.get('project_tags') else '')
            + children + '</li>')


def _project_names(items, archive):
    names, seen = [], set()
    for item in list(items) + list(archive):
        for name in item.get('project_tags', []):
            key = name.lower()
            if key not in seen:
                seen.add(key)
                names.append(name)
    return sorted(names, key=str.lower)


def render_todos(snapshot):
    """Render a local-only widget; live bridge capability enables its controls."""
    items = ordered_todos([item for item in snapshot.get('todos', []) if item.get('status') in ('pending', 'completed', 'cancelled')])
    config = snapshot.get('todo_interaction') or {}
    enabled = bool(config.get('endpoint') and config.get('token'))
    disabled = '' if enabled else ' disabled'
    summary = todo_summary({'todos': items})
    counts = f'{len(summary["pending"])} open · {len(summary["completed"])} completed · {len(summary["cancelled"])} cancelled'
    archive = snapshot.get('todo_archive', [])
    project_names = _project_names(items, archive)
    initial = dict(config, todos=items, archive=archive,
                   timezone=snapshot.get('report', {}).get('timezone', 'UTC'))
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
            '<span class="muted">Saved locally · carried across days</span></div>'
            f'<p class="todo-counts">{counts}</p>'
            '<form class="todo-add"><div class="todo-add-fields">'
            '<label class="todo-add-title" for="todo-title">New task'
            f'<input id="todo-title" name="title" maxlength="500" placeholder="What needs doing?" required{disabled}>'
            '</label>'
            f'<button type="submit"{disabled}>Add task</button></div>'
            '<div class="todo-add-projects"><label for="todo-project-tags">Projects <span>(optional)</span></label>'
            f'<input id="todo-project-tags" name="project_tags" list="todo-project-options" placeholder="e.g. Transport, PrivateLink"{disabled}>'
            '</div>'
            '<datalist id="todo-project-options">'
            + ''.join(f'<option value="{escape(name, quote=True)}"></option>' for name in project_names)
            + '</datalist></form>'
            '<p id="todo-project-help" class="todo-project-help">Choose existing tags or create a new one. Tags save with the task.</p>'
            '<div class="todo-toolbar"><div class="todo-tabs" role="tablist" aria-label="Task status">'
            + ''.join(f'<button type="button" role="tab" id="todo-tab-{status}" data-todo-filter="{status}" '
                      f'aria-controls="todo-panel" aria-selected="{str(status == "pending").lower()}" '
                      f'tabindex="{0 if status == "pending" else -1}">{label}</button>'
                      for status, label in [('pending', 'Open'), ('completed', 'Completed'),
                                            ('cancelled', 'Cancelled'), ('all', 'All tasks'), ('archive', 'Archived')])
            + '</div><label class="todo-project-filter" for="todo-project-filter">Project'
            '<select id="todo-project-filter" data-todo-project-filter>'
            '<option value="">All projects</option><option value="__untagged__">Untagged</option>'
            + ''.join(f'<option value="tag:{escape(name, quote=True)}">{escape(name)}</option>' for name in project_names)
            + f'</select></label><button type="button" data-todo-clear-view{disabled}>Clear tab</button></div>'
            f'<p class="todo-undo" hidden><span></span> <button type="button" data-todo-undo{disabled}>Undo last clear</button></p>'
            '<div id="todo-panel" role="tabpanel" aria-labelledby="todo-tab-pending">'
            f'<ul class="todo-list">{rows}</ul><p class="todo-empty"' + (' hidden' if items else '') + '>No tasks here.</p></div>'
            '<p class="todo-status" role="status" aria-live="polite">'
            + ('' if enabled else 'Open the live Morning Coffee workspace to change tasks.') + '</p>'
            f'<script type="application/json" id="todo-config">{encoded}</script></section>')
