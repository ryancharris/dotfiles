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
from todo_state import TodoError, load_todos, ordered_todos, save_todo_action, todo_summary


class TodoStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def add(self, title='Review transport plan', due_date=None):
        request = {'action': 'add', 'title': title}
        if due_date is not None:
            request['due_date'] = due_date  # Older open reports can still add tasks.
        return save_todo_action(self.root, request)['item']

    def test_lifecycle_is_shared_across_briefs_days_and_reloads(self):
        item = self.add()
        self.assertEqual(load_todos(self.root), [item])
        complete = save_todo_action(self.root, {'action': 'complete', 'id': item['id']})
        self.assertEqual(complete['item']['status'], 'completed')
        cancelled = save_todo_action(self.root, {'action': 'cancel', 'id': item['id']})
        self.assertEqual(cancelled['item']['status'], 'cancelled')
        reopened = save_todo_action(self.root, {'action': 'reopen', 'id': item['id']})
        self.assertEqual(reopened['item']['status'], 'pending')
        self.assertNotIn('due_date', reopened['item'])
        self.assertEqual(reopened['item']['created_at'], item['created_at'])
        save_todo_action(self.root, {'action': 'complete', 'id': item['id']})
        reopened = save_todo_action(self.root, {'action': 'reopen', 'id': item['id']})
        self.assertEqual(reopened['item']['status'], 'pending')
        summary = todo_summary({'report': {'date': '2026-10-23'}, 'todos': load_todos(self.root)})
        self.assertEqual(summary['pending'][0]['id'], item['id'])
        removed = save_todo_action(self.root, {'action': 'remove', 'id': item['id']})
        self.assertEqual(removed['item']['status'], 'removed')
        self.assertEqual(removed['todos'], [])
        self.assertEqual(load_todos(self.root), [])
        self.assertEqual(json.loads((self.root / 'todos' / 'state.json').read_text())['items'], [])
        with self.assertRaises(TodoError):
            save_todo_action(self.root, {'action': 'reopen', 'id': item['id']})

    def test_status_summary_keeps_all_open_work_across_dates(self):
        old = self.add('Overdue', '2026-10-19')
        today = self.add('Due today')
        future = self.add('Future', '2026-10-21')
        done = self.add('Completed overdue', '2026-10-18')
        cancelled = self.add('Cancelled today')
        save_todo_action(self.root, {'action': 'complete', 'id': done['id']})
        save_todo_action(self.root, {'action': 'cancel', 'id': cancelled['id']})
        result = todo_summary({'report': {'date': '2026-10-20', 'timezone': 'America/Toronto'}, 'todos': load_todos(self.root)})
        self.assertEqual({entry['id'] for entry in result['pending']}, {old['id'], today['id'], future['id']})
        self.assertEqual([entry['id'] for entry in result['completed']], [done['id']])
        self.assertEqual([entry['id'] for entry in result['cancelled']], [cancelled['id']])
        tomorrow = todo_summary({'report': {'date': '2027-01-01'}, 'todos': load_todos(self.root)})
        self.assertEqual(tomorrow, result)
        self.assertEqual(len(load_todos(self.root)), 5)

    def test_clear_tab_deletes_only_selected_items_and_promotes_other_statuses(self):
        parent = self.add('Keep completed parent')
        save_todo_action(self.root, {'action': 'complete', 'id': parent['id']})
        first = save_todo_action(self.root, {'action': 'add', 'title': 'Clear open child', 'parent_id': parent['id']})['item']
        second = save_todo_action(self.root, {'action': 'add', 'title': 'Clear open grandchild', 'parent_id': first['id']})['item']
        survivor = save_todo_action(self.root, {'action': 'add', 'title': 'Keep cancelled descendant', 'parent_id': second['id']})['item']
        save_todo_action(self.root, {'action': 'cancel', 'id': survivor['id']})
        unseen = self.add('Added by another session after the view was loaded')
        result = save_todo_action(self.root, {'action': 'clear', 'status': 'pending', 'ids': [first['id'], second['id']]})
        self.assertEqual(result['removed_ids'], [first['id'], second['id']])
        saved = {item['id']: item for item in load_todos(self.root)}
        self.assertEqual(set(saved), {parent['id'], survivor['id'], unseen['id']})
        self.assertEqual(saved[survivor['id']]['parent_id'], parent['id'])
        self.assertEqual(saved[survivor['id']]['status'], 'cancelled')
        raw = json.loads((self.root / 'todos' / 'state.json').read_text())['items']
        self.assertEqual({item['id'] for item in raw}, set(saved))
        save_todo_action(self.root, {'action': 'clear', 'status': 'all', 'ids': list(saved)})
        self.assertEqual(load_todos(self.root), [])
        self.assertEqual(json.loads((self.root / 'todos' / 'state.json').read_text())['items'], [])

    def test_archive_and_undo_persist_status_importance_and_nested_relationships(self):
        parent = self.add('Parent')
        child = save_todo_action(self.root, {'action': 'add', 'title': 'Child', 'parent_id': parent['id'], 'important': True})['item']
        grandchild = save_todo_action(self.root, {'action': 'add', 'title': 'Keep completed child', 'parent_id': child['id']})['item']
        save_todo_action(self.root, {'action': 'complete', 'id': grandchild['id']})
        cleared = save_todo_action(self.root, {'action': 'clear', 'status': 'pending', 'ids': [parent['id'], child['id']]})
        reloaded = load_todos(self.root, with_warnings=True)
        self.assertEqual({entry['id'] for entry in reloaded['todo_archive']}, {parent['id'], child['id']})
        self.assertIsNone(reloaded['todos'][0]['parent_id'])
        unrelated = self.add('Another session added this')
        restored = save_todo_action(self.root, {'action': 'undo', 'id': cleared['batch_id']})
        saved = {entry['id']: entry for entry in restored['todos']}
        self.assertEqual(saved[child['id']]['parent_id'], parent['id'])
        self.assertTrue(saved[child['id']]['important'])
        self.assertEqual(saved[grandchild['id']]['parent_id'], child['id'])
        self.assertEqual(saved[grandchild['id']]['status'], 'completed')
        self.assertIn(unrelated['id'], saved)
        self.assertEqual(restored['archive'], [])
        with self.assertRaises(TodoError):
            save_todo_action(self.root, {'action': 'undo', 'id': cleared['batch_id']})

    def test_restore_individual_child_before_parent_and_preserve_subsequent_edits(self):
        parent = self.add('Parent')
        child = save_todo_action(self.root, {'action': 'add', 'title': 'Child', 'parent_id': parent['id']})['item']
        save_todo_action(self.root, {'action': 'clear', 'status': 'all', 'ids': [parent['id'], child['id']]})
        restored = save_todo_action(self.root, {'action': 'restore', 'id': child['id']})
        self.assertIsNone(restored['todos'][0]['parent_id'])
        restored = save_todo_action(self.root, {'action': 'restore', 'id': parent['id']})
        self.assertEqual(next(entry for entry in restored['todos'] if entry['id'] == child['id'])['parent_id'], parent['id'])
        clear = save_todo_action(self.root, {'action': 'remove', 'id': parent['id']})
        save_todo_action(self.root, {'action': 'complete', 'id': child['id']})
        restored = save_todo_action(self.root, {'action': 'undo', 'id': clear['batch_id']})
        saved_child = next(entry for entry in restored['todos'] if entry['id'] == child['id'])
        self.assertIsNone(saved_child['parent_id'])  # Do not overwrite a later edit.
        self.assertEqual(saved_child['status'], 'completed')

    def test_archive_restore_is_atomic_and_corrupt_archive_preserves_store(self):
        item = self.add()
        cleared = save_todo_action(self.root, {'action': 'remove', 'id': item['id']})
        self.assertEqual(cleared['archive'][0]['status'], 'pending')
        path = self.root / 'todos' / 'state.json'
        before = path.read_bytes()
        with patch('todo_state.os.replace', side_effect=OSError('Disk full')):
            with self.assertRaises(OSError):
                save_todo_action(self.root, {'action': 'restore', 'id': item['id']})
        self.assertEqual(path.read_bytes(), before)
        raw = json.loads(before)
        raw['archive'][0]['items'].append(dict(raw['archive'][0]['items'][0]))
        path.write_text(json.dumps(raw))
        broken = path.read_bytes()
        with self.assertRaises(TodoError):
            save_todo_action(self.root, {'action': 'add', 'title': 'Do not overwrite corrupt archive'})
        self.assertEqual(path.read_bytes(), broken)
        self.assertTrue(load_todos(self.root, with_warnings=True)['warnings'])

    def test_clear_rejects_stale_or_invalid_selection_without_partial_deletion(self):
        first, second = self.add('First'), self.add('Second')
        save_todo_action(self.root, {'action': 'complete', 'id': second['id']})
        path = self.root / 'todos' / 'state.json'
        before = path.read_bytes()
        requests = [
            {'action': 'clear', 'status': 'pending', 'ids': [first['id'], second['id']]},
            {'action': 'clear', 'status': 'all', 'ids': [first['id'], 'a' * 32]},
            {'action': 'clear', 'status': 'all', 'ids': []},
            {'action': 'clear', 'status': 'all', 'ids': [first['id'], first['id']]},
            {'action': 'clear', 'status': 'invalid', 'ids': [first['id']]},
            {'action': 'clear', 'status': 'all', 'ids': [None]},
        ]
        for request in requests:
            with self.subTest(request=request), self.assertRaises(TodoError):
                save_todo_action(self.root, request)
            self.assertEqual(path.read_bytes(), before)
        with patch('todo_state.os.replace', side_effect=OSError('Disk write failed')):
            with self.assertRaises(OSError):
                save_todo_action(self.root, {'action': 'clear', 'status': 'pending', 'ids': [first['id']]})
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_requests_preserve_existing_store(self):
        item = self.add()
        path = self.root / 'todos' / 'state.json'
        before = path.read_bytes()
        requests = [None, {}, {'action': []}, {'action': 'remove', 'id': '../state'},
                    {'action': 'add', 'title': ' ', 'due_date': '2026-10-20'},
                    {'action': 'add', 'title': 'x' * 501, 'due_date': '2026-10-20'},
                    {'action': 'reschedule', 'id': item['id'], 'due_date': '20/10/2026'},
                    {'action': 'complete', 'id': item['id'], 'provider': 'github'},
                    {'action': 'set_importance', 'id': item['id'], 'important': 1},
                    {'action': 'set_importance', 'id': item['id'], 'important': 'true'},
                    {'action': 'set_importance', 'id': item['id'], 'important': None},
                    {'action': 'add', 'title': 'Task', 'due_date': '2026-10-20', 'important': 'yes'},
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

    def test_titles_are_normalized_and_legacy_add_dates_are_ignored(self):
        result = save_todo_action(self.root, {'action': 'add', 'title': '  Review\n  RFC\t ', 'due_date': '2028-02-29'},
                                  now=datetime(2026, 10, 20, 12, tzinfo=timezone.utc))
        self.assertEqual(result['item']['title'], 'Review RFC')
        self.assertNotIn('due_date', result['item'])
        data = json.loads((self.root / 'todos' / 'state.json').read_text())
        self.assertEqual(data['items'][0]['updated_at'], '2026-10-20T12:00:00+00:00')

    def test_legacy_due_fields_are_preserved_but_never_filter_or_order_tasks(self):
        first, second = self.add('First open task'), self.add('Second open task')
        path = self.root / 'todos' / 'state.json'
        legacy = json.loads(path.read_text())
        legacy['items'][0]['due_date'] = '2099-12-31'
        legacy['items'][1]['due_date'] = '2000-01-01'
        path.write_text(json.dumps(legacy))
        before = path.read_bytes()
        loaded = load_todos(self.root)
        self.assertEqual([item['id'] for item in loaded], [first['id'], second['id']])
        self.assertEqual(len(todo_summary({'todos': loaded})['pending']), 2)
        self.assertEqual(path.read_bytes(), before)
        save_todo_action(self.root, {'action': 'complete', 'id': first['id']})
        stored = json.loads(path.read_text())['items']
        self.assertEqual([item['due_date'] for item in stored], ['2099-12-31', '2000-01-01'])

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

    def test_importance_persists_independently_through_lifecycle_and_legacy_load(self):
        first = self.add('Ordinary task', '2026-10-19')
        important = save_todo_action(self.root, {'action': 'add', 'title': 'Important task', 'due_date': '2026-10-22', 'important': True})['item']
        self.assertEqual([item['id'] for item in load_todos(self.root)], [important['id'], first['id']])
        save_todo_action(self.root, {'action': 'complete', 'id': important['id']})
        save_todo_action(self.root, {'action': 'reopen', 'id': important['id']})
        loaded = {item['id']: item for item in load_todos(self.root)}
        self.assertTrue(loaded[important['id']]['important'])
        self.assertEqual(loaded[important['id']]['status'], 'pending')
        self.assertNotIn('due_date', loaded[important['id']])
        unstar = save_todo_action(self.root, {'action': 'set_importance', 'id': important['id'], 'important': False})
        self.assertFalse(unstar['item']['important'])
        self.assertEqual(unstar['item']['status'], 'pending')
        self.assertEqual([item['id'] for item in unstar['todos']], [first['id'], important['id']])
        path = self.root / 'todos' / 'state.json'
        legacy = json.loads(path.read_text())
        for item in legacy['items']:
            item.pop('important')
        path.write_text(json.dumps(legacy))
        self.assertTrue(all(item['important'] is False for item in load_todos(self.root)))
        save_todo_action(self.root, {'action': 'set_importance', 'id': first['id'], 'important': True})
        self.assertTrue(all(type(item['important']) is bool for item in json.loads(path.read_text())['items']))

    def test_important_descendants_promote_groups_without_starring_ancestors(self):
        ordinary = self.add('Ordinary root', '2026-10-18')
        parent = self.add('Parent root', '2026-10-25')
        sibling = save_todo_action(self.root, {'action': 'add', 'title': 'Earlier child', 'due_date': '2026-10-19', 'parent_id': parent['id']})['item']
        child = save_todo_action(self.root, {'action': 'add', 'title': 'Later child', 'due_date': '2026-10-24', 'parent_id': parent['id']})['item']
        nested = save_todo_action(self.root, {'action': 'add', 'title': 'Important descendant', 'due_date': '2026-10-20', 'parent_id': child['id'], 'important': True})['item']
        loaded = load_todos(self.root)
        self.assertEqual([item['id'] for item in loaded], [parent['id'], child['id'], nested['id'], sibling['id'], ordinary['id']])
        self.assertTrue(next(item for item in loaded if item['id'] == nested['id'])['important'])
        self.assertFalse(next(item for item in loaded if item['id'] == parent['id'])['important'])
        self.assertFalse(next(item for item in loaded if item['id'] == child['id'])['important'])
        # A starred task outside a selected view does not reorder the matching queue.
        filtered_order = ordered_todos(loaded, matching_ids={ordinary['id'], sibling['id']})
        self.assertEqual([item['id'] for item in filtered_order], [ordinary['id'], parent['id'], sibling['id'], child['id'], nested['id']])
        save_todo_action(self.root, {'action': 'remove', 'id': child['id']})
        promoted = next(item for item in load_todos(self.root) if item['id'] == nested['id'])
        self.assertEqual(promoted['parent_id'], parent['id'])
        self.assertTrue(promoted['important'])


if __name__ == '__main__':
    unittest.main()
