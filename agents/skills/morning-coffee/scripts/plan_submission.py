"""Private local day-plan retention and submission markup. No provider writes."""
from datetime import date, datetime, timezone
from pathlib import Path
import html
import json
import os
import secrets
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from day_calendar import calendar_data

LABELS = {'focus': '🔎 Focus', 'exercise': '👟 Exercise', 'dog_walk': '🐕 Dog walk', 'lunch': '🥪 Lunch'}


class PlanError(ValueError):
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
        if (kind == 'focus' and minutes < 120) or (kind == 'exercise' and minutes != 60) or (kind in ('dog_walk', 'lunch') and minutes != 30):
            raise PlanError('Use at least two hours for focus, one hour for exercise, and thirty minutes for lunch or dog walks.')
        if any(start < row['start'] + row['minutes'] and row['start'] < start + minutes for row in result):
            raise PlanError('Your selected blocks overlap. Move them before submitting.')
        result.append({'kind': kind, 'start': start, 'minutes': minutes})
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


def save_plan(root, snapshot, request, now=None):
    """Append an immutable private record. This is a chosen plan, never completion evidence."""
    blocks = validate_plan(snapshot, request)
    report = snapshot['report']
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise PlanError('Submission time must include a timezone.')
    folder = _folder(root, report['date'], report['timezone'])
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
    record = {'version': 1, 'date': report['date'], 'timezone': report['timezone'],
              'submitted_at': instant.isoformat(), 'blocks': blocks,
              'calendar_checked_at': (snapshot.get('availability') or {}).get('checked_at'),
              'calendar_coverage': (snapshot.get('availability') or {}).get('coverage', ''),
              'source_collected_at': snapshot.get('collected_at'), 'kind': 'submitted-local-plan'}
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
    result = '<div class="plan-submission"><p class="muted">Save your chosen blocks for today’s Tea · stored locally.</p>'
    result += '<button type="button" class="plan-submit-button"' + ('' if ready else ' disabled') + '>Review &amp; submit plan</button>'
    if not ready:
        server = Path(__file__).resolve().with_name('local_plan_server.py')
        command = 'python3 ' + str(server) + ' --snapshot /path/to/coffee/snapshot.json --output /tmp/coffee-plan.html --background --open'
        result += '<details><summary>Enable local plan saving</summary><p>Start a local submission session, then open its HTML:</p><pre><code>' + html.escape(command) + '</code></pre><p>No calendar events are created. The local save service runs independently; open its live report URL.</p></details>'
    result += '<div class="plan-submit-review" hidden></div><p class="plan-submit-status" role="status" aria-live="polite"></p>'
    if ready:
        payload = json.dumps({'endpoint': endpoint, 'token': token}, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        result += '<script type="application/json" class="plan-submit-data">' + payload + '</script>'
    return result + '</div>'
