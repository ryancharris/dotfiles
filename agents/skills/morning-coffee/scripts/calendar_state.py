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
        if (kind not in ('focus', 'exercise', 'dog_walk', 'lunch') or
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
        if (not isinstance(record, dict) or set(record) - {'history'} != {'version', 'date', 'timezone', 'state'} or
                type(record['version']) is not int or record['version'] not in (1, 2) or
                record['date'] != day or record['timezone'] != timezone or
                not isinstance(record['state'], dict) or
                any(not isinstance(key, str) or not re.fullmatch('[0-9a-f]{64}', key) or
                    type(done) is not bool for key, done in record['state'].items())):
            raise ValueError()
        if record['version'] == 2 and 'history' not in record:
            raise ValueError('Missing calendar action history.')
        record['history'] = validate_events(record.get('history', []), 'calendar')
        return record
    except (WorkspaceError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise CalendarError('Calendar completion choices could not be read. Existing files were preserved; repair ' + path.name + ' before retrying.') from exc


def _read(folder, day, timezone):
    return dict(_read_record(folder, day, timezone)['state'])


def load_calendar_state(root, snapshot, with_warnings=False):
    """Read explicit true/false overrides without changing the active workspace."""
    from workspace_state import WorkspaceError, _safe_folder, _locked
    day, timezone = _scope(snapshot)
    state, warnings = {}, []
    try:
        folder = _safe_folder(root)
        if folder.exists():
            with _locked(root) as folder:
                state = _read(folder, day, timezone)
    except (CalendarError, WorkspaceError) as exc:
        if not with_warnings:
            raise CalendarError(str(exc)) from exc
        warnings.append(str(exc))
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
            record['version'] = 2  # Older writers must not discard retained action history.
            _write(folder, record, filename=_filename(day, timezone))
    except WorkspaceError as exc:
        raise CalendarError(str(exc)) from exc
    return {'key': request['key'], 'done': request['done']}
