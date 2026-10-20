"""Daily brief history, conservative reconciliation and rendering. Standard library only."""
import argparse
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4
from zoneinfo import ZoneInfo

from render_brief import render
from plan_day import suggest
from plan_submission import latest_plan
from time_format import clock_label
from review_state import load_review_state
from todo_state import load_todos

KINDS = ('morning-coffee', 'tea-time', 'refresh')
SOURCES = ('github', 'calendar', 'drive', 'incidentio', 'notion', 'slack')
SECTIONS = {
    'priorities': ('github', 'incidentio', 'slack', 'notion'),
    'agenda': ('calendar',), 'okr': ('drive',), 'oncall': ('incidentio',),
    'rfcs': ('notion',), 'reviews': ('github',), 'yesterday': ('github', 'slack', 'notion'),
}
LISTS = {'agenda': 'events', 'rfcs': 'items', 'reviews': 'items', 'yesterday': 'items'}
LABELS = {'priorities': 'Daily priorities', 'agenda': 'Today', 'okr': 'Quarterly planning',
          'oncall': 'On call & incidents', 'rfcs': 'RFCs to review',
          'reviews': 'Reviews waiting', 'yesterday': 'Yesterday'}
FIELD_LABELS = {'reviewDecision': 'Review decision', 'mergeStateStatus': 'Merge status',
                'ci': 'Checks', 'effort': 'Review effort', 'changedFiles': 'Changed files',
                'commitCount': 'Commits', 'additions': 'Lines added', 'deletions': 'Lines removed',
                'user_approved': 'Approved by you', 'approval_status': 'Approval status',
                'next_action': 'Next action', 'done': 'Completion checkpoint',
                'join_url': 'Call link', 'counts': 'Incident counts'}


