"""Private calendar completion choices, independent of elapsed time and providers."""
from datetime import date, datetime, timezone as utc_timezone
import hashlib
import json
import re
import secrets
from zoneinfo import ZoneInfo

from local_history import validate_events


class CalendarError(ValueError):
    pass


class StaleCalendarError(CalendarError):
    pass


def _scope(snapshot):
    try:
        report = snapshot['report']
        day, timezone = report['date'], report['timezone']
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError()
        ZoneInfo(timezone)
        return day, timezone
    except (ValueError, TypeError, KeyError) as exc:
        raise CalendarError('Choose a valid report date and IANA timezone.') from exc


def calendar_key(snapshot, row, local=False):
    """Scope a source event or exact local plan choice to this report day."""
    day, timezone = _scope(snapshot)
    if not isinstance(row, dict):
        raise CalendarError('Choose a calendar item listed in this report.')
    if local:
        kind, start, minutes = row.get('kind'), row.get('start'), row.get('minutes')
        if (kind not in ('focus', 'exercise', 'dog_walk', 'lunch', 'learning') or
                type(start) is not int or type(minutes) is not int or
                start < 0 or minutes <= 0 or start + minutes > 1440):
            raise CalendarError('Choose a valid saved local plan block.')
        identity = ['local', kind, start, minutes]
    else:
        source_id, url = row.get('id'), row.get('url')
        if (isinstance(source_id, str) and source_id.strip()) or type(source_id) is int:
            identity = ['source-id', str(source_id)]
        elif isinstance(url, str) and url.strip():
            identity = ['source-url', url]
        else:
            title, start = row.get('title', ''), row.get('start')
            if not isinstance(title, str) or not isinstance(start, str) or not start:
                raise CalendarError('A calendar item needs an ID, URL or title and start time.')
            identity = ['source-fallback', title, start]
    value = json.dumps([day, timezone, identity], ensure_ascii=True, separators=(',', ':'))
    return hashlib.sha256(value.encode()).hexdigest()


def _filename(day, timezone):
    return 'calendar-' + day + '-' + hashlib.sha256(timezone.encode()).hexdigest() + '.json'


