"""Suggest verified daily blocks; calendar writes require a separate confirmation."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

GOALS = {'focus': 120, 'exercise': 60, 'dog_walk': 30, 'lunch': 30}


def stamp(value, timezone):
    if not isinstance(value, str):
        raise ValueError('Availability timestamp must be a string')
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), time(), timezone)
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timed availability intervals need a timezone')
    return parsed.astimezone(timezone)


def rounded(value):
    """Round forward to a local quarter-hour, preserving busy boundaries."""
    remainder = timedelta(minutes=value.minute % 15, seconds=value.second, microseconds=value.microsecond)
    return value - remainder + (timedelta(minutes=15) if remainder else timedelta())


def planning_bounds(snapshot):
    """Legacy checks cover only their work window; wider coverage must be explicit."""
    availability = snapshot.get('availability') or {}
    timezone = ZoneInfo(snapshot['report']['timezone'])
    day = date.fromisoformat(snapshot['report']['date'])
    day_start = datetime.combine(day, time(), timezone)
    day_end = datetime.combine(day + timedelta(days=1), time(), timezone)
    window_start = datetime.combine(day, time.fromisoformat(availability.get('window_start', '09:00')), timezone)
    window_end = datetime.combine(day, time.fromisoformat(availability.get('window_end', '17:00')), timezone)
    if window_end <= window_start:
        raise ValueError('Planning window must end after its start')
    coverage_start = max(day_start, stamp(availability.get('coverage_start', window_start.isoformat()), timezone))
    coverage_end = min(day_end, stamp(availability.get('coverage_end', window_end.isoformat()), timezone))
    if coverage_end <= coverage_start:
        raise ValueError('Availability coverage must end after its start')
    return day_start, day_end, window_start, window_end, coverage_start, coverage_end


def candidates(free, minutes):
    duration = timedelta(minutes=minutes)
    result = []
    for start, end in free:
        cursor = rounded(start)
        while cursor + duration <= end:
            result.append((cursor, cursor + duration))
            cursor += timedelta(minutes=15)
    return result


def suggest(snapshot):
    availability = snapshot.get('availability') or {}
    result = {'status': 'unverified', 'coverage': availability.get('coverage', 'Availability not collected.'),
              'checked_at': availability.get('checked_at'), 'exercise_minutes': 60, 'focus_minutes': 120,
              'dog_walk_minutes': 30, 'lunch_minutes': 30, 'suggestions': [], 'unscheduled': list(GOALS),
              'note': 'Availability unverified; place blocks manually.'}
    if availability.get('status') != 'complete':
        return result
    try:
        timezone = ZoneInfo(snapshot['report']['timezone'])
        day_start, day_end, window_start, window_end, coverage_start, coverage_end = planning_bounds(snapshot)
        result['window'] = window_start.strftime('%H:%M') + '–' + window_end.strftime('%H:%M') + ' · ' + str(timezone)
        result['coverage_start'], result['coverage_end'] = coverage_start.isoformat(), coverage_end.isoformat()
        evaluated = max(stamp(snapshot['collected_at'], timezone), stamp(availability['checked_at'], timezone))
        result['evaluated_at'] = evaluated.isoformat()
        start = rounded(max(coverage_start, evaluated))
        if not isinstance(availability.get('busy'), list):
            raise ValueError('A complete check must provide busy intervals')
        busy = []
        events = [event for event in snapshot.get('agenda', {}).get('events', [])
                  if event.get('start') and event.get('end') and not event.get('cancelled') and
                  not event.get('declined') and not event.get('_retained_at')]
        for interval in availability['busy'] + events:
            left, right = stamp(interval['start'], timezone), stamp(interval['end'], timezone)
            if right <= left:
                raise ValueError('Busy interval ends before it starts')
            left, right = max(start, left), min(coverage_end, right)
            if left < right:
                busy.append((left, right))
        free, cursor = [], start
        for left, right in sorted(busy):
            if cursor < left:
                free.append((cursor, left))
            cursor = max(cursor, right)
        if cursor < coverage_end:
            free.append((cursor, coverage_end))
        options = {}
        for kind, duration in GOALS.items():
            domain = free if kind == 'dog_walk' else [(max(left, window_start), min(right, window_end)) for left, right in free]
            options[kind] = candidates(domain, duration)
        kinds = list(GOALS)
        noon = day_start + timedelta(hours=12)
        def preferences(slots):
            focus, exercise, dog, lunch = slots
            return (focus[0] if focus else day_end,
                    abs((exercise[0] - noon).total_seconds()) if exercise else float('inf'),
                    abs((lunch[0] - noon).total_seconds()) if lunch else float('inf'),
                    dog[0] if dog else day_end)
        # Sweep time with a 4-bit goal mask. A state stores the best schedule for
        # that mask by this time, avoiding a Cartesian product of candidate slots.
        nodes = sorted({point for rows in options.values() for slot in rows for point in slot})
        states = {point: {} for point in nodes}
        edges = {}
        for index, kind in enumerate(kinds):
            for slot in options[kind]:
                edges.setdefault(slot[0], []).append((index, slot))
        empty = (None,) * len(kinds)
        previous = {0: empty}
        def keep(target, mask, slots):
            if mask not in target or preferences(slots) < preferences(target[mask]):
                target[mask] = slots
        for point in nodes:
            current = states[point]
            for mask, slots in previous.items():
                keep(current, mask, slots)
            for mask, slots in list(current.items()):
                for index, slot in edges.get(point, []):
                    if mask & (1 << index):
                        continue
                    updated = list(slots)
                    updated[index] = slot
                    keep(states[slot[1]], mask | (1 << index), tuple(updated))
            previous = current
        best = min(previous.values(), key=lambda slots: (
                   -sum(slots[index] is not None for index in (0, 1)),
                   -sum(GOALS[kinds[index]] for index in (0, 1) if slots[index]),
                   -sum(slot is not None for slot in slots), preferences(slots)))
        chosen = [(kind, slot) for kind, slot in zip(kinds, best) if slot]
        result['suggestions'] = [{'kind': kind, 'start': slot[0].isoformat(), 'end': slot[1].isoformat(),
                                  'minutes': GOALS[kind]} for kind, slot in sorted(chosen, key=lambda item: item[1][0])]
        result['unscheduled'] = [kind for kind, slot in zip(kinds, best) if not slot]
        result['status'] = 'suggested' if not result['unscheduled'] else 'insufficient'
        labels = {'focus': '2h focus', 'exercise': '1h exercise', 'dog_walk': '30m dog walk', 'lunch': '30m lunch'}
        result['note'] = ('Suggested · nothing booked.' if not result['unscheduled'] else
                          'No verified slot: ' + ', '.join(labels[kind] for kind in result['unscheduled']) + '.')
    except (ValueError, KeyError, TypeError) as exc:
        result.update(status='unverified', suggestions=[], unscheduled=list(GOALS),
                      note='Availability unverified: ' + str(exc))
    return result
