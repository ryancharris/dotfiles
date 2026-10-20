"""Explicit local task lifecycle, durable storage and concurrent updates."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from todo_state import TodoError, load_todos, save_todo_action, todo_summary


class TodoStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def add(self, title='Review transport plan', due_date='2026-10-20'):
        return save_todo_action(self.root, {'action': 'add', 'title': title, 'due_date': due_date})['item']

    def test_lifecycle_is_shared_across_briefs_days_and_reloads(self):
        item = self.add()
        self.assertEqual(load_todos(self.root), [item])
        complete = save_todo_action(self.root, {'action': 'complete', 'id': item['id']})
        self.assertEqual(complete['item']['status'], 'completed')
        cancelled = save_todo_action(self.root, {'action': 'cancel', 'id': item['id']})
        self.assertEqual(cancelled['item']['status'], 'cancelled')
        rescheduled = save_todo_action(self.root, {'action': 'reschedule', 'id': item['id'], 'due_date': '2026-10-22'})
        self.assertEqual(rescheduled['item']['status'], 'pending')
        self.assertEqual(rescheduled['item']['due_date'], '2026-10-22')
        self.assertEqual(rescheduled['item']['created_at'], item['created_at'])
        save_todo_action(self.root, {'action': 'complete', 'id': item['id']})
        reopened = save_todo_action(self.root, {'action': 'reopen', 'id': item['id']})
        self.assertEqual(reopened['item']['status'], 'pending')
        summary = todo_summary({'report': {'date': '2026-10-23'}, 'todos': load_todos(self.root)})
        self.assertEqual(summary['overdue'][0]['id'], item['id'])
        removed = save_todo_action(self.root, {'action': 'remove', 'id': item['id']})
        self.assertEqual(removed['item']['status'], 'removed')
        self.assertEqual(removed['todos'], [])
        self.assertEqual(load_todos(self.root), [])
        with self.assertRaises(TodoError):
            save_todo_action(self.root, {'action': 'reopen', 'id': item['id']})

    def test_only_pending_work_counts_as_due_and_overdue(self):
        old = self.add('Overdue', '2026-10-19')
        today = self.add('Due today')
        future = self.add('Future', '2026-10-21')
        done = self.add('Completed overdue', '2026-10-18')
        cancelled = self.add('Cancelled today')
        save_todo_action(self.root, {'action': 'complete', 'id': done['id']})
        save_todo_action(self.root, {'action': 'cancel', 'id': cancelled['id']})
        result = todo_summary({'report': {'date': '2026-10-20', 'timezone': 'America/Toronto'}, 'todos': load_todos(self.root)})
        self.assertEqual([entry['id'] for entry in result['overdue']], [old['id']])
        self.assertEqual([entry['id'] for entry in result['due_today']], [today['id']])
        self.assertEqual([entry['id'] for entry in result['upcoming']], [future['id']])
        self.assertEqual(len(load_todos(self.root)), 5)

    def test_invalid_requests_preserve_existing_store(self):
        item = self.add()
        path = self.root / 'todos' / 'state.json'
        before = path.read_bytes()
        requests = [None, {}, {'action': []}, {'action': 'remove', 'id': '../state'},
                    {'action': 'add', 'title': ' ', 'due_date': '2026-10-20'},
                    {'action': 'add', 'title': 'x' * 501, 'due_date': '2026-10-20'},
                    {'action': 'add', 'title': 'Title', 'due_date': '2026-02-30'},
                    {'action': 'reschedule', 'id': item['id'], 'due_date': '20/10/2026'},
                    {'action': 'complete', 'id': item['id'], 'provider': 'github'},
                    {'action': 'complete', 'id': 'a' * 32}]
        for request in requests:
            with self.subTest(request=request):
                with self.assertRaises(TodoError):
                    save_todo_action(self.root, request)
                self.assertEqual(path.read_bytes(), before)

    def test_concurrent_actions_do_not_lose_other_items(self):
        def add(index):
            return self.add('Task ' + str(index))
        with ThreadPoolExecutor(max_workers=8) as pool:
            added = list(pool.map(add, range(24)))
        self.assertEqual(len(load_todos(self.root)), 24)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda item: save_todo_action(self.root, {'action': 'complete', 'id': item['id']}), added))
        saved = load_todos(self.root)
        self.assertEqual({item['id'] for item in saved}, {item['id'] for item in added})
        self.assertTrue(all(item['status'] == 'completed' for item in saved))

    def test_store_is_private_and_corruption_is_disclosed_not_overwritten(self):
        self.assertEqual(load_todos(self.root), [])
        self.assertFalse((self.root / 'todos').exists())
        self.add()
        folder = self.root / 'todos'
        self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
        for name in ('state.json', '.lock'):
            self.assertEqual((folder / name).stat().st_mode & 0o777, 0o600)
        path = folder / 'state.json'
        path.write_text('{broken')
        result = load_todos(self.root, with_warnings=True)
        self.assertEqual(result['todos'], [])
        self.assertTrue(result['warnings'])
        with self.assertRaises(TodoError):
            self.add('Preserve corrupted file')
        self.assertEqual(path.read_text(), '{broken')

    def test_titles_are_normalized_and_dates_are_calendar_dates(self):
        result = save_todo_action(self.root, {'action': 'add', 'title': '  Review\n  RFC\t ', 'due_date': '2028-02-29'},
                                  now=datetime(2026, 10, 20, 12, tzinfo=timezone.utc))
        self.assertEqual(result['item']['title'], 'Review RFC')
        self.assertEqual(result['item']['due_date'], '2028-02-29')
        data = json.loads((self.root / 'todos' / 'state.json').read_text())
        self.assertEqual(data['items'][0]['updated_at'], '2026-10-20T12:00:00+00:00')

    def test_subtasks_keep_independent_state_and_promote_on_parent_removal(self):
        parent = self.add('Parent', '2026-10-23')
        first = save_todo_action(self.root, {'action': 'add', 'title': 'First child', 'due_date': '2026-10-20', 'parent_id': parent['id']})['item']
        second = save_todo_action(self.root, {'action': 'add', 'title': 'Second child', 'due_date': '2026-10-21', 'parent_id': parent['id']})['item']
        nested = save_todo_action(self.root, {'action': 'add', 'title': 'Nested child', 'due_date': '2026-10-19', 'parent_id': first['id']})['item']
        save_todo_action(self.root, {'action': 'complete', 'id': parent['id']})
        loaded = {item['id']: item for item in load_todos(self.root)}
        self.assertEqual(loaded[parent['id']]['status'], 'completed')
        self.assertTrue(all(loaded[item['id']]['status'] == 'pending' for item in (first, second, nested)))
        save_todo_action(self.root, {'action': 'cancel', 'id': first['id']})
        self.assertEqual(next(item for item in load_todos(self.root) if item['id'] == nested['id'])['status'], 'pending')
        save_todo_action(self.root, {'action': 'remove', 'id': first['id']})
        loaded = {item['id']: item for item in load_todos(self.root)}
        self.assertEqual(loaded[nested['id']]['parent_id'], parent['id'])
        self.assertEqual(loaded[nested['id']]['status'], 'pending')
        self.assertEqual(loaded[second['id']]['parent_id'], parent['id'])
        save_todo_action(self.root, {'action': 'remove', 'id': parent['id']})
        loaded = load_todos(self.root)
        self.assertEqual({item['id'] for item in loaded}, {second['id'], nested['id']})
        self.assertTrue(all(item['parent_id'] is None and item['status'] == 'pending' for item in loaded))
        with self.assertRaises(TodoError):
            save_todo_action(self.root, {'action': 'add', 'title': 'Orphan', 'due_date': '2026-10-20', 'parent_id': parent['id']})

    def test_old_flat_store_migrates_and_invalid_parent_cycles_are_preserved(self):
        first, second = self.add('First'), self.add('Second')
        path = self.root / 'todos' / 'state.json'
        flat = json.loads(path.read_text())
        for item in flat['items']:
            item.pop('parent_id')
        path.write_text(json.dumps(flat))
        self.assertTrue(all(item['parent_id'] is None for item in load_todos(self.root)))
        cyclic = json.loads(path.read_text())
        cyclic['items'][0]['parent_id'] = second['id']
        cyclic['items'][1]['parent_id'] = first['id']
        path.write_text(json.dumps(cyclic))
        before = path.read_bytes()
        self.assertTrue(load_todos(self.root, with_warnings=True)['warnings'])
        with self.assertRaises(TodoError):
            self.add('Preserve cycle')
        self.assertEqual(path.read_bytes(), before)

    def test_failed_atomic_write_keeps_previous_tasks_and_cleans_temporary_file(self):
        item = self.add()
        path = self.root / 'todos' / 'state.json'
        before = path.read_bytes()
        with patch('todo_state.os.replace', side_effect=OSError('Disk write failed')):
            with self.assertRaises(OSError):
                save_todo_action(self.root, {'action': 'complete', 'id': item['id']})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(load_todos(self.root), [item])
        self.assertFalse(list(path.parent.glob('*.tmp')))


if __name__ == '__main__':
    unittest.main()
