"""Private local day-plan retention and submission markup. No provider writes."""
from datetime import date, datetime, timezone
from contextlib import contextmanager
import fcntl
from pathlib import Path
import html
import json
import os
import secrets
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from day_calendar import calendar_data, plan_revision, focus_name

LABELS = {'focus': '🔎 Focus', 'exercise': '👟 Exercise', 'dog_walk': '🐕 Dog walk', 'lunch': '🥪 Lunch'}


class PlanError(ValueError):
    pass


class StalePlanError(PlanError):
    pass


def _folder(root, day, zone):
    date.fromisoformat(day)
    ZoneInfo(zone)
    return Path(root) / zone.replace('/', '__') / day / 'submitted-plans'


def _blocks(blocks):
    if not isinstance(blocks, list) or len(blocks) > 4:
        raise PlanError('Submit up to four blocks.')
    result, kinds = [], set()
    for block in blocks:
        if not isinstance(block, dict):
            raise PlanError('A selected block is invalid.')
        kind, start, minutes = block.get('kind'), block.get('start'), block.get('minutes')
        if kind not in LABELS or kind in kinds or type(start) is not int or type(minutes) is not int:
            raise PlanError('A block is invalid or duplicated.')
        kinds.add(kind)
        if start % 15 or not 0 <= start < 1440 or minutes <= 0 or start + minutes > 1440:
            raise PlanError('Use quarter-hour starts within the report day.')
        # Keep previously supported longer lengths readable/removable; new short focus uses quarter hours.
        if (kind == 'focus' and (minutes < 15 or (minutes < 120 and minutes % 15))) or (kind == 'exercise' and minutes != 60) or (kind in ('dog_walk', 'lunch') and minutes != 30):
            raise PlanError('Use focus blocks in 15-minute increments, one hour for exercise, and thirty minutes for lunch or dog walks.')
        if any(start < row['start'] + row['minutes'] and row['start'] < start + minutes for row in result):
            raise PlanError('Your selected blocks overlap. Move them before submitting.')
        try:
            name = focus_name(block.get('name', '')) if kind == 'focus' else ''
            if kind != 'focus' and 'name' in block:
                raise ValueError('Only focus blocks can have a custom name.')
        except ValueError as exc:
            raise PlanError(str(exc)) from exc
        result.append({'kind': kind, 'start': start, 'minutes': minutes, **({'name': name} if name else {})})
    return sorted(result, key=lambda row: (row['start'], row['kind']))


def validate_plan(snapshot, request):
    report = snapshot['report']
    if not isinstance(request, dict) or request.get('date') != report['date'] or request.get('timezone') != report['timezone']:
        raise PlanError('This submission session belongs to a different day or timezone.')
    data = calendar_data(snapshot)
    if not data['verified']:
        raise PlanError('Calendar availability is unverified. Refresh Coffee before submitting a plan.')
    blocks = _blocks(request.get('blocks'))
    for block in blocks:
        domain = next(row for row in data['blocks'] if row['kind'] == block['kind'])
        if not domain['min_start'] <= block['start'] < block['start'] + block['minutes'] <= domain['max_end']:
            raise PlanError('A block is outside its checked scheduling window. Refresh Coffee or choose a verified time.')
        if any(block['start'] < row['end'] and row['start'] < block['start'] + block['minutes'] for row in data['fixed']):
            raise PlanError('A selected block overlaps a calendar event. Move it before submitting.')
    return blocks


