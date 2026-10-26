"""24-hour display formatting for clock UI fields, never source prose."""
from copy import deepcopy
from datetime import datetime
import re
from zoneinfo import ZoneInfo
from calendar_display import all_day_event


_MERIDIEM = r'[ap]\.?m\.?'
_TWELVE = re.compile(r'(?<![\w:])(0?[1-9]|1[0-2])(?::([0-5]\d))?\s*(' + _MERIDIEM + r')(?!\w)', re.I)
_RANGE = re.compile(
    r'(?<![\w:])(0?[1-9]|1[0-2])(?::([0-5]\d))?\s*(' + _MERIDIEM + r')?'
    r'\s*([–—-]|to)\s*(0?[1-9]|1[0-2])(?::([0-5]\d))?\s*(' + _MERIDIEM + r')?(?![\w:])', re.I)
_CLOCK = re.compile(r'(?<![\w:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])')


def _hour(hour, meridiem):
    return int(hour) % 12 + (12 if meridiem.lower().startswith('p') else 0)


def clock_label(value):
    """Normalize legacy clock labels, preserving date, timezone and surrounding labels.

    Call only for fields whose purpose is displaying time. Evidence and user/source
    prose must stay verbatim. Ranges may share a meridiem, e.g. 11–1 PM.
    """
    if not isinstance(value, str):
        return value

    def clock_range(match):
        first, minute, first_period, separator, last, last_minute, last_period = match.groups()
        if not (first_period or last_period):
            return match.group(0)
        if not first_period:
            first_period = last_period
            if int(first) % 12 > int(last) % 12:
                first_period = 'am' if last_period.lower().startswith('p') else 'pm'
        if not last_period:
            last_period = first_period
            if int(last) % 12 < int(first) % 12:
                last_period = 'pm' if first_period.lower().startswith('a') else 'am'
        return f'{_hour(first, first_period):02}:{minute or "00"}–{_hour(last, last_period):02}:{last_minute or "00"}'

    value = _RANGE.sub(clock_range, value)
    value = _TWELVE.sub(lambda match: f'{_hour(match[1], match[3]):02}:{match[2] or "00"}', value)
    return _CLOCK.sub(lambda match: f'{int(match[1]):02}:{match[2]}', value)


def local_time(value, zone, with_date=False, with_zone=False):
    """Format an ISO instant in the report timezone; offset-free values are local."""
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    timezone = ZoneInfo(zone)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone).strftime(('%b %d, ' if with_date else '') + '%H:%M' + (' %Z' if with_zone else ''))


def event_time(event, zone):
    if all_day_event(event):
        return 'All day'
    try:
        start = local_time(event['start'], zone)
        return start + ('–' + local_time(event['end'], zone) if event.get('end') else '')
    except (KeyError, ValueError, TypeError, AttributeError):
        return clock_label(event.get('time', 'Time unavailable'))


def display_snapshot(snapshot):
    """Normalize designated UI fields on a copy; saved source facts remain intact."""
    result = deepcopy(snapshot)
    report = result['report']
    zone = report['timezone']
    try:
        report['time'] = local_time(result['collected_at'], zone)
    except (KeyError, ValueError, TypeError, AttributeError):
        report['time'] = clock_label(report['time'])
    for event in result['agenda']['events']:
        event['time'] = event_time(event, zone)
    result['oncall']['shift'] = clock_label(result['oncall']['shift'])
    reviews = result['reviews']
    reviews['collected_label'] = clock_label(reviews['collected_label'])
    if result.get('authored_prs'):
        result['authored_prs']['collected_label'] = clock_label(result['authored_prs'].get('collected_label', ''))
    for item in result['rfcs']['items']:
        item['submitted_local'] = clock_label(item['submitted_local'])
    for update in result.get('updates', {}).get('items', []):
        for field in update.get('fields', []):
            if field['label'] in ('Time', 'Start', 'End', 'Shift', 'Submitted Local'):
                for key in ('before', 'after'):
                    field[key] = clock_label(field[key])
    # Retained-row labels are rendered by their original timestamp, localized here.
    for section, field in (('priorities', None), ('unverified_priorities', None), ('agenda', 'events'),
                           ('reviews', 'items'), ('authored_prs', 'items'), ('rfcs', 'items'), ('yesterday', 'items')):
        rows = result.get(section, []) if field is None else result.get(section, {}).get(field, [])
        for row in rows:
            if row.get('_retained_at'):
                parsed = datetime.fromisoformat(row['_retained_at'].replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=ZoneInfo(zone))
                row['_retained_at'] = parsed.astimezone(ZoneInfo(zone)).isoformat()
    return result