def resolve_root(override=None, environ=None):
    """Choose a retention directory without writing user configuration."""
    env = os.environ if environ is None else environ
    if override is not None:
        return Path(override).expanduser()
    if env.get('ENGINEERING_BRIEFS_DIR'):
        configured = env['ENGINEERING_BRIEFS_DIR']
    else:
        config = Path(env.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')) / 'engineering-briefs/config.json'
        if config.exists():
            data = json.loads(config.read_text())
            if not isinstance(data, dict) or not isinstance(data.get('report_dir'), str) or not data['report_dir'].strip():
                raise ValueError(f'{config}: report_dir must be a nonempty absolute path or ~/path')
            configured = data['report_dir']
        else:
            return Path.home() / 'daily-briefs'
    root = Path(configured).expanduser()
    if not root.is_absolute():
        raise ValueError('Configured report directory must be an absolute path or ~/path')
    return root


def instant(value):
    if not isinstance(value, str):
        raise ValueError('Collection timestamp must be an ISO 8601 string')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Collection timestamps must include a timezone')
    return parsed


def day_dir(root, date, timezone):
    datetime.strptime(date, '%Y-%m-%d')
    ZoneInfo(timezone)
    return Path(root) / timezone.replace('/', '__') / date


def history(root, date, timezone):
    entries, warnings = [], []
    folder = day_dir(root, date, timezone)
    for file in sorted(folder.glob('*/snapshot.json')):
        try:
            data = json.loads(file.read_text())
            meta = data['history']
            if meta['kind'] not in KINDS:
                raise ValueError('Unknown report kind')
            if data['report']['date'] != date or data['report']['timezone'] != timezone:
                raise ValueError('Mismatched local day or timezone')
            instant(meta['created_at'])
            if not file.with_name('report.html').is_file():
                raise ValueError('Missing HTML companion')
            # Validate the data we will compare; valid JSON alone is insufficient.
            render(data)
            entries.append((data, file))
        except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
            warnings.append(f'Ignored unreadable history {file.parent.name}: {exc}')
    entries.sort(key=lambda entry: (instant(entry[0]['history']['created_at']), str(entry[1])))
    return entries, warnings


def prepare(root, date, timezone, kind):
    if kind not in KINDS:
        raise ValueError('Unknown report kind')
    entries, warnings = history(root, date, timezone)
    saved = latest_plan(root, date, timezone, with_warnings=True)
    warnings.extend(saved['warnings'])
    local_todos = load_todos(root, with_warnings=True)
    warnings.extend(local_todos['warnings'])
    morning = next((entry for entry in reversed(entries) if entry[0]['history']['kind'] == 'morning-coffee'), None)
    tea = next((entry for entry in reversed(entries) if entry[0]['history']['kind'] == 'tea-time'), None)
    refresh = next((entry for entry in reversed(entries) if entry[0]['history']['kind'] == 'refresh'), None)
    previous = entries[-1] if entries and morning else None
    return {'directory': str(day_dir(root, date, timezone)), 'route': 'morning-coffee' if kind == 'morning-coffee' or morning is None else kind,
            'morning': str(morning[1]) if morning else None,
            'tea': str(tea[1]) if tea else None,
            'refresh': str(refresh[1]) if refresh else None,
            'submitted_plan': saved['plan']['path'] if saved['plan'] else None,
            'todos': local_todos['todos'],
            'todo_archive': local_todos['todo_archive'],
            'previous': str(previous[1]) if previous else None, 'warnings': warnings}


def items(snapshot, section):
    data = snapshot.get(section)
    if section == 'priorities':
        return (data or []) + snapshot.get('unverified_priorities', [])
    if section in LISTS:
        return (data or {}).get(LISTS[section], [])
    return [data] if data else []


def identity(item, section):
    # Event IDs must be calendar-qualified; URL handles legacy snapshots.
    return str((item.get('url') if section in ('reviews', 'rfcs') else None) or item.get('id') or item.get('url') or (section if section in ('okr', 'oncall') else item.get('title', '')))


def meaningful(item, section):
    fields = {
        'priorities': ('title', 'context', 'action', 'done', 'status'),
        'agenda': ('title', 'time', 'start', 'end', 'free', 'tentative', 'join_url'),
        'okr': ('label', 'url', 'period'),
        'oncall': ('state', 'responder', 'shift', 'counts'),
        'rfcs': ('title', 'user_approved', 'approval_status', 'summary', 'next_action'),
        'reviews': ('title', 'queue', 'teams', 'readiness', 'reviewDecision', 'mergeStateStatus',
                    'ci', 'effort', 'changedFiles', 'commitCount', 'additions', 'deletions', 'summary'),
        'yesterday': ('title', 'content'),
    }
    return {key: item.get(key) for key in fields[section]}


def brief(item, section):
    if section == 'reviews':
        ci = item.get('ci', {})
        return f"{item.get('mergeStateStatus', 'unknown')}; {item.get('reviewDecision') or 'review unknown'}; CI {ci.get('passing', '?')}/{ci.get('total', '?')}, {ci.get('failing', '?')} failing"
    if section == 'agenda':
        return item.get('time', 'Time unavailable') + (' · tentative' if item.get('tentative') else '') + (' · free' if item.get('free') else '')
    if section == 'oncall':
        counts = ', '.join(f'{value} {key}' for key, value in item.get('counts', {}).items())
        return f"{item.get('state', 'Unknown')} · {item.get('shift', '')} · {counts}"
    return format_value(item.get('action') or item.get('next_action') or item.get('label') or item.get('content') or '')


def format_value(value):
    if value is None:
        return 'Unavailable'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, dict):
        return '; '.join(f'{key.replace("_", " ")}: {format_value(part)}' for key, part in value.items())
    if isinstance(value, list):
        return ', '.join(format_value(part) for part in value) or 'None'
    return str(value) or 'None'


def event_window(item, timezone):
    if not item.get('start'):
        return clock_label(item.get('time', 'Time unavailable'))
    def local(value):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
        return parsed.astimezone(ZoneInfo(timezone)).strftime('%b %d, %H:%M %Z')
    if item.get('all_day'):
        return 'All day · ' + item['start'][:10]
    try:
        return local(item['start']) + (' to ' + local(item['end']) if item.get('end') else '')
    except ValueError:
        return clock_label(item.get('time', 'Time unavailable'))


