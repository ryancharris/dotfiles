"""Render a local, movable day planner from timestamped calendar evidence."""
from datetime import date, datetime, time, timedelta
import html
import hashlib
import json
import unicodedata
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from plan_day import GOALS, stamp, suggest, planning_bounds
from calendar_state import calendar_key, scheduling_snapshot
from calendar_display import DISPLAY_START, DISPLAY_END, visible_calendar_event

LABELS = {'focus': '🔎 Focus', 'exercise': '👟 Exercise', 'dog_walk': '🐕 Dog walk', 'lunch': '🥪 Lunch'}
E = lambda value: html.escape(str(value), quote=True)
FOCUS_NAME_MAX = 120


def focus_name(value=''):
    """Normalize an optional plain-text focus name; legacy blocks omit it."""
    if not isinstance(value, str) or any(unicodedata.category(char) in ('Cc', 'Cs') for char in value):
        raise ValueError('Use a plain-text focus name without control characters.')
    value = value.strip()
    if len(value) > FOCUS_NAME_MAX:
        raise ValueError(f'Keep the focus name to {FOCUS_NAME_MAX} characters or fewer.')
    return value


def block_label(block):
    """Display an optional focus name without changing the block identity."""
    if block.get('kind') == 'focus':
        name = focus_name(block.get('name', ''))
        return '🔎 ' + name if name else LABELS['focus']
    return LABELS[block['kind']]


def calendar_completion_config(snapshot):
    config = snapshot.get('calendar_interaction')
    if not isinstance(config, dict):
        return None
    try:
        endpoint = urlsplit(config.get('endpoint', ''))
        if (endpoint.scheme == 'http' and endpoint.hostname == '127.0.0.1' and endpoint.port and
                endpoint.path == '/calendar/done' and not endpoint.query and not endpoint.fragment and
                not endpoint.username and not endpoint.password and
                isinstance(config.get('token'), str) and len(config['token']) >= 32):
            return config
    except (ValueError, TypeError):
        pass
    return None


def calendar_completion_ui(snapshot, key, label):
    if not key:
        return '', ''
    mark = (snapshot.get('calendar_state') or {}).get(key)
    attrs = ' data-calendar-key="' + E(key) + '"'
    if type(mark) is bool:
        attrs += ' data-calendar-done="' + str(mark).lower() + '"'
    button = ('<button type="button" data-calendar-toggle aria-pressed="' + str(mark is True).lower() +
              '" aria-label="' + E(('Undo done: ' if mark else 'Mark done: ') + label) + '">' +
              ('Undo done' if mark else 'Done') + '</button>') if calendar_completion_config(snapshot) else ''
    return attrs, button


def calendar_remove_button(snapshot, event, removed=False):
    """Skip only the exact source occurrence in the local planner."""
    if not calendar_completion_config(snapshot) or not event.get('start') or not event.get('end'):
        return ''
    label = 'Undo skip' if removed else 'Skip'
    return ('<button type="button" data-calendar-remove data-event-key="' + E(calendar_key(snapshot, event)) +
            '" data-event-start="' + E(event['start']) + '" data-event-end="' + E(event['end']) +
            '" data-removed="' + str(removed).lower() + '" aria-label="' + E(label + ': ' + event.get('title', 'Calendar event')) +
            '" title="' + E('Restore this time in the local planner.' if removed else
                            'Hide this occurrence and free its time in the local planner. Google Calendar is unchanged.') +
            '">' + label + '</button>')


