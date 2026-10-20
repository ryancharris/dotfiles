"""Render a local, movable day planner from timestamped calendar evidence."""
from datetime import date, datetime, time
import html
import json
from zoneinfo import ZoneInfo
from plan_day import GOALS, stamp, suggest, planning_bounds

LABELS = {'focus': '🔎 Focus', 'exercise': '👟 Exercise', 'dog_walk': '🐕 Dog walk', 'lunch': '🥪 Lunch'}
E = lambda value: html.escape(str(value), quote=True)


def _visible(title):
    value = str(title).strip()
    while value and not value[0].isalnum():
        value = value[1:]
    return value.strip().casefold() not in ('daycare dropoff', 'family time')


def calendar_data(snapshot, read_only=False):
    """Use explicit starts/ends only; display times are never scheduling evidence."""
    timezone = ZoneInfo(snapshot['report']['timezone'])
    day = date.fromisoformat(snapshot['report']['date'])
    availability = snapshot.get('availability') or {}
    plan = suggest(snapshot) if not read_only else {'status': 'suggested' if availability.get('status') == 'complete' else 'unverified', 'suggestions': [], 'note': '', 'coverage': availability.get('coverage', 'Availability not collected.'), 'checked_at': availability.get('checked_at')}
    def minute(value):
        local = stamp(value, timezone)
        return (local.date() - day).days * 1440 + local.hour * 60 + local.minute + local.second / 60
    def clock(value, fallback):
        try:
            parsed = time.fromisoformat(value)
            return parsed.hour * 60 + parsed.minute
        except (ValueError, TypeError):
            return fallback
    lower, upper = 0, 1440
    work_start = clock(availability.get('window_start'), 540)
    work_end = clock(availability.get('window_end'), 1020)
    if work_end <= work_start:
        work_start, work_end = 540, 1020
    try:
        _, _, _, _, verified_start, verified_end = planning_bounds(snapshot)
        verified_start, verified_end = minute(verified_start.isoformat()), minute(verified_end.isoformat())
    except (ValueError, KeyError, TypeError):
        verified_start, verified_end = work_start, work_end
    def interval(item):
        try:
            start, end = minute(item['start']), minute(item['end'])
            return (max(lower, start), min(upper, end)) if start < end and start < upper and end > lower else None
        except (KeyError, TypeError, ValueError):
            return None
    fixed, visible_busy = [], []
    for event in (snapshot.get('agenda') or {}).get('events', []):
        if event.get('cancelled') or event.get('declined') or event.get('_retained_at'):
            continue
        bounds = interval(event)
        if not bounds:
            continue
        start, end = bounds
        visible = _visible(event.get('title', ''))
        fixed.append({'start': start, 'end': end, 'label': str(event.get('title') or 'Calendar event') if visible else 'Busy',
                      'free': bool(event.get('free')), 'anonymous': not visible})
        visible_busy.append((start, end))
    # Subtract visible busy events so private intervals never duplicate named blocks.
    anonymous = []
    for busy in availability.get('busy', []) if isinstance(availability.get('busy'), list) else []:
        bounds = interval(busy)
        if not bounds:
            continue
        pieces = [bounds]
        for left, right in visible_busy:
            next_pieces = []
            for start, end in pieces:
                if right <= start or left >= end:
                    next_pieces.append((start, end))
                else:
                    if start < left:
                        next_pieces.append((start, left))
                    if right < end:
                        next_pieces.append((right, end))
            pieces = next_pieces
        anonymous.extend(pieces)
    merged = []
    for start, end in sorted(anonymous):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    fixed.extend({'start': start, 'end': end, 'label': 'Busy', 'free': False, 'anonymous': True}
                 for start, end in merged)
    suggestions = {item['kind']: item for item in plan['suggestions']}
    blocks = [{'kind': kind, 'label': LABELS[kind], 'minutes': duration,
               'start': minute(suggestions[kind]['start']) if kind in suggestions else None,
               'min_start': verified_start if kind == 'dog_walk' else max(work_start, verified_start),
               'max_end': verified_end if kind == 'dog_walk' else min(work_end, verified_end)}
              for kind, duration in GOALS.items()] if not read_only else []
    submitted = snapshot.get('submitted_plan')
    submitted_blocks, submitted_at, submitted_error = [], None, ''
    if submitted is not None:
        try:
            if not isinstance(submitted, dict) or submitted.get('date') != str(day) or submitted.get('timezone') != str(timezone):
                raise ValueError('Saved plan belongs to a different day or timezone')
            if not isinstance(submitted.get('blocks'), list):
                raise ValueError('Saved plan has no block list')
            seen = set()
            for item in submitted['blocks']:
                kind, start, duration = item['kind'], item['start'], item['minutes']
                if kind not in GOALS or kind in seen or type(start) is not int or type(duration) is not int:
                    raise ValueError('Saved plan has an invalid block')
                if start < 0 or duration < GOALS[kind] or (kind != 'focus' and duration != GOALS[kind]) or start + duration > 1440:
                    raise ValueError('Saved plan has an invalid time or duration')
                seen.add(kind)
                submitted_blocks.append({'kind': kind, 'label': LABELS[kind], 'start': start, 'minutes': duration,
                                         'conflict': any(start < event['end'] and event['start'] < start + duration for event in fixed)})
            submitted_at = stamp(submitted['submitted_at'], timezone).strftime('%H:%M %Z')
        except (ValueError, TypeError, KeyError):
            submitted_blocks, submitted_at = [], None
            submitted_error = 'Saved plan unavailable; submit it again in Coffee.'
    if not read_only and submitted_at is not None:
        saved = {item['kind']: item for item in submitted_blocks}
        accepted, needs_time = [], []
        for block in blocks:
            selected = saved.get(block['kind'])
            block['start'] = None
            if selected:
                start, end = selected['start'], selected['start'] + selected['minutes']
                valid = (not selected['conflict'] and start >= block['min_start'] and end <= block['max_end'] and
                         not any(start < other['start'] + other['minutes'] and other['start'] < end for other in accepted))
                if valid:
                    block['start'], block['minutes'] = start, selected['minutes']
                    accepted.append(block)
                else:
                    needs_time.append(block['label'])
        plan['note'] = 'Your submitted plan · edit and submit again.'
        if needs_time:
            plan['note'] += ' Needs a new time: ' + ', '.join(needs_time) + '.'
    if submitted_error:
        plan['note'] = submitted_error
    try:
        now = minute(plan.get('evaluated_at') or snapshot['collected_at'])
    except (ValueError, KeyError, TypeError):
        now = lower
    return {'start': lower, 'end': upper, 'now': now, 'read_only': read_only,
            'verified_start': verified_start, 'verified_end': verified_end, 'timezone': str(timezone), 'date': str(day),
            'verified': plan['status'] != 'unverified', 'fixed': sorted(fixed, key=lambda row: row['start']),
            'blocks': blocks, 'submitted_blocks': submitted_blocks, 'submitted_at': submitted_at,
            'submitted_error': submitted_error, 'note': plan['note'], 'coverage': plan['coverage'],
            'checked_at': plan.get('checked_at')}


