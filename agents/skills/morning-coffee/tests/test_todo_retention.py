"""Calendar boundaries and bounded archive retention through the durable store."""
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from todo_state import TodoError, StaleTodoError, load_todos, save_todo_action
from local_history import export_history


class TodoRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.zone = 'America/Toronto'

    def at(self, value):
        return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo(self.zone))

    def save(self, request, when='2026-10-27T16:00:00'):
        return save_todo_action(self.root, request, now=self.at(when), timezone_name=self.zone)

    def load(self, when):
        return load_todos(self.root, True, now=self.at(when), timezone_name=self.zone)

    def test_new_root_and_subtask_use_save_day_in_workspace_timezone(self):
        # The UTC date differs from the workspace date at this instant.
        instant = datetime.fromisoformat('2026-10-28T02:00:00+00:00')
        parent = save_todo_action(self.root, {'action': 'add', 'title': 'Today'},
                                  now=instant, timezone_name=self.zone)['item']
        child = save_todo_action(self.root, {'action': 'add', 'title': 'Child', 'parent_id': parent['id']},
                                 now=instant, timezone_name=self.zone)['item']
        self.assertEqual(parent['task_date'], '2026-10-27')
        self.assertEqual(child['task_date'], '2026-10-27')
        after_midnight = self.save({'action': 'add', 'title': 'Next day'}, '2026-10-28T00:00:00')['item']
        self.assertEqual(after_midnight['task_date'], '2026-10-28')
        # An older parent date never becomes a new subtask's default.
        next_child = self.save({'action': 'add', 'title': 'New child', 'parent_id': parent['id']},
                               '2026-10-28T09:00:00')['item']
        self.assertEqual(next_child['task_date'], '2026-10-28')

    def test_midnight_archives_closed_parent_promotes_open_child_and_preserves_date(self):
        parent = self.save({'action': 'add', 'title': 'Parent', 'task_date': '2026-10-28'})['item']
        child = self.save({'action': 'add', 'title': 'Open child', 'parent_id': parent['id']})['item']
        self.save({'action': 'complete', 'id': parent['id']})
        self.save({'action': 'edit', 'id': parent['id'], 'title': 'Edited', 'base_title': 'Parent'}, '2026-10-27T23:59:00')
        self.assertEqual(len(self.load('2026-10-27T23:59:59')['todos']), 2)
        result = self.load('2026-10-28T00:00:00')
        self.assertEqual([item['id'] for item in result['todos']], [child['id']])
        self.assertIsNone(result['todos'][0]['parent_id'])
        self.assertEqual(result['todo_archive'][0]['task_date'], '2026-10-28')
        self.assertEqual(result['todo_archive'][0]['title'], 'Edited')
        path = self.root / 'todos/state.json'
        before = path.read_bytes()
        self.load('2026-10-28T01:00:00')
        self.assertEqual(before, path.read_bytes())
        restored = self.save({'action': 'restore', 'id': parent['id']}, '2026-10-28T01:00:00')
        self.assertEqual(next(item for item in restored['todos'] if item['id'] == child['id'])['parent_id'], parent['id'])
        self.assertEqual(len(self.load('2026-10-28T23:59:59')['todos']), 2)
        self.assertEqual(len(self.load('2026-10-29T00:00:00')['todo_archive']), 1)

    def test_seven_elapsed_days_including_dst_and_long_offline_gap(self):
        task = self.save({'action': 'add', 'title': 'Finished'})['item']
        self.save({'action': 'cancel', 'id': task['id']}, '2026-10-31T22:00:00')
        # Toronto falls back on Nov 1: seven elapsed days end at 23:00 on Nov 7.
        self.assertEqual(len(self.load('2026-11-07T22:59:59')['todo_archive']), 1)
        self.assertEqual(self.load('2026-11-07T23:00:00')['todo_archive'], [])
        another = self.save({'action': 'add', 'title': 'Another'}, '2026-11-08T12:00:00')['item']
        self.save({'action': 'complete', 'id': another['id']}, '2026-11-08T12:00:00')
        result = self.load('2026-12-01T12:00:00')
        self.assertEqual(result['todos'], [])
        self.assertEqual(result['todo_archive'], [])
        self.assertTrue(export_history(self.root)['events'])

    def test_date_validation_clear_and_concurrent_edit(self):
        task = self.save({'action': 'add', 'title': 'Work', 'task_date': '2028-02-29'})['item']
        request = {'action': 'edit', 'id': task['id'], 'title': 'Work', 'base_title': 'Work',
                   'task_date': '2026-10-29', 'base_task_date': '2028-02-29'}
        self.save(request)
        with self.assertRaises(StaleTodoError):
            self.save(dict(request, task_date=None))
        self.save(dict(request, task_date=None, base_task_date='2026-10-29'))
        self.assertIsNone(self.load('2026-10-27T17:00:00')['todos'][0]['task_date'])
        before = (self.root / 'todos/state.json').read_bytes()
        for value in ('2026-02-29', '2026-1-01', 'tomorrow', 7, []):
            with self.subTest(value=value), self.assertRaises(TodoError):
                self.save({'action': 'add', 'title': 'Bad date', 'task_date': value})
        self.assertEqual((self.root / 'todos/state.json').read_bytes(), before)

    def test_legacy_closed_task_and_manual_archive_expire_without_touching_open_work(self):
        task = self.save({'action': 'add', 'title': 'Legacy'})['item']
        self.save({'action': 'complete', 'id': task['id']})
        path = self.root / 'todos/state.json'
        data = json.loads(path.read_text())
        data['items'][0].pop('closed_at')
        path.write_text(json.dumps(data))
        open_task = self.save({'action': 'add', 'title': 'Open'})['item']
        self.save({'action': 'remove', 'id': open_task['id']})
        self.assertEqual(len(self.load('2026-10-28T00:00:00')['todo_archive']), 2)
        self.assertEqual(len(self.load('2026-11-03T16:00:00')['todo_archive']), 1)
        self.assertEqual(self.load('2026-11-04T00:00:00')['todo_archive'], [])

    def test_expired_legacy_parent_never_backdates_a_child_closed_today(self):
        parent = self.save({'action': 'add', 'title': 'Old parent'}, '2026-10-18T12:00:00')['item']
        self.save({'action': 'complete', 'id': parent['id']}, '2026-10-18T12:00:00')
        # Simulate a pre-upgrade legacy tree without closure timestamps.
        path = self.root / 'todos/state.json'
        data = json.loads(path.read_text())
        child = dict(parent, id='c' * 32, parent_id=parent['id'], title='Closed today',
                     status='completed', created_at='2026-10-18T12:00:00-04:00',
                     updated_at='2026-10-27T12:00:00-04:00')
        data['items'][0].pop('closed_at')
        data['items'].append(child)
        path.write_text(json.dumps(data))
        for _ in range(3):
            result = self.load('2026-10-27T16:00:00')
            self.assertEqual([item['id'] for item in result['todos']], [child['id']])
            self.assertEqual(result['todo_archive'], [])
        result = self.load('2026-10-28T00:00:00')
        self.assertEqual(result['todos'], [])
        self.assertEqual([item['id'] for item in result['todo_archive']], [child['id']])

    def test_timezone_and_atomic_failure_preserve_previous_store(self):
        task = self.save({'action': 'add', 'title': 'Closed'})['item']
        self.save({'action': 'complete', 'id': task['id']})
        # 02:00 UTC is still the same day in Toronto.
        self.assertEqual(len(load_todos(self.root, now=datetime.fromisoformat('2026-10-28T02:00:00+00:00'))), 1)
        path = self.root / 'todos/state.json'
        before = path.read_bytes()
        with patch('todo_state.os.replace', side_effect=OSError('disk full')):
            result = self.load('2026-10-28T01:00:00')
        self.assertTrue(result['warnings'])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(self.load('2026-10-28T01:00:00')['todo_archive']), 1)


if __name__ == '__main__':
    unittest.main()
