"""Private, root-wide state for the all-day Morning Coffee workspace.

Published snapshots remain immutable. Only this manifest advances; callers choose
and resolve the report root before calling this module. No provider credentials
or bridge configuration are returned in the public workspace view.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone as utc_timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from todo_state import save_todo_action
from review_state import (apply_verified_re_requests, load_review_state, canonical_url,
                          ReviewError, verified_re_request)


class WorkspaceError(ValueError):
    pass


class StaleWorkspaceError(WorkspaceError):
    pass


# Six independent provider collections can exceed fifteen minutes. Keep a
# bounded recovery window without invalidating a healthy scheduled collection.
TIMEOUT_SECONDS = 3600
TERMINAL = {'completed', 'resolved', 'closed', 'merged', 'cancelled'}


def _instant(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed
    except (ValueError, TypeError, AttributeError) as exc:
        raise WorkspaceError('Workspace timestamps must include a timezone.') from exc


def _now(now):
    value = now or datetime.now(utc_timezone.utc)
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise WorkspaceError('Workspace time must include a timezone.')
    return value


def _day(date, timezone):
    try:
        if datetime.strptime(date, '%Y-%m-%d').date().isoformat() != date:
            raise ValueError()
        ZoneInfo(timezone)
    except (ValueError, TypeError, KeyError) as exc:
        raise WorkspaceError('Choose a valid local date and IANA timezone.') from exc


def _safe_folder(root, create=False):
    root = Path(root).expanduser().resolve()
    folder = root / 'workspace'
    if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
        raise WorkspaceError('The workspace directory is invalid. Preserve it and repair its path before retrying.')
    if create:
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        folder.chmod(0o700)
    return folder


@contextmanager
def _locked(root):
    folder = _safe_folder(root, True)
    try:
        fd = os.open(folder / '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
    except OSError as exc:
        raise WorkspaceError('The workspace lock could not be opened. Preserve existing files and repair permissions.') from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield folder
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _json(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError) as exc:
        raise WorkspaceError('The private workspace file could not be read. Existing files were preserved; repair it before retrying.') from exc


def _write(folder, state, filename='state.json'):
    temporary = folder / ('.state-' + secrets.token_hex(8) + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, folder / filename)
        directory = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def published_snapshot(root, snapshot_path):
    """Validate an immutable published pair within exactly the configured root."""
    supplied_root = Path(root).expanduser().absolute()
    root = supplied_root.resolve()
    path = Path(snapshot_path)
    if path.is_absolute():
        try:
            path = root / path.relative_to(supplied_root)
        except ValueError:
            pass
    else:
        path = root / path
    try:
        relative = path.relative_to(root)
        if len(relative.parts) != 4 or relative.name != 'snapshot.json' or any(part.startswith('.') for part in relative.parts):
            raise ValueError()
        cursor = root
        for part in relative.parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError()
        if path.resolve() != path or not path.is_file() or not path.with_name('report.html').is_file() or path.with_name('report.html').is_symlink():
            raise ValueError()
        snapshot = _json(path)
        report, history = snapshot['report'], snapshot['history']
        date, zone = report['date'], report['timezone']
        _day(date, zone)
        if relative.parts[:2] != (zone.replace('/', '__'), date):
            raise ValueError()
        stamp = _instant(snapshot['collected_at'])
        if history['kind'] not in ('morning-coffee', 'tea-time', 'refresh') or _instant(history['created_at']) != stamp or stamp.astimezone(ZoneInfo(zone)).date().isoformat() != date:
            raise ValueError()
        if not isinstance(snapshot.get('priorities', []), list) or not all(isinstance(row, dict) for row in snapshot.get('priorities', [])):
            raise ValueError()
        if not isinstance(snapshot.get('work_suggestions', []), list) or not all(isinstance(row, dict) for row in snapshot.get('work_suggestions', [])):
            raise ValueError()
        _validate_answers(snapshot.get('user_answers', []))
        return snapshot, relative.as_posix()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise WorkspaceError('Choose a published snapshot and HTML pair inside the configured report root, with matching local date and timezone.') from exc


def _validate_answers(answers):
    if not isinstance(answers, list):
        raise WorkspaceError('User confirmations must be a list; existing files were preserved.')
    for row in answers:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'] or not isinstance(row.get('section'), str):
            raise WorkspaceError('User confirmations require a source section and ID; existing files were preserved.')
        _instant(row.get('answered_at'))


def _read(root, folder, with_snapshot=False):
    path = folder / 'state.json'
    if not path.exists() and not path.is_symlink():
        return (None, None) if with_snapshot else None
    state = _json(path)
    try:
        if not isinstance(state, dict) or state['schema_version'] != 1 or type(state['version']) is not int or state['version'] < 1:
            raise ValueError()
        _day(state['date'], state['timezone'])
        snapshot, relative = published_snapshot(root, state['active_snapshot'])
        if snapshot['report']['date'] != state['date'] or snapshot['report']['timezone'] != state['timezone']:
            raise ValueError()
        for key in ('selected_priorities', 'suggestions'):
            if not isinstance(state[key], list) or not all(isinstance(row, dict) and isinstance(row['id'], str) and isinstance(row['item'], dict) for row in state[key]):
                raise ValueError()
        if any(type(row['completed']) is not bool for row in state['selected_priorities']):
            raise ValueError()
        if any(not isinstance(row['fingerprint'], str) for row in state['suggestions']):
            raise ValueError()
        if not isinstance(state['accepted'], dict) or not isinstance(state['dismissed'], dict):
            raise ValueError()
        if any(not isinstance(key, str) or not isinstance(value, list) or not all(isinstance(entry, str) for entry in value) for key, value in state['dismissed'].items()):
            raise ValueError()
        if any(not isinstance(value, dict) or not isinstance(value['fingerprint'], str) or not re.fullmatch(r'[a-f0-9]{32}', value['task_id']) for value in state['accepted'].values()):
            raise ValueError()
        _validate_answers(state.get('user_answers', []))
        for record in state['accepted'].values():
            if not isinstance(record.get('previous_versions', []), list) or not all(isinstance(row, dict) and isinstance(row['fingerprint'], str) and isinstance(row['task_id'], str) for row in record.get('previous_versions', [])):
                raise ValueError()
        request = state['refresh']
        if request is not None:
            UUID(request['id'])
            _day(request['date'], request['timezone'])
            _instant(request['requested_at'])
            _instant(request['updated_at'])
            if request['action'] not in ('refresh', 'start_today') or request['status'] not in ('pending', 'running', 'failed', 'completed'):
                raise ValueError()
        return (state, (snapshot, relative)) if with_snapshot else state
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise WorkspaceError('The workspace manifest is invalid. Existing files were preserved; repair state.json before retrying.') from exc


def read_bridge_config(root):
    """Read private assistant dispatch configuration; never embed this in reports."""
    folder = _safe_folder(root)
    path = folder / 'config.json'
    if not path.exists() and not path.is_symlink():
        return {}
    try:
        if path.stat().st_mode & 0o077 or folder.stat().st_mode & 0o077:
            raise WorkspaceError('Set workspace directory permissions to 700 and config.json to 600 before refreshing.')
        return _validate_bridge_config(_json(path))
    except (OSError, ValueError, TypeError) as exc:
        if isinstance(exc, WorkspaceError):
            raise
        raise WorkspaceError('The private refresh configuration is invalid. Preserve config.json and repair it before retrying.') from exc


def _validate_bridge_config(config):
    if not isinstance(config, dict) or set(config) - {'webhook_url', 'timeout_seconds', 'thread_url', 'scheduled_task_id', 'local_t3'}:
        raise ValueError()
    local = config.get('local_t3')
    if local is not None:
        required = {'cli_path', 'node_path', 'runtime_path', 'thread_id'}
        if not isinstance(local, dict) or not required.issubset(local) or set(local) - required - {'base_dir'}:
            raise ValueError()
        if not isinstance(local['thread_id'], str):
            raise ValueError()
        UUID(local['thread_id'])
        for key in set(local) - {'thread_id'}:
            value = local[key]
            if not isinstance(value, str) or not Path(value).is_absolute() or any(ord(char) < 32 for char in value):
                raise ValueError()
    url = config.get('webhook_url')
    if url is not None:
        parsed = urlsplit(url)
        if not isinstance(url, str) or parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.fragment or parsed.username or parsed.password:
            raise ValueError()
    thread_url = config.get('thread_url')
    if thread_url is not None and (not isinstance(thread_url, str) or not thread_url.startswith('t3-thread://') or not urlsplit(thread_url).netloc or any(ord(char) < 32 for char in thread_url)):
        raise ValueError()
    task_id = config.get('scheduled_task_id')
    if task_id is not None and (not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 200 or any(ord(char) < 32 for char in task_id)):
        raise ValueError()
    timeout = config.get('timeout_seconds', TIMEOUT_SECONDS)
    if type(timeout) is not int or not 30 <= timeout <= 3600:
        raise ValueError()
    return dict(config)


def configure_bridge(root, config):
    """Provision private bridge JSON without returning or logging its contents."""
    try:
        config = _validate_bridge_config(config)
    except (ValueError, TypeError, AttributeError) as exc:
        raise WorkspaceError('The bridge configuration is invalid; existing configuration was preserved.') from exc
    with _locked(root) as folder:
        path = folder / 'config.json'
        if path.exists() or path.is_symlink():
            read_bridge_config(root)  # Never overwrite a corrupt existing file.
        _write(folder, config, filename='config.json')
    return {'ok': True, 'bridge_configured': bridge_configured(config)}


def bridge_configured(config):
    return bool(config.get('local_t3') or config.get('webhook_url'))


def _expire(root, folder, state, now):
    request = state and state.get('refresh')
    if request and request['status'] in ('pending', 'running'):
        try:
            timeout = read_bridge_config(root).get('timeout_seconds', TIMEOUT_SECONDS)
        except WorkspaceError:
            # A broken assistant bridge cannot prevent ordinary local work.
            timeout = TIMEOUT_SECONDS
        if (now - _instant(request['requested_at'])).total_seconds() >= timeout:
            request.update(status='failed', updated_at=now.isoformat(), error='Refresh timed out. Check the assistant connection and try Refresh all again.')
            state['version'] += 1
            _write(folder, state)
    return state


def load_workspace(root, now=None):
    """Load the current workspace; a read never rolls over the local day."""
    if not _safe_folder(root).exists():
        return None
    with _locked(root) as folder:
        return deepcopy(_expire(root, folder, _read(root, folder), _now(now)))


def load_workspace_with_snapshot(root, now=None):
    """Load state and its fully validated active snapshot in one read."""
    if not _safe_folder(root).exists():
        return None, None
    with _locked(root) as folder:
        state, snapshot = _read(root, folder, with_snapshot=True)
        state = _expire(root, folder, state, _now(now))
        return deepcopy(state), snapshot


def _identity(item):
    value = item.get('source_id') or item.get('id') or item.get('url')
    return str(value) if value else None


def material_fingerprint(item):
    """Ignore collection timestamps and generated recommendation wording."""
    if item.get('material_key') is not None:
        material = {'source_id': _identity(item), 'material_key': item['material_key']}
    else:
        material = {key: item[key] for key in ('source_id', 'id', 'url', 'source_url', 'status', 'state', 'outcome', 'reviewDecision', 'mergeStateStatus') if key in item}
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def _done(item):
    # Missing work and generated "done" checkpoint prose are not completion.
    return item.get('verified') is not False and str(item.get('status') or item.get('state') or item.get('outcome') or '').lower() in TERMINAL


def _accepted_fingerprints(state, key):
    record = state['accepted'].get(key)
    return {row['fingerprint'] for row in [record, *record.get('previous_versions', [])]} if record else set()


def _locally_done_review(item, snapshot, local_reviews, now):
    urls = set()
    for field in ('source_url', 'url', 'source_id', 'id'):
        try:
            urls.add(canonical_url(item.get(field)))
        except ReviewError:
            continue
    kind = item.get('source_kind')
    for mark in local_reviews.values():
        if not mark.get('done') or mark.get('url') not in urls or (kind in ('pr', 'rfc') and kind != mark['kind']):
            continue
        section = 'reviews' if mark['kind'] == 'pr' else 'rfcs'
        rows = (snapshot.get(section) or {}).get('items', [])
        for row in rows:
            event = verified_re_request(mark['kind'], row, snapshot)
            if (event and event['url'] == mark['url'] and
                    _instant(mark['updated_at']) < event['requested_at'] <= now):
                break
        else:
            return True
    return False


def _confirmed_finished(item, snapshot, answers):
    """Local confirmations and explicit source resolutions also retire proposals."""
    identities = {str(item[field]) for field in ('source_id', 'id', 'url', 'source_url') if item.get(field)}
    for value in list(identities):
        try:
            identities.add(canonical_url(value))
        except ReviewError:
            pass
    # A generated proposal cannot override an explicit completed source priority.
    for priority in snapshot.get('priorities', []):
        if _identity(priority) in identities and _done(priority):
            return True
    for answer in answers.values():
        if str(answer['id']) in identities and _done(answer):
            return True
    for resolution in snapshot.get('resolutions', []):
        if resolution.get('verified') is not True or not _done(resolution):
            continue
        values = {str(resolution[field]) for field in ('id', 'url') if resolution.get(field)}
        for value in list(values):
            try:
                values.add(canonical_url(value))
            except ReviewError:
                pass
        if identities & values:
            return True
    return False


def _reconcile(state, snapshot, root, now, initial=False, start_today=False):
    local_reviews = load_review_state(root)
    answers = {(row.get('section'), str(row.get('id'))): deepcopy(row) for row in state.get('user_answers', [])}
    for row in snapshot.get('user_answers', []):
        key = (row.get('section'), str(row.get('id')))
        if key not in answers or _instant(row['answered_at']) > _instant(answers[key]['answered_at']):
            answers[key] = deepcopy(row)
    state['user_answers'] = list(answers.values())
    priorities = snapshot.get('priorities', [])
    observed = {_identity(row): row for row in priorities if _identity(row)}
    for resolution in snapshot.get('resolutions', []):
        if resolution.get('verified') is True and resolution.get('section') == 'priorities' and _identity(resolution):
            observed[_identity(resolution)] = resolution
    if initial:
        state['selected_priorities'] = [{'id': _identity(row), 'item': deepcopy(row), 'completed': False} for row in priorities if _identity(row) and row.get('verified') is not False and not _done(row)]
    else:
        selected = state['selected_priorities']
        if start_today:
            selected = [row for row in selected if not row['completed']]
        for row in selected:
            fresh = observed.get(row['id'])
            if fresh:
                confirmations = {key: value for key, value in row['item'].items() if key.startswith('user_') or key in ('confirmed', 'confirmation')}
                row['item'].update(deepcopy(fresh))
                row['item'].update(confirmations)
                row['completed'] = row['completed'] or _done(fresh)
        state['selected_priorities'] = selected
    for row in state['selected_priorities']:
        answer = answers.get(('priorities', row['id']))
        if answer and str(answer.get('status') or answer.get('outcome') or '').lower() in TERMINAL:
            row['completed'] = True
    chosen = {row['id'] for row in state['selected_priorities']}
    candidates = snapshot.get('work_suggestions', []) + priorities
    if not isinstance(candidates, list):
        raise WorkspaceError('Published work suggestions must be a list.')
    suggestions = []
    known = set()
    for item in candidates:
        if not isinstance(item, dict):
            raise WorkspaceError('Published work suggestions must contain objects.')
        key = _identity(item)
        if not key or key in known or key in chosen:
            continue
        known.add(key)
        if item.get('verified') is False or _done(item) or _confirmed_finished(item, snapshot, answers) or _locally_done_review(item, snapshot, local_reviews, now):
            continue
        fingerprint = material_fingerprint(item)
        if fingerprint in state['dismissed'].get(key, []) or fingerprint in _accepted_fingerprints(state, key):
            continue
        suggestions.append({'id': key, 'fingerprint': fingerprint, 'item': deepcopy(item)})
    # Incomplete refreshes must not erase already proposed work.
    for row in state['suggestions']:
        if not _confirmed_finished(row['item'], snapshot, answers) and not _locally_done_review(row['item'], snapshot, local_reviews, now) and row['id'] not in known and row['id'] not in chosen and row['fingerprint'] not in _accepted_fingerprints(state, row['id']) and row['fingerprint'] not in state['dismissed'].get(row['id'], []):
            suggestions.append(row)
    state['suggestions'] = suggestions


def open_workspace(root, snapshot_path, now=None):
    with _locked(root) as folder:
        state = _read(root, folder)
        if state:
            return deepcopy(_expire(root, folder, state, _now(now)))
        snapshot, relative = published_snapshot(root, snapshot_path)
        state = {'schema_version': 1, 'version': 1, 'active_snapshot': relative,
                 'date': snapshot['report']['date'], 'timezone': snapshot['report']['timezone'],
                 'selected_priorities': [], 'suggestions': [], 'accepted': {}, 'dismissed': {}, 'refresh': None}
        _reconcile(state, snapshot, root, _now(now), initial=True)
        _write(folder, state)
        apply_verified_re_requests(root, snapshot, now=_now(now))
        return deepcopy(state)


def begin_refresh(root, action, date, timezone, now=None):
    if action not in ('refresh', 'start_today', 'today'):
        raise WorkspaceError('Choose Refresh all or Start today.')
    _day(date, timezone)
    instant = _now(now)
    with _locked(root) as folder:
        state = _expire(root, folder, _read(root, folder), instant)
        if state is None:
            raise WorkspaceError('Open a published Morning Coffee snapshot before refreshing.')
        automatic = action == 'today'
        if automatic:
            if date < state['date']:
                raise WorkspaceError('The active workspace is dated after today. Preserve it and inspect its local date before refreshing.')
            action = 'refresh' if (date, timezone) == (state['date'], state['timezone']) else 'start_today'
        request = state.get('refresh')
        if request and request['status'] in ('pending', 'running'):
            if automatic and (request['action'], request['date'], request['timezone']) != (action, date, timezone):
                raise WorkspaceError('A refresh for another day or action is already running. Complete or fail its exact request ID before starting today.')
            return {'created': False, 'request': deepcopy(request), 'state': deepcopy(state)}
        if action == 'refresh' and (date, timezone) != (state['date'], state['timezone']):
            raise WorkspaceError('Use Start today to move the workspace to another local day.')
        request = {'id': str(uuid4()), 'action': action, 'date': date, 'timezone': timezone,
                   'status': 'pending', 'requested_at': instant.isoformat(), 'updated_at': instant.isoformat(),
                   'previous_snapshot': state['active_snapshot'], 'previous_version': state['version']}
        state['refresh'] = request
        state['version'] += 1
        _write(folder, state)
        return {'created': True, 'request': deepcopy(request), 'state': deepcopy(state)}


def begin_today(root, timezone, now=None):
    """Select same-day refresh or authorized rollover under the workspace lock."""
    instant = _now(now)
    try:
        date = instant.astimezone(ZoneInfo(timezone)).date().isoformat()
    except (ValueError, TypeError, KeyError) as exc:
        raise WorkspaceError('Choose a valid IANA timezone.') from exc
    return begin_refresh(root, 'today', date, timezone, now=instant)


def mark_dispatch(root, request_id, success, error=None, now=None):
    instant = _now(now)
    with _locked(root) as folder:
        state = _expire(root, folder, _read(root, folder), instant)
        request = state and state.get('refresh')
        if not request or request['id'] != request_id:
            raise WorkspaceError('This refresh request is stale. Reload the workspace status.')
        if request['status'] not in ('pending', 'running'):
            return deepcopy(state)
        request.update(status='running' if success else 'failed', updated_at=instant.isoformat())
        if not success:
            # Never expose remote error text, URL query parameters, or credentials.
            request['error'] = 'Source refresh requires T3. Open T3 and check its refresh bridge, then try Refresh all again.'
        state['version'] += 1
        _write(folder, state)
        return deepcopy(state)


def complete_refresh(root, snapshot_path, request_id=None, now=None):
    snapshot, relative = published_snapshot(root, snapshot_path)
    instant = _now(now)
    with _locked(root) as folder:
        state = _expire(root, folder, _read(root, folder), instant)
        if state is None:
            raise WorkspaceError('Open the workspace before applying a refresh.')
        request = state.get('refresh')
        if request_id is not None:
            if not request or request['id'] != request_id or request['status'] not in ('pending', 'running'):
                raise WorkspaceError('This refresh completion is stale. Existing workspace facts were preserved.')
            date, zone = request['date'], request['timezone']
            start_today = request['action'] == 'start_today'
        else:
            if request and request['status'] in ('pending', 'running'):
                raise WorkspaceError('A refresh is already running. Complete it using its request ID.')
            date, zone = state['date'], state['timezone']
            start_today = False
        if (snapshot['report']['date'], snapshot['report']['timezone']) != (date, zone):
            raise WorkspaceError('The published refresh does not match the requested local day and timezone.')
        previous, _ = published_snapshot(root, state['active_snapshot'])
        if _instant(snapshot['collected_at']) <= _instant(previous['collected_at']):
            raise WorkspaceError('The refreshed snapshot must be newer than the active snapshot.')
        if request_id is not None and _instant(snapshot['collected_at']) < _instant(request['requested_at']):
            raise WorkspaceError('The refreshed snapshot predates this request. Collect fresh sources before completing it.')
        _reconcile(state, snapshot, root, instant, start_today=start_today)
        state.update(active_snapshot=relative, date=date, timezone=zone, version=state['version'] + 1)
        if request_id is not None:
            request.update(status='completed', updated_at=instant.isoformat())
            request.pop('error', None)
        _write(folder, state)
        apply_verified_re_requests(root, snapshot, now=instant)
        return deepcopy(state)


def suggestion_action(root, request, now=None):
    if (not isinstance(request, dict) or set(request) != {'action', 'id', 'fingerprint'} or
            request['action'] not in ('accept', 'dismiss') or not isinstance(request['id'], str) or
            not isinstance(request['fingerprint'], str) or not re.fullmatch(r'[a-f0-9]{64}', request['fingerprint'])):
        raise WorkspaceError('Choose Add to today or Dismiss for a known suggestion.')
    with _locked(root) as folder:
        state = _read(root, folder)
        if state is None:
            raise WorkspaceError('Open the workspace before choosing work.')
        key = request['id']
        fingerprint = request['fingerprint']
        # A delayed retry acknowledges only the version originally chosen, even
        # when a new material version now occupies the same source identity.
        acknowledged = (_accepted_fingerprints(state, key) if request['action'] == 'accept'
                        else state['dismissed'].get(key, []))
        if fingerprint in acknowledged:
            return deepcopy(state)
        row = next((row for row in state['suggestions'] if row['id'] == key), None)
        if row is None or row['fingerprint'] != fingerprint:
            raise StaleWorkspaceError('This suggestion changed. Reload the workspace before choosing work.')
        if request['action'] == 'accept':
            item = row['item']
            action = {'action': 'add', 'title': item.get('title') or item.get('action') or key}
            if item.get('project_tags') is not None:
                action['project_tags'] = item['project_tags']
            # Stable identity makes a retry safe if task storage commits before this manifest.
            task_id = hashlib.sha256(('workspace-suggestion:' + key + ':' + row['fingerprint']).encode()).hexdigest()[:32]
            result = save_todo_action(root, action, now=_now(now), task_id=task_id, timezone_name=state['timezone'])
            previous = state['accepted'].get(key)
            versions = deepcopy(previous.get('previous_versions', [])) + [{field: value for field, value in previous.items() if field != 'previous_versions'}] if previous else []
            state['accepted'][key] = {'fingerprint': row['fingerprint'], 'task_id': result['item']['id'], 'source_version': state['version'], 'previous_versions': versions}
        else:
            state['dismissed'].setdefault(key, []).append(row['fingerprint'])
        state['suggestions'] = [item for item in state['suggestions'] if item['id'] != key]
        state['version'] += 1
        _write(folder, state)
        return deepcopy(state)


def public_workspace(state):
    if state is None:
        return None
    result = {key: deepcopy(state[key]) for key in ('version', 'date', 'timezone', 'selected_priorities', 'suggestions', 'accepted')}
    request = state.get('refresh')
    result['refresh'] = {key: request[key] for key in ('id', 'action', 'date', 'timezone', 'status', 'requested_at', 'updated_at', 'error') if key in request} if request else None
    return result


def workspace_snapshot(root, state=None, validated_snapshot=None):
    """Read current facts with the user's chosen work and confirmations overlaid."""
    state = load_workspace(root) if state is None else state
    if state is None:
        raise WorkspaceError('Open a published Morning Coffee snapshot first.')
    snapshot = None
    if validated_snapshot is None:
        snapshot, _ = published_snapshot(root, state['active_snapshot'])
    else:
        # Only reuse a snapshot returned with this state by
        # load_workspace_with_snapshot; bind it to the exact validated pointer.
        snapshot, relative = validated_snapshot
        if relative != state['active_snapshot']:
            raise WorkspaceError('Choose the snapshot referenced by the active workspace.')
    snapshot['priorities'] = [deepcopy(row['item']) for row in state['selected_priorities'] if not row['completed']]
    snapshot['user_answers'] = deepcopy(state.get('user_answers', []))
    return snapshot


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, help='Configured report root; never obtain this from a webhook payload')
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect')
    begin = commands.add_parser('begin', help='Explicitly start today, or refresh when the active workspace is already today')
    begin.add_argument('--timezone', required=True, help='User IANA timezone; today is resolved at the time of this command')
    complete = commands.add_parser('complete')
    complete.add_argument('--request-id', required=True)
    complete.add_argument('--snapshot', type=Path, required=True)
    apply = commands.add_parser('apply')
    apply.add_argument('--snapshot', type=Path, required=True)
    fail = commands.add_parser('fail')
    fail.add_argument('--request-id', required=True)
    fail.add_argument('--message', help='Accepted for operator compatibility; public errors always use safe fixed wording')
    configure = commands.add_parser('configure')
    configure.add_argument('--config-file', required=True, help='Private JSON file or - for stdin; configuration is never printed')
    for command in (inspect, begin, complete, apply, fail, configure):
        command.add_argument('--root', type=Path, default=argparse.SUPPRESS, help='Configured report root')
    args = parser.parse_args()
    if args.root is None:
        parser.error('--root is required')
    try:
        if args.command == 'configure':
            config = json.load(sys.stdin) if args.config_file == '-' else _json(Path(args.config_file))
            result = configure_bridge(args.root, config)
        elif args.command == 'inspect':
            state = load_workspace(args.root)
            result = public_workspace(state)
            if state:
                # Local assistant CLI needs the validated pointer; HTTP uses public_workspace directly.
                result['active_snapshot'] = state['active_snapshot']
        elif args.command == 'begin':
            started = begin_today(args.root, args.timezone)
            result = {'created': started['created'], 'request': public_workspace(started['state'])['refresh'],
                      'active_snapshot': started['state']['active_snapshot']}
        else:
            if args.command == 'complete':
                UUID(args.request_id)
                state = complete_refresh(args.root, args.snapshot, request_id=args.request_id)
            elif args.command == 'apply':
                state = complete_refresh(args.root, args.snapshot)
            else:
                UUID(args.request_id)
                state = mark_dispatch(args.root, args.request_id, False)
            result = public_workspace(state)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (WorkspaceError, ValueError, OSError) as exc:
        # Exception text from OS/config parsers can contain private data.
        print(str(exc) if isinstance(exc, WorkspaceError) else 'Workspace operation failed; existing state was preserved.', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
