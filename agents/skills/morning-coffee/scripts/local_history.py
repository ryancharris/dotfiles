"""Read-only JSON lookbacks over local actions and immutable chosen-plan revisions."""
import argparse
from collections import Counter
from datetime import date, datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo


def instant(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('History timestamps require a timezone.')
    return parsed


def task_summary(item):
    """Keep personal task metadata, excluding legacy fields and unrelated payloads."""
    result = {key: item.get(key, [] if key == 'project_tags' else None)
              for key in ('id', 'title', 'status', 'parent_id', 'important', 'project_tags')}
    if 'task_date' in item:
        result['task_date'] = item['task_date']
    if 'position' in item:
        result['position'] = item['position']
    return result


def validate_events(events, domain):
    if not isinstance(events, list):
        raise ValueError('Invalid local action history.')
    seen = set()
    for event in events:
        if (not isinstance(event, dict) or not isinstance(event.get('id'), str) or
                not re.fullmatch('[a-f0-9]{32}', event['id']) or event['id'] in seen):
            raise ValueError('Invalid local action history identity.')
        seen.add(event['id'])
        instant(event['at'])
        if domain == 'todo':
            if event.get('action') not in ('add', 'edit', 'set_importance', 'set_project_tags',
                                         'complete', 'cancel', 'reopen', 'clear', 'remove', 'restore', 'undo', 'move'):
                raise ValueError('Invalid task history action.')
            if event['action'] == 'move':
                move = event.get('move')
                valid_id = lambda value: isinstance(value, str) and re.fullmatch('[a-f0-9]{32}', value)
                if (not isinstance(move, dict) or set(move) != {'target_id', 'placement', 'previous_parent_id', 'parent_id'} or
                        move['placement'] not in ('before', 'after', 'inside', 'root-end') or
                        (move['target_id'] is not None if move['placement'] == 'root-end' else not valid_id(move['target_id'])) or
                        (move['placement'] == 'inside' and move['parent_id'] != move['target_id']) or
                        (move['placement'] == 'root-end' and move['parent_id'] is not None) or
                        any(value is not None and not valid_id(value) for value in (move['previous_parent_id'], move['parent_id']))):
                    raise ValueError('Invalid task move history.')
            if not isinstance(event.get('tasks'), list) or not event['tasks']:
                raise ValueError('Invalid task history metadata.')
            for task in event['tasks']:
                if (not isinstance(task, dict) or not isinstance(task.get('id'), str) or
                        not re.fullmatch('[a-f0-9]{32}', task['id']) or
                        not isinstance(task.get('title'), str) or
                        not isinstance(task.get('project_tags'), list) or
                        any(not isinstance(tag, str) for tag in task['project_tags'])):
                    raise ValueError('Invalid task history metadata.')
                if 'position' in task and (type(task['position']) is not int or task['position'] < 0):
                    raise ValueError('Invalid task history position.')
        elif (event.get('action') not in ('set_done', 'set_removed') or
              type(event.get('done' if event['action'] == 'set_done' else 'removed')) is not bool or
              not isinstance(event.get('key'), str) or not re.fullmatch('[a-f0-9]{64}', event['key']) or
              not isinstance(event.get('item'), dict) or event['item'].get('source') not in ('local', 'calendar')):
            raise ValueError('Invalid calendar history metadata.')
    return events


def export_history(root, from_date=None, to_date=None, timezone_name='America/Toronto', project=None):
    """Do not acquire store locks or create files; atomic store replacement makes reads safe.

    This is a best-effort read across stores, not a cross-store transactional snapshot.
    Date filtering uses action instants in the requested timezone. Facts without an
    action timestamp remain separate, and are never counted as recorded actions.
    """
    zone = ZoneInfo(timezone_name)
    for value in (from_date, to_date):
        if value is not None and date.fromisoformat(value).isoformat() != value:
            raise ValueError('Dates must use YYYY-MM-DD.')
    if from_date and to_date and from_date > to_date:
        raise ValueError('--from must be on or before --to.')
    root = Path(root)
    events, facts, warnings = [], [], []

    def in_range(stamp):
        day = instant(stamp).astimezone(zone).date().isoformat()
        return (not from_date or from_date <= day) and (not to_date or day <= to_date)

    def matching(task):
        return project is None or project.casefold() in [tag.casefold() for tag in task.get('project_tags', [])]

    todo_path = root / 'todos' / 'state.json'
    if todo_path.exists():
        try:
            from todo_state import _read
            state = _read(todo_path.parent)
            for event in state['history']:
                tasks = [task for task in event['tasks'] if matching(task)]
                if tasks and in_range(event['at']):
                    events.append(dict(event, domain='todo', tasks=tasks, provenance='recorded-action'))
            # Current facts have unknown action dates. Expose separately even when
            # filtering dates, so a lookback never fabricates historical completion.
            for item in state['items']:
                if matching(item):
                    facts.append(dict(domain='todo', provenance='current-state', task=task_summary(item),
                                      updated_at=item['updated_at'], action_at=None))
            for batch in state['archive']:
                for item in batch['items']:
                    if matching(item) and in_range(batch['cleared_at']):
                        facts.append(dict(domain='todo', provenance='retained-archive', task=task_summary(item),
                                          batch_id=batch['id'], cleared_at=batch['cleared_at'], action_at=None))
        except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
            warnings.append('Task history unavailable: ' + str(exc))
    for path in sorted((root / 'workspace').glob('calendar-*.json')):
        try:
            from calendar_state import _read_record
            scope = json.loads(path.read_text())
            record = _read_record(path.parent, scope['date'], scope['timezone'])
            if project is not None:
                continue
            for event in record['history']:
                if in_range(event['at']):
                    events.append(dict(event, domain='calendar', date=record['date'], timezone=record['timezone'],
                                       provenance='recorded-action'))
            if (not from_date or from_date <= record['date']) and (not to_date or record['date'] <= to_date):
                for key, done in record['state'].items():
                    facts.append(dict(domain='calendar', provenance='current-state', date=record['date'],
                                      timezone=record['timezone'], key=key, done=done, action_at=None))
        except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
            warnings.append('Calendar history unavailable in ' + path.name + ': ' + str(exc))
    if project is None:
        for path in sorted(root.glob('*/*/submitted-plans/*.json')):
            try:
                from plan_submission import _blocks
                record = json.loads(path.read_text())
                if record.get('version') != 1 or record.get('kind') != 'submitted-local-plan':
                    raise ValueError('Invalid plan metadata.')
                date.fromisoformat(record['date'])
                ZoneInfo(record['timezone'])
                blocks = _blocks(record['blocks'])
                if in_range(record['submitted_at']):
                    event = dict(domain='plan', provenance='immutable-submission', at=record['submitted_at'],
                                 date=record['date'], timezone=record['timezone'], revision=path.name,
                                 action='remove' if 'removed_block' in record else 'submit', blocks=blocks)
                    if 'removed_block' in record:
                        event['removed_block'] = _blocks([record['removed_block']])[0]
                    events.append(event)
            except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
                warnings.append('Plan history unavailable in ' + path.name + ': ' + str(exc))
    events.sort(key=lambda event: instant(event['at']))
    return {'version': 1, 'timezone': timezone_name, 'from': from_date, 'to': to_date, 'project': project,
            'events': events, 'counts': dict(sorted(Counter(event['domain'] + ':' + event['action'] for event in events).items())),
            'facts': facts, 'warnings': warnings,
            'limitations': ['Action history starts when recording was introduced; earlier transitions and completion times are unknown.',
                            'Current facts are not dated actions. Retained archive timestamps record clearing, not completion.',
                            'Plan submissions record intent. Calendar marks record explicit choices; elapsed styling is not completion evidence.',
                            'Project filtering applies to task tags at the action time and excludes untagged plan/calendar history.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--from', dest='from_date')
    parser.add_argument('--to', dest='to_date')
    parser.add_argument('--timezone', default='America/Toronto')
    parser.add_argument('--project')
    args = parser.parse_args()
    from report_history import resolve_root
    try:
        result = export_history(resolve_root(args.root), args.from_date, args.to_date, args.timezone, args.project)
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