def _clock(minutes):
    return f'{int(minutes) // 60:02}:{int(minutes) % 60:02}'


def render_calendar(snapshot, read_only=False):
    data = calendar_data(snapshot, read_only=read_only)
    lower, upper = data['start'], data['end']
    span = upper - lower
    def position(start, end):
        return f'top:{(start-lower)/span*100:.4f}%;height:{(end-start)/span*100:.4f}%'
    ticks = ''.join('<div class="day-tick" style="top:' + str((point - lower) / span * 100) + '%"><span>' +
                    _clock(point) + '</span></div>' for point in range(int(lower), int(upper) + 1, 60))
    fixed = ''
    # Share the fixed lane when events overlap instead of hiding one another.
    groups, group, until = [], [], -1
    for item in data['fixed']:
        if item['start'] >= until and group:
            groups.append(group)
            group = []
        group.append(item)
        until = max(until, item['end']) if len(group) > 1 else item['end']
    if group:
        groups.append(group)
    for group in groups:
        ends = []
        for item in group:
            column = next((index for index, end in enumerate(ends) if end <= item['start']), len(ends))
            if column == len(ends):
                ends.append(item['end'])
            else:
                ends[column] = item['end']
            item['_column'] = column
        for item in group:
            item['_columns'] = len(ends)
    for item in data['fixed']:
        classes = 'day-fixed' + (' day-short' if item['end'] - item['start'] < 45 else '') + (' day-free' if item['free'] else '') + (' day-anonymous' if item['anonymous'] else '')
        fixed += '<div class="' + classes + '" style="' + position(item['start'], item['end']) + ';left:' + str(item['_column'] / item['_columns'] * 100) + '%;width:' + str(100 / item['_columns']) + '%" title="' + E(item['label'] + ' · ' + _clock(item['start']) + '–' + _clock(item['end'])) + '"><b>' + E(item['label']) + '</b><span>' + _clock(item['start']) + '–' + _clock(item['end']) + (' · free' if item['free'] else '') + '</span></div>'
    submitted_markup = ''
    if read_only:
        for item in data['submitted_blocks']:
            start, end = item['start'], item['start'] + item['minutes']
            classes = 'day-submitted-block' + (' day-short' if item['minutes'] < 45 else '') + (' day-submitted-conflict' if item['conflict'] else '')
            submitted_markup += '<div class="' + classes + '" data-kind="' + item['kind'] + '" style="' + position(start, end) + '" title="' + E(item['label'] + ' · ' + _clock(start) + '–' + _clock(end) + (' · overlaps calendar' if item['conflict'] else '')) + '"><b>' + E(item['label']) + '</b><span>' + _clock(start) + '–' + _clock(end) + '</span></div>'
    blocks, controls = '', '' 
    for block in data['blocks']:
        kind, start = block['kind'], block['start']
        clock = _clock(start) if start is not None else ''
        blocks += '<button type="button" class="day-block' + (' day-short' if block['minutes'] < 45 else '') + '" data-kind="' + kind + '"' + (' style="' + position(start, start + block['minutes']) + '"' if start is not None else ' hidden') + ' aria-label="' + E(block['label'] + ', ' + str(block['minutes']) + ' minutes. Use arrow keys to move 15 minutes.') + '"><b>' + E(block['label']) + '</b><span>' + (clock + '–' + _clock(start + block['minutes']) if start is not None else '') + '</span></button>'
        controls += '<div class="day-control" data-kind="' + kind + '"><label for="day-time-' + kind + '">' + E(block['label']) + ' <small>' + str(block['minutes']) + 'm</small></label><input id="day-time-' + kind + '" type="time" step="900" value="' + clock + '" aria-label="' + E(block['label'] + ' start time') + '"><button type="button" data-place="' + kind + '"' + (' hidden' if start is not None else '') + '>Place</button><button type="button" data-remove="' + kind + '"' + (' hidden' if start is None else '') + ' aria-label="Unplace ' + E(block['label']) + '">×</button></div>'
    for item in data['fixed']:
        item.pop('_column', None)
        item.pop('_columns', None)
    serialized = json.dumps(data, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    checked = ''
    if data['checked_at']:
        try:
            checked = ' · checked ' + stamp(data['checked_at'], ZoneInfo(data['timezone'])).strftime('%H:%M %Z')
        except (TypeError, ValueError):
            pass
    scope = 'Primary calendar only' if any(label in str(data['coverage']).casefold() for label in ('primary calendar only', 'primary-only', 'primary only')) else 'Checked calendars'
    if not data['verified']:
        scope = 'Availability unverified'
    title = '🍵 Today’s calendar' if read_only else '🗓️ Shape your day'
    view_class = (' day-read-only' + (' day-has-submitted' if data['submitted_at'] is not None else '')) if read_only else ''
    toolbar = '' if read_only else '<button type="button" class="day-reset">Reset</button>'
    instructions = 'Calendar and submitted plan · read only.' if read_only else 'Drag or edit times · dog walks anytime · submit below to save.'
    headings = '<span>Calendar</span>' + ('<span>Your submitted plan</span>' if read_only and data['submitted_at'] is not None else '' if read_only else '<span>Your plan</span>')
    submitted_note = ''
    if read_only:
        submitted_note = (('Submitted ' if data['submitted_blocks'] else 'Empty plan submitted ') + data['submitted_at'] + ' · saved locally.' if data['submitted_at'] is not None else data['submitted_error'] or 'No plan submitted yet.')
        conflicts = [item['label'] for item in data['submitted_blocks'] if item['conflict']]
        if conflicts:
            submitted_note += ' Overlaps current calendar: ' + ', '.join(conflicts) + '.'
    interactive = '' if read_only else (
        '<div class="day-controls" aria-label="Plan times and unplaced blocks">' + controls + '</div>'
        '<p class="day-warning" role="status" aria-live="polite"></p>'
        '<div id="coffee-confirmation"></div>'
        '<noscript><p>Enable JavaScript to move and submit blocks.</p></noscript>'
        '<script type="application/json" class="day-calendar-data">' + serialized + '</script>')
    return ('<section id="focus-exercise" class="day-calendar' + view_class + '" aria-labelledby="day-calendar-title">'
            '<div class="section-head"><h2 id="day-calendar-title">' + title + '</h2>' + toolbar + '</div>'
            '<p class="day-calendar-note">' + instructions + '</p>'
            '<p class="day-calendar-meta">' + E(data['timezone'] + ' · ' + scope + checked) + '</p>'
            + ('<p class="day-plan-status">' + E(submitted_note) + '</p>' if read_only else '<p class="day-plan-status">' + E(data['note']) + '</p>') +
            '<div class="day-column-head">' + headings + '</div>'
            '<div class="day-scroll" data-scroll-minute="' + str(max(0, min(data['now'] - 60, 1200))) + '" tabindex="0" aria-label="Full day calendar; scroll for all hours">'
            '<div class="day-board" style="--day-hours:' + str(span / 60) + '">' + ticks +
            '<div class="day-fixed-lane">' + fixed + '</div>' + ('<div class="day-submitted-lane">' + submitted_markup + '</div>' if read_only and data['submitted_at'] is not None else '' if read_only else '<div class="day-plan-lane">' + blocks + '</div>') + '</div></div>'
            + interactive + '</section>')
