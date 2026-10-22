"""Local retrospectives preserve choices atomically without creating invented history."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from calendar_state import calendar_key, load_calendar_state, save_calendar_state
from local_history import export_history
from todo_state import TodoError, load_todos, save_todo_action


def at(hour=12, day=22):
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


def calendar_snapshot():
    return {'report': {'date': '2026-10-22', 'timezone': 'America/Toronto'},
            'agenda': {'events': [{'id': 'calendar/event', 'title': 'A meeting',
                                  'description': 'Do not retain private provider descriptions',
                                  'start': '2026-10-22T13:00:00Z'}]},
            'submitted_plan': {'blocks': [{'kind': 'focus', 'start': 540, 'minutes': 45, 'name': 'Named focus'}]}}


class LocalHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def read_todos(self):
        return json.loads((self.root / 'todos/state.json').read_text())

    def add(self, title='A task', tags=None, hour=12):
        return save_todo_action(self.root, {'action': 'add', 'title': title,
                                          'project_tags': tags or []}, now=at(hour))['item']

    def test_clear_restore_clear_and_undo_keep_prior_events_after_archive_disappears(self):
        task = self.add(tags=['Transport'])
        save_todo_action(self.root, {'action': 'complete', 'id': task['id']}, now=at(13))
        cleared = save_todo_action(self.root, {'action': 'clear', 'ids': [task['id']], 'status': 'completed'}, now=at(14))
        save_todo_action(self.root, {'action': 'restore', 'id': task['id']}, now=at(15))
        second = save_todo_action(self.root, {'action': 'remove', 'id': task['id']}, now=at(16))
        save_todo_action(self.root, {'action': 'undo', 'id': second['batch_id']}, now=at(17))
        state = self.read_todos()
        self.assertEqual(state['version'], 2, 'Older writers must refuse to erase history')
        self.assertEqual(state['archive'], [])
        self.assertEqual([event['action'] for event in state['history']], ['add', 'complete', 'clear', 'restore', 'remove', 'undo'])
        self.assertEqual(state['history'][2]['batch_id'], cleared['batch_id'])
        self.assertEqual(state['history'][2]['tasks'][0]['project_tags'], ['Transport'])
        self.assertNotIn('history', load_todos(self.root, with_warnings=True))

    def test_noops_keep_original_timestamp_bytes_and_completion_time(self):
        task = self.add()
        save_todo_action(self.root, {'action': 'complete', 'id': task['id']}, now=at(13))
        path = self.root / 'todos/state.json'
        before = path.read_bytes()
        for request in ({'action': 'complete', 'id': task['id']},
                        {'action': 'edit', 'id': task['id'], 'title': task['title'], 'base_title': task['title']},
                        {'action': 'set_importance', 'id': task['id'], 'important': False},
                        {'action': 'set_project_tags', 'id': task['id'], 'project_tags': []}):
            save_todo_action(self.root, request, now=at(14))
            self.assertEqual(path.read_bytes(), before)
        save_todo_action(self.root, {'action': 'edit', 'id': task['id'], 'title': 'Renamed', 'base_title': task['title']}, now=at(15))
        state = self.read_todos()
        self.assertEqual(state['history'][1]['at'], at(13).isoformat())
        self.assertEqual(state['items'][0]['updated_at'], at(15).isoformat())
        self.assertEqual(state['history'][2]['previous_title'], task['title'])

    def test_concurrent_saves_and_failed_writes_keep_state_and_history_together(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            tasks = list(pool.map(lambda i: self.add('Task ' + str(i)), range(20)))
        self.assertEqual(len(self.read_todos()['history']), 20)
        path = self.root / 'todos/state.json'
        before = path.read_bytes()
        with patch('todo_state.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                save_todo_action(self.root, {'action': 'complete', 'id': tasks[0]['id']}, now=at(13))
        self.assertEqual(path.read_bytes(), before)
        state = self.read_todos()
        state['history'][0]['at'] = 'unknown'
        path.write_text(json.dumps(state))
        before = path.read_bytes()
        with self.assertRaises(TodoError):
            self.add('Do not overwrite corrupt history')
        self.assertEqual(path.read_bytes(), before)

    def test_calendar_marks_keep_metadata_toggle_times_and_legacy_choices(self):
        snapshot = calendar_snapshot()
        source_key = calendar_key(snapshot, snapshot['agenda']['events'][0])
        local_key = calendar_key(snapshot, snapshot['submitted_plan']['blocks'][0], local=True)
        save_calendar_state(self.root, snapshot, {'key': source_key, 'done': True}, now=at(12))
        path = next((self.root / 'workspace').glob('calendar-*.json'))
        before = path.read_bytes()
        save_calendar_state(self.root, snapshot, {'key': source_key, 'done': True}, now=at(13))
        self.assertEqual(path.read_bytes(), before)
        save_calendar_state(self.root, snapshot, {'key': source_key, 'done': False}, now=at(14))
        save_calendar_state(self.root, snapshot, {'key': local_key, 'done': True}, now=at(15))
        record = json.loads(path.read_text())
        self.assertEqual(record['version'], 2)
        self.assertEqual([event['done'] for event in record['history']], [True, False, True])
        self.assertEqual(record['history'][1]['previous_done'], True)
        self.assertEqual(record['history'][2]['item']['name'], 'Named focus')
        self.assertNotIn('description', json.dumps(record))
        self.assertEqual(load_calendar_state(self.root, snapshot), {source_key: False, local_key: True})
        # Upgrading a legacy file must preserve a mark with an unknown action date.
        record.pop('history')
        record['version'] = 1
        path.write_text(json.dumps(record))
        save_calendar_state(self.root, snapshot, {'key': local_key, 'done': False}, now=at(16))
        upgraded = json.loads(path.read_text())
        self.assertEqual(upgraded['state'][source_key], False)
        self.assertEqual(len(upgraded['history']), 1)
        self.assertEqual(upgraded['history'][0]['at'], at(16).isoformat())
        before = path.read_bytes()
        with patch('workspace_state.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                save_calendar_state(self.root, snapshot, {'key': source_key, 'done': True}, now=at(17))
        self.assertEqual(path.read_bytes(), before)

    def test_read_only_export_filters_actual_action_dates_and_projects(self):
        tagged = self.add(tags=['Transport'])
        self.add('Other', ['Unrelated'])
        save_todo_action(self.root, {'action': 'complete', 'id': tagged['id']}, now=at(1, day=23))
        before = {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in self.root.rglob('*') if path.is_file()}
        result = export_history(self.root, '2026-10-22', '2026-10-22', 'America/Toronto', 'transport')
        self.assertEqual([event['action'] for event in result['events']], ['add', 'complete'])
        self.assertEqual(result['counts'], {'todo:add': 1, 'todo:complete': 1})
        self.assertEqual(result['events'][-1]['at'], at(1, day=23).isoformat())
        self.assertEqual(before, {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in self.root.rglob('*') if path.is_file()})
        missing = self.root / 'missing'
        self.assertEqual(export_history(missing)['events'], [])
        self.assertFalse(missing.exists())
        with self.assertRaises(ValueError):
            export_history(self.root, '2026-10-23', '2026-10-22')

    def test_legacy_facts_and_immutable_plans_do_not_invent_completion_actions(self):
        task = self.add()
        save_todo_action(self.root, {'action': 'complete', 'id': task['id']}, now=at(13))
        state = self.read_todos()
        state.pop('history')
        state['version'] = 1
        (self.root / 'todos/state.json').write_text(json.dumps(state))
        folder = self.root / 'America__Toronto/2026-10-22/submitted-plans'
        folder.mkdir(parents=True)
        for n, blocks in enumerate(([{'kind': 'focus', 'start': 540, 'minutes': 45, 'name': 'Focus name'}], [])):
            record = {'version': 1, 'date': '2026-10-22', 'timezone': 'America/Toronto',
                      'kind': 'submitted-local-plan', 'submitted_at': at(14+n).isoformat(), 'blocks': blocks}
            if n:
                record['removed_block'] = {'kind': 'focus', 'start': 540, 'minutes': 45, 'name': 'Focus name'}
            (folder / (str(n) + '.json')).write_text(json.dumps(record))
        result = export_history(self.root, '2026-10-22', '2026-10-22')
        self.assertEqual([event['action'] for event in result['events']], ['submit', 'remove'])
        self.assertEqual(result['facts'][0]['task']['status'], 'completed')
        self.assertIsNone(result['facts'][0]['action_at'])
        self.assertNotIn('todo:complete', result['counts'])
        self.assertEqual(result['events'][0]['blocks'][0]['name'], 'Focus name')
        (folder / 'broken.json').write_text('{')
        self.assertEqual(len(export_history(self.root)['warnings']), 1)
        result = subprocess.run([sys.executable, str(SKILL / 'scripts/local_history.py'), '--root', str(self.root),
                                 '--from', '2026-10-22', '--to', '2026-10-22', '--project', 'Transport'],
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout)['events'], [])


if __name__ == '__main__':
    unittest.main()