def _read_record(folder, day, timezone):
    from workspace_state import WorkspaceError, _json
    path = folder / _filename(day, timezone)
    if not path.exists() and not path.is_symlink():
        return {'version': 1, 'date': day, 'timezone': timezone, 'state': {}, 'history': []}
    try:
        record = _json(path)
        if (not isinstance(record, dict) or set(record) - {'history', 'removed'} != {'version', 'date', 'timezone', 'state'} or
                type(record['version']) is not int or record['version'] not in (1, 2, 3) or
                record['date'] != day or record['timezone'] != timezone or
                not isinstance(record['state'], dict) or
                any(not isinstance(key, str) or not re.fullmatch('[0-9a-f]{64}', key) or
                    type(done) is not bool for key, done in record['state'].items())):
            raise ValueError()
        if record['version'] >= 2 and 'history' not in record:
            raise ValueError('Missing calendar action history.')
        removed = record.get('removed', {})
        if (not isinstance(removed, dict) or
                any(not isinstance(key, str) or not re.fullmatch('[0-9a-f]{64}', key) or
                    not isinstance(value, dict) or set(value) != {'start', 'end'} or
                    not all(isinstance(value[field], str) and value[field] for field in ('start', 'end'))
                    for key, value in removed.items())):
            raise ValueError('Invalid removed calendar events.')
        record['history'] = validate_events(record.get('history', []), 'calendar')
        return record
    except (WorkspaceError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise CalendarError('Calendar completion choices could not be read. Existing files were preserved; repair ' + path.name + ' before retrying.') from exc


def _read(folder, day, timezone):
    return dict(_read_record(folder, day, timezone)['state'])


def load_calendar_state(root, snapshot, with_warnings=False, include_removed=False):
    """Read explicit true/false overrides without changing the active workspace."""
    from workspace_state import WorkspaceError, _safe_folder, _locked
    day, timezone = _scope(snapshot)
    state, removed, warnings = {}, {}, []
    try:
        folder = _safe_folder(root)
        if folder.exists():
            with _locked(root) as folder:
                record = _read_record(folder, day, timezone)
                state, removed = dict(record['state']), dict(record.get('removed', {}))
    except (CalendarError, WorkspaceError) as exc:
        if not with_warnings:
            raise CalendarError(str(exc)) from exc
        warnings.append(str(exc))
    if include_removed:
        return {'state': state, 'removed': removed, 'warnings': warnings}
    return {'state': state, 'warnings': warnings} if with_warnings else state


def _identities(snapshot):
    result = set()
    for rows, local in (((snapshot.get('agenda') or {}).get('events', []), False),
                        ((snapshot.get('submitted_plan') or {}).get('blocks', []), True)):
        for row in rows:
            try:
                result.add(calendar_key(snapshot, row, local=local))
            except CalendarError:
                continue
    return result


def _item_metadata(snapshot, key):
    for rows, local in (((snapshot.get('agenda') or {}).get('events', []), False),
                        ((snapshot.get('submitted_plan') or {}).get('blocks', []), True)):
        for row in rows:
            try:
                if calendar_key(snapshot, row, local=local) == key:
                    fields = ('kind', 'start', 'minutes', 'name') if local else ('id', 'url', 'title', 'start', 'end', 'all_day')
                    return dict({field: row[field] for field in fields if field in row},
                                source='local' if local else 'calendar')
            except CalendarError:
                continue
    raise CalendarError('This calendar item is not listed in this report.')


def save_calendar_state(root, snapshot, request, now=None):
    """Atomically retain a completion override for a currently listed item."""
    from workspace_state import WorkspaceError, _locked, _write
    day, timezone = _scope(snapshot)
    if (not isinstance(request, dict) or set(request) != {'key', 'done'} or
            not isinstance(request['key'], str) or type(request['done']) is not bool):
        raise CalendarError('Send a calendar key and a true or false done state.')
    item = _item_metadata(snapshot, request['key'])
    instant = now or datetime.now(utc_timezone.utc)
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise CalendarError('Calendar choice time must include a timezone.')
    try:
        with _locked(root) as folder:
            record = _read_record(folder, day, timezone)
            state = record['state']
            if state.get(request['key']) is request['done'] and request['key'] in state:
                return {'key': request['key'], 'done': request['done']}
            event = {'id': secrets.token_hex(16), 'at': instant.astimezone(utc_timezone.utc).isoformat(),
                     'action': 'set_done', 'key': request['key'], 'done': request['done'], 'item': item}
            if request['key'] in state:
                event['previous_done'] = state[request['key']]
            state[request['key']] = request['done']
            record['history'].append(event)
            record['version'] = max(2, record['version'])
            _write(folder, record, filename=_filename(day, timezone))
    except WorkspaceError as exc:
        raise CalendarError(str(exc)) from exc
    return {'key': request['key'], 'done': request['done']}


def event_removed(snapshot, event):
    """Removal belongs to this occurrence at these times; a reschedule reappears."""
    value = (snapshot.get('calendar_removed') or {}).get(calendar_key(snapshot, event))
    return value is not None and value == {field: event.get(field) for field in ('start', 'end')}


def scheduling_snapshot(snapshot):
    """Overlay local removals without changing provider evidence or other busy time."""
    from copy import deepcopy
    if not snapshot.get('calendar_removed'):
        return snapshot
    result = deepcopy(snapshot)
    events = result.get('agenda', {}).get('events', [])
    removed = [event for event in events if event_removed(result, event)]
    result.setdefault('removed_calendar_events', []).extend(removed)
    result['agenda']['events'] = [event for event in events if not event_removed(result, event)]
    busy = result.get('availability', {}).get('busy', [])
    # Collectors retain one interval per event. Legacy records have no ID:
    # consume one exact interval, never subtract from an aggregated busy span.
    for event in removed:
        for index, interval in enumerate(busy):
            if (all(interval.get(field) == event.get(field) for field in ('start', 'end')) and
                    ('event_id' not in interval or interval['event_id'] == event.get('id'))):
                busy.pop(index)
                break
    return result


def save_calendar_removal(root, snapshot, request, now=None):
    """Remove or restore a current provider occurrence locally, with stale-tab checks."""
    from workspace_state import WorkspaceError, _locked, _write
    day, timezone = _scope(snapshot)
    if (not isinstance(request, dict) or set(request) != {'key', 'start', 'end', 'removed', 'base_removed'} or
            not isinstance(request['key'], str) or
            any(type(request[field]) is not bool for field in ('removed', 'base_removed'))):
        raise CalendarError('Choose a calendar event to remove or restore.')
    item = _item_metadata(snapshot, request['key'])
    if item['source'] != 'calendar' or not item.get('start') or not item.get('end'):
        raise CalendarError('Only a timestamped calendar event can be removed from today.')
    bounds = {field: item[field] for field in ('start', 'end')}
    if any(request[field] != bounds[field] for field in bounds):
        raise StaleCalendarError('This event moved. Reload today before changing it.')
    instant = now or datetime.now(utc_timezone.utc)
    if instant.tzinfo is None:
        raise CalendarError('Calendar choice time must include a timezone.')
    try:
        with _locked(root) as folder:
            record = _read_record(folder, day, timezone)
            removed = record.setdefault('removed', {})
            current = removed.get(request['key']) == bounds
            if current != request['base_removed']:
                raise StaleCalendarError('This event changed in another tab. Reload today before changing it.')
            if current != request['removed']:
                if request['removed']:
                    removed[request['key']] = bounds
                else:
                    removed.pop(request['key'], None)
                record['history'].append({'id': secrets.token_hex(16), 'at': instant.astimezone(utc_timezone.utc).isoformat(),
                    'action': 'set_removed', 'key': request['key'], 'removed': request['removed'],
                    'previous_removed': current, 'item': item})
                record['version'] = 3
                _write(folder, record, filename=_filename(day, timezone))
    except WorkspaceError as exc:
        raise CalendarError(str(exc)) from exc
    return {field: request[field] for field in ('key', 'start', 'end', 'removed')}
