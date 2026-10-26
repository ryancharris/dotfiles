"""Provider calendar display policy, independent of scheduling evidence."""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

DISPLAY_START = 8 * 60
DISPLAY_END = 19 * 60


def all_day_event(event):
    if event.get('all_day') is True:
        return True
    try:
        return all(isinstance(event[field], str) and len(event[field]) == 10 and
                   date.fromisoformat(event[field]) for field in ('start', 'end'))
    except (KeyError, ValueError):
        return False


def in_display_window(snapshot, event):
    """Require positive overlap of the report day's local [08:00, 19:00)."""
    if all_day_event(event):
        return True
    try:
        start, end = (datetime.fromisoformat(event[field].replace('Z', '+00:00'))
                      for field in ('start', 'end'))
        if start.tzinfo is None or end.tzinfo is None:
            return False
        start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        report = snapshot['report']
        day, zone = date.fromisoformat(report['date']), ZoneInfo(report['timezone'])
        lower, upper = (datetime.combine(day, time(minutes // 60, minutes % 60), zone)
                        .astimezone(timezone.utc) for minutes in (DISPLAY_START, DISPLAY_END))
        return start < end and start < upper and end > lower
    except (KeyError, ValueError, TypeError, AttributeError):
        # Display strings cannot establish overlap; retain raw evidence for validation.
        return False


def visible_calendar_event(snapshot, event):
    title = str(event.get('title', '')).strip()
    while title and not title[0].isalnum():
        title = title[1:]
    return (not event.get('cancelled') and not event.get('declined') and
            title.strip().casefold() not in ('daycare dropoff', 'family time') and
            in_display_window(snapshot, event))


def visible_calendar_change(snapshot, change):
    """Project summaries without removing their underlying change evidence."""
    if change.get('section') != 'Today':
        return True
    event = change.get('calendar_event')
    if not isinstance(event, dict):
        # Older updates may still identify a current event. Removed legacy rows
        # without authoritative timestamps cannot establish display eligibility.
        candidates = (snapshot.get('agenda', {}).get('events', []) +
                      snapshot.get('removed_calendar_events', []))
        event = next((row for row in candidates
                      if str(row.get('id') or row.get('url') or row.get('title', ''))
                      == str(change.get('id'))), None)
    return isinstance(event, dict) and visible_calendar_event(snapshot, event)