def resolved(record):
    return bool(record and record.get('verified') is True and record.get('url') and
                record.get('outcome') in ('merged', 'closed', 'approved', 'cancelled', 'completed', 'resolved'))


def complete(snapshot, section):
    return all(snapshot.get('sources', {}).get(source, {}).get('status') == 'complete' for source in SECTIONS[section])


def reconcile(current, previous):
    result = deepcopy(current)
    stale = []
    stale_evidence = {}
    resolutions = {(r['section'], str(r['id'])): r for r in current.get('resolutions', [])}
    for section in SECTIONS:
        if complete(current, section):
            continue
        old = items(previous, section)
        if not old:
            continue
        observed_at = previous.get('stale_evidence', {}).get(section, previous['collected_at'])
        retained_times = []
        if section in LISTS or section == 'priorities':
            rows = items(result, section)
            known = {identity(row, section) for row in rows}
            for row in old:
                key = identity(row, section)
                if key not in known and not resolved(resolutions.get((section, key))):
                    retained = deepcopy(row)
                    retained['_retained_at'] = row.get('_retained_at', previous['collected_at'])
                    retained_times.append(retained['_retained_at'])
                    rows.append(retained)
            if section == 'priorities':
                result[section] = rows[:4]
                result['unverified_priorities'] = rows[4:]
            else:
                result[section][LISTS[section]] = rows
        else:
            # Only explicitly verified singleton fields replace earlier facts.
            retained = deepcopy(previous.get(section))
            for field in current.get('refreshed_fields', {}).get(section, []):
                if field in (current.get(section) or {}):
                    retained[field] = deepcopy(current[section][field])
            result[section] = retained
            if set(meaningful(retained, section)) - set(current.get('refreshed_fields', {}).get(section, [])):
                retained_times.append(observed_at)
        if retained_times:
            stale.append(LABELS[section])
            stale_evidence[section] = min(retained_times, key=instant)
    def updated_key(row):
        try:
            return instant(row.get('updatedAt')).timestamp()
        except (ValueError, TypeError):
            return float('inf')
    result['reviews']['items'].sort(key=updated_key)
    result['agenda']['events'].sort(key=lambda row: (not row.get('all_day', False), row.get('start') or row.get('time', '')))
    result['stale_sections'] = stale
    result['stale_evidence'] = stale_evidence
    if stale:
        result['coverage'] = (result.get('coverage', '') + ' Previous facts retained where refresh is incomplete: ' + ', '.join(stale) + '.').strip()
    return result


def changes(current, previous):
    result = []
    resolutions = {(r['section'], str(r['id'])): r for r in current.get('resolutions', [])}
    for section in SECTIONS:
        before = {identity(row, section): row for row in items(previous, section)}
        after = {identity(row, section): row for row in items(current, section)}
        old_ranks = {key: rank for rank, key in enumerate(before, 1)}
        new_ranks = {key: rank for rank, key in enumerate(after, 1)}
        for key in dict.fromkeys([*after, *before]):
            old, new = before.get(key), after.get(key)
            resolution = resolutions.get((section, key))
            rank_changed = section == 'priorities' and old is not None and new is not None and old_ranks[key] != new_ranks[key]
            if old == new and not rank_changed:
                continue
            if new is None:
                status = 'Resolved' if resolved(resolution) else 'No longer listed' if complete(current, section) else 'Unverified'
            elif old is None:
                status = 'New'
            elif meaningful(old, section) != meaningful(new, section) or rank_changed:
                status = 'Updated'
            else:
                continue
            item = new or old
            fields = []
            if old is not None and new is not None:
                old_values, new_values = meaningful(old, section), meaningful(new, section)
                fields = [{'label': FIELD_LABELS.get(key, key.replace('_', ' ').title()), 'before': format_value(old_values[key]), 'after': format_value(new_values[key])}
                          for key in old_values if old_values[key] != new_values[key]]
                if section == 'agenda' and any(old_values[key] != new_values[key] for key in ('time', 'start', 'end')):
                    fields = [field for field in fields if field['label'] not in ('Time', 'Start', 'End')]
                    fields.insert(0, {'label': 'Time', 'before': event_window(old, current['report']['timezone']),
                                      'after': event_window(new, current['report']['timezone'])})
                if rank_changed:
                    fields.insert(0, {'label': 'Priority rank', 'before': str(old_ranks[key]), 'after': str(new_ranks[key])})
            result.append({'section': LABELS[section], 'status': status, 'fields': fields,
                           'id': key,
                           'importance': 0 if section == 'priorities' else 1 if section == 'oncall' else 2 if section == 'agenda'
                           else 3 if status == 'Resolved' else 4 if new and (new.get('readiness', {}).get('status') == 'READY' or new.get('reviewDecision') == 'APPROVED')
                           else 9 if section == 'reviews' and old and new and 'UNKNOWN' in (old.get('mergeStateStatus'), new.get('mergeStateStatus')) else 5,
                           'title': item.get('title') or item.get('label') or LABELS[section],
                           'url': resolution.get('url', '') if resolution else item.get('url', ''), 'before': brief(old, section) if old else '',
                           'after': brief(new, section) if new else resolution.get('detail', '') if resolution else 'Absent from current queue; completion not established.'})
    return result