@contextmanager
def _plan_lock(root, day, zone):
    folder = _folder(root, day, zone)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
    with os.fdopen(os.open(folder / '.lock', os.O_RDWR | os.O_CREAT, 0o600), 'r+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield folder


def _append_plan(folder, record, now=None):
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise PlanError('Submission time must include a timezone.')
    record = dict(record, submitted_at=instant.isoformat())
    name = instant.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + secrets.token_hex(6) + '.json'
    temporary = folder / ('.' + name + '.tmp')
    target = folder / name
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(record, path=str(target))


def save_plan(root, snapshot, request, now=None, require_revision=False):
    """Append an immutable private record. This is a chosen plan, never completion evidence."""
    blocks = validate_plan(snapshot, request)
    report = snapshot['report']
    record = {'version': 1, 'date': report['date'], 'timezone': report['timezone'], 'blocks': blocks,
              'calendar_checked_at': (snapshot.get('availability') or {}).get('checked_at'),
              'calendar_coverage': (snapshot.get('availability') or {}).get('coverage', ''),
              'source_collected_at': snapshot.get('collected_at'), 'kind': 'submitted-local-plan'}
    with _plan_lock(root, report['date'], report['timezone']) as folder:
        if require_revision or 'base_revision' in request:
            latest = latest_plan(root, report['date'], report['timezone'])
            if 'base_revision' not in request or request['base_revision'] != plan_revision(latest):
                raise StalePlanError('Your saved plan changed. Your draft is still available; reload the workspace before submitting it.')
        return _append_plan(folder, record, now)


def remove_plan_block(root, snapshot, request, now=None):
    """Remove exactly one saved local choice, retaining every immutable prior version."""
    report = snapshot['report']
    if not isinstance(request, dict) or set(request) != {'date', 'timezone', 'revision', 'block'}:
        raise PlanError('Choose an existing submitted local plan block to remove.')
    if request['date'] != report['date'] or request['timezone'] != report['timezone']:
        raise PlanError('This removal session belongs to a different day or timezone.')
    block = request['block']
    if not isinstance(block, dict) or set(block) != {'kind', 'start', 'minutes'}:
        raise PlanError('Choose an existing submitted local plan block to remove.')
    block = _blocks([block])[0]
    with _plan_lock(root, report['date'], report['timezone']) as folder:
        latest = latest_plan(root, report['date'], report['timezone'])
        if latest is None or request['revision'] != plan_revision(latest):
            raise StalePlanError('Your saved plan changed. Reload the workspace before removing a block.')
        chosen = next((row for row in latest['blocks'] if all(row[key] == block[key] for key in ('kind', 'start', 'minutes'))), None)
        if chosen is None:
            raise PlanError('That block is not in your latest submitted local plan.')
        record = {key: value for key, value in latest.items() if key not in ('path', 'warnings')}
        record.update(blocks=[row for row in latest['blocks'] if row != chosen],
                      previous_revision=request['revision'], removed_block=chosen)
        return _append_plan(folder, record, now)


def latest_plan(root, day, zone, with_warnings=False):
    """Read only this local day's latest valid submission; optionally expose damaged-file warnings."""
    warnings = []
    result = None
    for path in sorted(_folder(root, day, zone).glob('*.json'), reverse=True):
        try:
            record = json.loads(path.read_text())
            stamp = datetime.fromisoformat(record['submitted_at'].replace('Z', '+00:00'))
            if record.get('version') != 1 or record.get('date') != day or record.get('timezone') != zone or stamp.tzinfo is None or record.get('kind') != 'submitted-local-plan':
                raise ValueError('invalid metadata')
            blocks = _blocks(record.get('blocks'))
            result = dict(record, blocks=blocks, path=str(path))
            break
        except (ValueError, TypeError, KeyError, OSError):
            warnings.append('An unreadable submitted plan was skipped: ' + path.name)
    if with_warnings:
        return {'plan': result, 'warnings': warnings}
    if result is not None and warnings:
        result['warnings'] = warnings
    if result is None and warnings:
        raise PlanError('No valid submitted plan could be read. ' + ' '.join(warnings))
    return result


def render_submission(snapshot):
    config = snapshot.get('plan_submission') or {}
    endpoint, token = config.get('endpoint'), config.get('token')
    ready = False
    if isinstance(endpoint, str) and isinstance(token, str):
        try:
            parsed = urlsplit(endpoint)
            ready = (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and parsed.port and
                     parsed.path == '/submit' and not parsed.query and not parsed.fragment and
                     not parsed.username and not parsed.password and len(token) >= 32)
        except ValueError:
            pass
    result = '<div class="plan-submission"><p class="muted">Save your chosen blocks for Today · stored locally.</p>'
    result += '<button type="button" class="plan-submit-button"' + ('' if ready else ' disabled') + '>Review &amp; submit plan</button>'
    if not ready:
        server = Path(__file__).resolve().with_name('local_plan_server.py')
        command = 'python3 ' + str(server) + ' --snapshot /path/to/coffee/snapshot.json --output /tmp/coffee-plan.html --background --open'
        result += '<details><summary>Enable local plan saving</summary><p>Start a local submission session, then open its HTML:</p><pre><code>' + html.escape(command) + '</code></pre><p>No calendar events are created. The local save service runs independently; open its live report URL.</p></details>'
    result += '<div class="plan-submit-review" hidden></div><p class="plan-submit-status" role="status" aria-live="polite"></p>'
    if ready:
        payload = json.dumps({'endpoint': endpoint, 'token': token, 'base_revision': config.get('base_revision')}, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        result += '<script type="application/json" class="plan-submit-data">' + payload + '</script>'
    return result + '</div>'