def plan_revision(plan):
    """Identify an immutable saved version without exposing its private file path."""
    if not isinstance(plan, dict):
        return None
    value = {key: value for key, value in plan.items() if key != 'warnings'}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def calendar_data(snapshot, read_only=False):
    """Use explicit starts/ends only; display times are never scheduling evidence."""
    snapshot = scheduling_snapshot(snapshot)
    timezone = ZoneInfo(snapshot['report']['timezone'])
    day = date.fromisoformat(snapshot['report']['date'])
    availability = snapshot.get('availability') or {}
    plan = suggest(snapshot) if not read_only else {'status': 'suggested' if availability.get('status') == 'complete' else 'unverified', 'suggestions': [], 'note': '', 'coverage': availability.get('coverage', 'Availability not collected.'), 'checked_at': availability.get('checked_at')}
    def minute(value):
        local = stamp(value, timezone)
        return ((local.date() - day).days * 1440 + local.hour * 60 + local.minute +
                local.second / 60 + local.microsecond / 60_000_000)
    def minute_end(value):
        return (datetime.combine(day, time.min, timezone) + timedelta(minutes=value)).isoformat()
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
        visible = visible_calendar_event(snapshot, event)
        try:
            end_at = stamp(event['end'], timezone).isoformat()
        except (KeyError, TypeError, ValueError):
            end_at = None
        fixed.append({'start': start, 'end': end, 'end_at': end_at,
                      'calendar_key': calendar_key(snapshot, event) if visible else None,
                      'label': str(event.get('title') or 'Calendar event') if visible else 'Busy',
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
    fixed.extend({'start': start, 'end': end, 'end_at': minute_end(end),
                  'label': 'Busy', 'free': False, 'anonymous': True}
                 for start, end in merged)
    blocks = [{'kind': kind, 'label': LABELS[kind], 'minutes': duration,
               'start': None,
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
                # Retain legacy longer focus lengths alongside configurable quarter-hour short blocks.
                if start < 0 or (kind == 'focus' and (duration < 15 or (duration < 120 and duration % 15))) or (kind != 'focus' and duration != GOALS[kind]) or start + duration > 1440:
                    raise ValueError('Saved plan has an invalid time or duration')
                seen.add(kind)
                name = focus_name(item.get('name', '')) if kind == 'focus' else ''
                submitted_blocks.append({'kind': kind, 'label': block_label(item), **({'name': name} if name else {}), 'start': start, 'minutes': duration,
                                         'calendar_key': calendar_key(snapshot, item, local=True),
                                         'end_at': minute_end(start + duration),
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
                block['minutes'] = selected['minutes']
                if selected.get('name'):
                    block['name'] = selected['name']
                block['label'] = selected['label']
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
    return {'start': lower, 'end': upper, 'view_start': lower if read_only else 510,
            'view_end': upper if read_only else 1020, 'now': now, 'read_only': read_only,
            'verified_start': verified_start, 'verified_end': verified_end, 'timezone': str(timezone), 'date': str(day),
            'verified': plan['status'] != 'unverified', 'fixed': sorted(fixed, key=lambda row: row['start']),
            'blocks': blocks, 'submitted_blocks': submitted_blocks, 'submitted_at': submitted_at,
            'submitted_error': submitted_error, 'note': plan['note'], 'coverage': plan['coverage'],
            'checked_at': plan.get('checked_at')}


def _clock(minutes):
    return f'{int(minutes) // 60:02}:{int(minutes) % 60:02}'


def removal_config(snapshot):
    """Only the live server may attach this local removal capability."""
    removal = snapshot.get('plan_removal') or {}
    if not isinstance(removal, dict):
        return None
    try:
        endpoint = urlsplit(removal.get('endpoint', ''))
        valid = (endpoint.scheme == 'http' and endpoint.hostname == '127.0.0.1' and endpoint.port and
                 endpoint.path == '/plan/remove' and not endpoint.query and not endpoint.fragment and
                 not endpoint.username and not endpoint.password and isinstance(removal.get('token'), str) and len(removal['token']) >= 32)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        return None
    data = calendar_data(snapshot, read_only=True)
    return dict(removal, date=data['date'], timezone=data['timezone'], revision=plan_revision(snapshot.get('submitted_plan')),
                blocks=[{key:block[key] for key in ('kind','start','minutes','name') if key in block} for block in data['submitted_blocks']])


def render_calendar(snapshot, read_only=False):
    data = calendar_data(snapshot, read_only=read_only)
    events = {calendar_key(snapshot, event): event for event in (snapshot.get('agenda') or {}).get('events', [])}
    removal = snapshot.get('plan_removal') or {}
    removal_ready = False
    if read_only and isinstance(removal, dict):
        try:
            endpoint = urlsplit(removal.get('endpoint', ''))
            removal_ready = (endpoint.scheme == 'http' and endpoint.hostname == '127.0.0.1' and endpoint.port and
                             endpoint.path == '/plan/remove' and not endpoint.query and not endpoint.fragment and
                             not endpoint.username and not endpoint.password and isinstance(removal.get('token'), str) and
                             len(removal['token']) >= 32)
        except (ValueError, TypeError):
            pass
    lower, upper = data['view_start'], data['view_end']
    span = upper - lower
    def position(start, end):
        start, end = max(lower, start), min(upper, end)
        return f'top:{(start-lower)/span*100:.4f}%;height:{max(0, end-start)/span*100:.4f}%'
    tick_points = [lower] + list(range((int(lower) // 60 + 1) * 60, int(upper), 60)) + [upper]
    ticks = ''.join('<div class="day-tick" style="top:' + str((point - lower) / span * 100) + '%"><span>' +
                    _clock(point) + '</span></div>' for point in tick_points)
    fixed = ''
    # Share the fixed lane when events overlap instead of hiding one another.
    groups, group, until = [], [], -1
    display_fixed = [item for item in data['fixed']
                     if item['start'] < min(upper, DISPLAY_END) and item['end'] > max(lower, DISPLAY_START)]
    for item in display_fixed:
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
    for item in display_fixed:
        classes = 'day-fixed' + (' day-short' if item['end'] - item['start'] < 45 else '') + (' day-free' if item['free'] else '') + (' day-anonymous' if item['anonymous'] else '')
        end_attr = ' data-calendar-end="' + E(item['end_at']) + '"' if item.get('end_at') else ''
        completion_attrs, completion_button = calendar_completion_ui(snapshot, item.get('calendar_key'), item['label'])
        skip_button = calendar_remove_button(snapshot, events.get(item.get('calendar_key'), {}))
        if completion_button: classes += ' day-completable'
        if skip_button: classes += ' day-skippable'
        fixed += '<div class="' + classes + '"' + end_attr + completion_attrs + ' style="' + position(item['start'], item['end']) + ';left:' + str(item['_column'] / item['_columns'] * 100) + '%;width:' + str(100 / item['_columns']) + '%" title="' + E(item['label'] + ' · ' + _clock(item['start']) + '–' + _clock(item['end'])) + '"><b>' + E(item['label']) + '</b><span>' + _clock(item['start']) + '–' + _clock(item['end']) + (' · free' if item['free'] else '') + '</span>' + completion_button + skip_button + '</div>'
    submitted_markup = ''
    if read_only:
        for item in data['submitted_blocks']:
            start, end = item['start'], item['start'] + item['minutes']
            classes = 'day-submitted-block' + (' day-short' if item['minutes'] < 45 else '') + (' day-submitted-conflict' if item['conflict'] else '')
            remove = ('<button type="button" class="day-remove-submitted" data-kind="' + item['kind'] + '" data-start="' + str(start) + '" data-minutes="' + str(item['minutes']) + '" aria-label="Cancel ' + E(item['label'] + ' at ' + _clock(start) + ' in your local plan') + '">Cancel</button>') if removal_ready else ''
            completion_attrs, completion_button = calendar_completion_ui(snapshot, item['calendar_key'], item['label'])
            if completion_button: classes += ' day-completable'
            submitted_markup += '<div class="' + classes + (' day-removable' if removal_ready else '') + '" data-local-plan-end="' + E(item['end_at']) + '"' + completion_attrs + ' data-kind="' + item['kind'] + '" style="' + position(start, end) + '" title="' + E(item['label'] + ' · ' + _clock(start) + '–' + _clock(end) + (' · overlaps calendar' if item['conflict'] else '')) + '"><b>' + E(item['label']) + '</b><span>' + _clock(start) + '–' + _clock(end) + '</span>' + completion_button + remove + '</div>'
    blocks, controls = '', '' 
    for block in data['blocks']:
        kind, start = block['kind'], block['start']
        clock = _clock(start) if start is not None else ''
        blocks += '<button type="button" id="day-block-' + kind + '" class="day-block' + (' day-short' if block['minutes'] < 45 else '') + '" data-kind="' + kind + '"' + (' style="' + position(start, start + block['minutes']) + '"' if start is not None and start < upper and start + block['minutes'] > lower else ' hidden') + ' aria-label="' + E(block['label'] + ', ' + str(block['minutes']) + ' minutes. Use arrow keys to move 15 minutes.') + '"><b>' + E(block['label']) + '</b><span>' + (clock + '–' + _clock(start + block['minutes']) if start is not None else '') + '</span></button>'
        duration_control = ('<label class="day-duration-label" for="day-duration-focus">Minutes</label><input id="day-duration-focus" data-duration type="number" min="15" max="' + str(max(15, int((block['max_end'] - block['min_start']) // 15) * 15)) + '" step="15" value="' + str(block['minutes']) + '" aria-label="Focus duration in minutes">') if kind == 'focus' else ''
        name_control = ('<label class="day-name-label" for="day-name-focus">Name (optional)</label><input id="day-name-focus" data-focus-name type="text" maxlength="' + str(FOCUS_NAME_MAX) + '" value="' + E(block.get('name', '')) + '" placeholder="Focus" aria-label="Focus block name (optional)">') if kind == 'focus' else ''
        selected = next((item for item in data['submitted_blocks'] if item['kind'] == kind), None)
        completion = ''
        if selected:
            attrs, toggle = calendar_completion_ui(snapshot, selected['calendar_key'], selected['label'])
            toggle = toggle.replace('<button type="button"', '<button type="button" id="day-completion-' + kind + '"', 1)
            completion = ('<span class="day-completion" data-calendar-saved-key="' + selected['calendar_key'] + '" data-calendar-saved-start="' + str(selected['start']) + '" data-calendar-saved-minutes="' + str(selected['minutes']) + '" data-calendar-saved-end="' + E(selected['end_at']) + '" data-local-plan-end="' + E(selected['end_at']) + '"' + attrs + '>' + toggle + '</span>')
        controls += '<div class="day-control" data-kind="' + kind + '"><label for="day-time-' + kind + '"><span data-block-label>' + E(block['label']) + '</span> <small data-duration-summary>' + str(block['minutes']) + 'm</small></label><input id="day-time-' + kind + '" type="text" inputmode="numeric" pattern="(?:[01][0-9]|2[0-3]):[0-5][0-9]" maxlength="5" placeholder="HH:MM" value="' + clock + '" aria-label="' + E(block['label'] + ' start time, HH:MM (24 hour)') + '">' + ('<div class="day-focus-options"><div class="day-option">' + duration_control + '</div><div class="day-option">' + name_control + '</div></div>' if kind == 'focus' else '') + '<button type="button" id="day-place-' + kind + '" data-place="' + kind + '"' + (' hidden' if start is not None else '') + '>Place</button><button type="button" id="day-unplace-' + kind + '" data-remove="' + kind + '"' + (' hidden' if start is None else '') + ' aria-label="Unplace ' + E(block['label']) + '">×</button>' + completion + '</div>'
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
    toolbar = '' if read_only else '<div class="day-toolbar"><button type="button" id="day-reset" class="day-reset">Reset</button><button type="button" id="day-cancel" class="day-cancel">Cancel editing</button></div>'
    instructions = ('Calendar events · read only. Remove a submitted local block if your plans changed.' if removal_ready else 'Calendar and submitted plan · read only.') if read_only else 'Choose blocks to place, drag or enter HH:MM (24 hour) · submit below to save. Skip a calendar event to free its time locally.'
    headings = '<span>Calendar</span>' + ('<span>Your submitted plan</span>' if read_only and data['submitted_at'] is not None else '')
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
    if read_only and removal_ready:
        config = dict(removal, date=data['date'], timezone=data['timezone'], revision=plan_revision(snapshot.get('submitted_plan')),
                      blocks=[{key: block[key] for key in ('kind', 'start', 'minutes', 'name') if key in block} for block in data['submitted_blocks']])
        payload = json.dumps(config, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        interactive = ('<p class="day-remove-status" role="status" aria-live="polite"></p>'
                       '<script type="application/json" class="day-plan-removal-data">' + payload + '</script>')
    elif read_only and data['submitted_blocks']:
        interactive = ('<details class="day-plan-removal-setup"><summary>Enable local plan removal</summary>'
                       '<p>Open a live Tea session to remove submitted blocks from your local plan.</p></details>')
    return ('<section id="focus-exercise" class="day-calendar' + view_class + '" aria-labelledby="day-calendar-title"' + (' hidden' if not read_only and data['submitted_at'] is not None else '') + '>'
            '<div class="section-head"><h2 id="day-calendar-title">' + title + '</h2>' + toolbar + '</div>'
            '<p class="day-calendar-note">' + instructions + '</p>'
            '<p class="day-calendar-meta">' + E(data['timezone'] + ' · ' + scope + checked) + '</p>'
            + ('<p class="day-plan-status">' + E(submitted_note) + '</p>' if read_only else '<p class="day-plan-status">' + E(data['note']) + '</p>') +
            '<div class="day-column-head">' + headings + '</div>'
            '<div class="day-scroll" data-scroll-start="' + str(lower) + '" data-scroll-end="' + str(upper) + '" data-scroll-minute="' + str(max(lower, min(data['now'] - 60, upper - 240))) + '" tabindex="0" aria-label="Calendar ' + _clock(lower) + ' to ' + _clock(upper) + '">'
            '<div class="day-board" style="--day-hours:' + str(span / 60) + '">' + ticks +
            '<div class="day-fixed-lane">' + fixed + '</div>' + ('<div class="day-submitted-lane">' + submitted_markup + '</div>' if read_only and data['submitted_at'] is not None else '' if read_only else '<div class="day-plan-lane">' + blocks + '</div>') + '</div></div>'
            + interactive + '</section>')