def planning_changes(current, previous):
    old, new = previous.get('day_plan'), current.get('day_plan')
    if not old or not new or (old['status'], old['suggestions']) == (new['status'], new['suggestions']):
        return []
    def summary(plan):
        timezone = ZoneInfo(current['report']['timezone'])
        slots = []
        for slot in plan['suggestions']:
            start = instant(slot['start']).astimezone(timezone).strftime('%H:%M')
            end = instant(slot['end']).astimezone(timezone).strftime('%H:%M %Z')
            slots.append(slot['kind'].replace('_', ' ').title() + ' ' + start + '–' + end)
        return '; '.join(slots) if slots else plan['note']
    return [{'section': 'Focus & exercise', 'status': 'Unverified' if new['status']=='unverified' else 'Updated',
             'title': 'A little room to move & focus', 'url': '#focus-exercise', 'importance': 2,
             'before': summary(old), 'after': summary(new), 'fields': []}]


def publish(root, snapshot, kind):
    now = instant(snapshot['collected_at'])
    timezone = snapshot['report']['timezone']
    date = snapshot['report']['date']
    if now.astimezone(ZoneInfo(timezone)).date().isoformat() != date:
        raise ValueError('collected_at does not belong to the report local day')
    for source in SOURCES:
        info = snapshot.get('sources', {}).get(source)
        if not info or info.get('status') not in ('complete', 'partial', 'unavailable'):
            raise ValueError(f'Missing source coverage: {source}')
        instant(info['checked_at'])
    plan = prepare(root, date, timezone, kind)
    actual = plan['route']
    result = deepcopy(snapshot)
    # Local save capabilities belong only to their ephemeral interactive session.
    result.pop('calendar_confirmation', None)
    result.pop('plan_submission', None)
    result.pop('plan_removal', None)
    result.pop('review_interaction', None)
    result.pop('todo_interaction', None)
    result.pop('workspace', None)
    result.pop('workspace_interaction', None)
    result.pop('todos', None)
    result.pop('review_state', None)
    result.pop('submitted_plan', None)
    saved = latest_plan(root, date, timezone, with_warnings=True)
    submitted = saved['plan']
    plan['warnings'] = list(dict.fromkeys(plan['warnings'] + saved['warnings']))
    if submitted:
        result['submitted_plan'] = submitted
    result['day_plan'] = suggest(result)
    if actual in ('tea-time', 'refresh'):
        morning = json.loads(Path(plan['morning']).read_text())
        previous = json.loads(Path(plan['previous']).read_text())
        if now <= instant(previous['history']['created_at']):
            raise ValueError('Refresh must be newer than its previous brief')
        earlier_resolutions = {(record['section'], str(record['id'])): deepcopy(record) for record in previous.get('resolutions', [])}
        for record in result.get('resolutions', []):
            record = deepcopy(record)
            if record.get('verified') is True:
                record.setdefault('verified_at', result['collected_at'])
            earlier_resolutions[(record['section'], str(record['id']))] = record
        result['resolutions'] = [record for (section, key), record in earlier_resolutions.items()
                                 if key not in {identity(row, section) for row in items(result, section)}]
        result = reconcile(result, previous)
        result['updates'] = {'since': previous['history']['created_at'],
                             'previous_kind': previous['history']['kind'],
                             'morning_at': morning['history']['created_at'],
                             'items': changes(result, previous),
                             'since_morning': changes(result, morning),
                             'plan_changed': (result.get('submitted_plan') or {}).get('blocks') !=
                                             (previous.get('submitted_plan') or {}).get('blocks')}
    # Personal review marks are root-wide local metadata, independent of source
    # facts and dates. Always reload; input/earlier snapshots are historical views.
    try:
        local_reviews = load_review_state(root, with_warnings=True)
        result['review_state'] = local_reviews['state']
        plan['warnings'].extend(local_reviews['warnings'])
    except (ValueError, OSError) as exc:
        result['review_state'] = {}
        plan['warnings'].append('Local review marks unavailable: ' + str(exc))
    local_todos = load_todos(root, with_warnings=True)
    result['todos'] = local_todos['todos']
    result['todo_archive'] = local_todos['todo_archive']
    plan['warnings'].extend(local_todos['warnings'])
    result['history'] = {'kind': actual, 'created_at': snapshot['collected_at'],
                         'morning': plan['morning'], 'previous': plan['previous'],
                         'tea': plan['tea'], 'refresh': plan['refresh'], 'warnings': plan['warnings']}
    report = result['report']
    report.update(title='Tea Time' if actual == 'tea-time' else 'Morning Coffee',
                  page_title=('Tea Time' if actual == 'tea-time' else 'Morning Coffee') + ' · ' + date,
                  time=now.astimezone(ZoneInfo(timezone)).strftime('%H:%M'),
                  eyebrow=('Fresh steep · Updated' if actual == 'tea-time' else 'Morning Coffee · Updated' if actual == 'refresh' else 'Freshly brewed · Daily engineering brief'))
    if kind in ('tea-time', 'refresh') and actual == 'morning-coffee':
        report['preview_label'] = (report.get('preview_label', '') + ' · Morning Coffee created — no morning brief existed today.').lstrip(' ·')
    folder = day_dir(root, date, timezone)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = actual + '-' + now.strftime('%H%M%S%f') + '-' + uuid4().hex[:8]
    # Publish the pair only after rendering succeeds; orphan temp dirs are ignored.
    with tempfile.TemporaryDirectory(prefix='.pending-', dir=folder) as temporary:
        stage = Path(temporary) / name
        stage.mkdir()
        stage.chmod(0o700)
        (stage / 'snapshot.json').write_text(json.dumps(result, indent=2) + '\n')
        (stage / 'report.html').write_text(render(result))
        (stage / 'snapshot.json').chmod(0o600)
        (stage / 'report.html').chmod(0o600)
        stage.rename(folder / name)
    return {'kind': actual, 'snapshot': str(folder / name / 'snapshot.json'),
            'html': str(folder / name / 'report.html'), 'warnings': plan['warnings']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, help='Retention directory; overrides ENGINEERING_BRIEFS_DIR and config.json')
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--date', required=True)
    prep.add_argument('--timezone', required=True)
    prep.add_argument('--kind', choices=KINDS, required=True)
    save = sub.add_parser('publish')
    save.add_argument('snapshot', type=Path)
    save.add_argument('--kind', choices=KINDS, required=True)
    args = parser.parse_args()
    root = resolve_root(args.root)
    if args.command == 'prepare':
        result = prepare(root, args.date, args.timezone, args.kind)
    else:
        result = publish(root, json.loads(args.snapshot.read_text()), args.kind)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
