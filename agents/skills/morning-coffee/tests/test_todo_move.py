"""Task moves preserve subtrees, manual order and atomic history."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from local_history import export_history
from todo_state import StaleTodoError, TodoError, load_todos, save_todo_action


class TodoMoveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sequence = 0

    def add(self, title, parent=None, important=False):
        self.sequence += 1
        return save_todo_action(self.root, {'action': 'add', 'title': title, 'parent_id': parent,
                                          'important': important, 'project_tags': ['Transport']},
                                now=datetime(2026, 10, 22, 12, tzinfo=timezone.utc)+timedelta(seconds=self.sequence),
                                task_id=f'{self.sequence:032x}')['item']

    def state(self):
        return json.loads((self.root / 'todos/state.json').read_text())

    def request(self, item, target=None, placement='root-end'):
        return {'action': 'move', 'id': item['id'], 'target_id': target['id'] if target else None,
                'placement': placement, 'base_order': [[entry['id'], entry['parent_id']] for entry in load_todos(self.root)]}

    def move(self, item, target=None, placement='root-end'):
        return save_todo_action(self.root, self.request(item, target, placement))

    def titles(self):
        return [entry['title'] for entry in load_todos(self.root)]

    def test_cross_day_root_move_is_rejected_but_nesting_and_same_day_move_work(self):
        earlier = self.add('Earlier')
        later = save_todo_action(self.root, {'action': 'add', 'title': 'Later', 'task_date': '2026-10-23'},
                                 now=datetime(2026, 10, 22, 12, tzinfo=timezone.utc))['item']
        same_day = self.add('Same day')
        path = self.root / 'todos/state.json'
        before = path.read_bytes()
        for placement in ('before', 'after'):
            with self.subTest(placement=placement), self.assertRaisesRegex(TodoError, 'same day'):
                self.move(earlier, later, placement)
            self.assertEqual(path.read_bytes(), before)
        self.move(earlier, same_day, 'after')
        self.assertEqual(self.titles(), ['Later', 'Same day', 'Earlier'])
        self.move(later, earlier, 'inside')
        self.assertEqual(next(item for item in load_todos(self.root) if item['id'] == later['id'])['parent_id'], earlier['id'])
        self.move(later)
        self.assertIsNone(next(item for item in load_todos(self.root) if item['id'] == later['id'])['parent_id'])

    def test_undated_tasks_move_with_today_using_workspace_timezone(self):
        dated = self.add('Dated today')
        undated = self.add('Undated')
        path = self.root / 'todos/state.json'
        stored = json.loads(path.read_text())
        next(item for item in stored['items'] if item['id'] == undated['id']).pop('task_date')
        path.write_text(json.dumps(stored))
        # October 23 UTC is still October 22 in Toronto.
        now = datetime(2026, 10, 23, 2, tzinfo=timezone.utc)
        result = save_todo_action(self.root, self.request(undated, dated, 'before'), now=now,
                                  timezone_name='America/Toronto')
        self.assertEqual([item['id'] for item in result['todos']], [undated['id'], dated['id']])
        self.assertNotIn('task_date', result['item'])
        # The same task becomes part of the new day after local midnight.
        with self.assertRaisesRegex(TodoError, 'same day'):
            save_todo_action(self.root, self.request(undated, dated, 'after'),
                             now=datetime(2026, 10, 23, 5, tzinfo=timezone.utc),
                             timezone_name='America/Toronto')

    def test_reorder_moves_whole_subtree_and_history_preserves_metadata(self):
        a = self.add('A')
        child = self.add('Child', a['id'])
        grandchild = self.add('Grandchild', child['id'])
        b = self.add('B')
        c = self.add('C')
        before = {entry['id']: entry for entry in load_todos(self.root)}
        result = self.move(a, b, 'after')
        self.assertEqual(self.titles(), ['B', 'A', 'Child', 'Grandchild', 'C'])
        self.assertEqual([entry['position'] for entry in result['todos']], list(range(5)))
        self.assertEqual(self.state()['version'], 3)
        for entry in result['todos']:
            for field in ('title', 'status', 'important', 'project_tags', 'created_at', 'parent_id'):
                self.assertEqual(entry[field], before[entry['id']][field])
            if entry['id'] != a['id']:
                self.assertEqual(entry['updated_at'], before[entry['id']]['updated_at'])
        event = self.state()['history'][-1]
        self.assertEqual(event['action'], 'move')
        self.assertEqual(event['tasks'][0]['position'], 1)
        self.assertEqual(event['move'], {'target_id': b['id'], 'placement': 'after', 'previous_parent_id': None, 'parent_id': None})
        self.assertEqual(export_history(self.root)['counts']['todo:move'], 1)

    def test_nest_before_after_and_unnest_to_root_end(self):
        a = self.add('A')
        child = self.add('Child', a['id'])
        b = self.add('B')
        c = self.add('C')
        self.move(b, a, 'inside')
        self.assertEqual(self.titles(), ['A', 'Child', 'B', 'C'])
        self.assertEqual(next(row for row in load_todos(self.root) if row['id'] == b['id'])['parent_id'], a['id'])
        self.move(c, child, 'before')
        self.assertEqual(self.titles(), ['A', 'C', 'Child', 'B'])
        self.move(c, b, 'after')
        self.assertEqual(self.titles(), ['A', 'Child', 'B', 'C'])
        result = self.move(b)
        self.assertEqual(self.titles(), ['A', 'Child', 'C', 'B'])
        self.assertIsNone(result['item']['parent_id'])
        self.assertEqual(result['move']['previous_parent_id'], a['id'])

    def test_noop_preserves_bytes_timestamps_and_legacy_schema(self):
        a = self.add('A')
        child = self.add('Child', a['id'])
        b = self.add('B')
        path = self.root / 'todos/state.json'
        before = path.read_bytes()
        for item, target, placement in ((b, None, 'root-end'), (a, b, 'before'), (b, a, 'after'), (child, a, 'inside')):
            self.move(item, target, placement)
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.state()['version'], 2)
        self.assertNotIn('position', load_todos(self.root)[0])

    def test_reject_cycles_missing_archived_and_malformed_targets_without_write(self):
        a = self.add('A')
        child = self.add('Child', a['id'])
        grandchild = self.add('Grandchild', child['id'])
        other = self.add('Archived')
        save_todo_action(self.root, {'action': 'remove', 'id': other['id']})
        path = self.root / 'todos/state.json'
        before = path.read_bytes()
        requests = [self.request(a, target, placement) for target in (a, child, grandchild) for placement in ('before', 'after', 'inside')]
        requests += [self.request(a, other, 'inside'), self.request(other, a, 'before')]
        request = self.request(a, child, 'inside')
        requests += [dict(request, target_id=None), dict(request, placement='root-end'), dict(request, placement='wrong'),
                     dict(request, target_id={}), dict(request, base_order=[[a['id']]]),
                     dict(request, base_order=request['base_order']*2), dict(request, extra=True)]
        for request in requests:
            with self.subTest(request=request), self.assertRaises(TodoError):
                save_todo_action(self.root, request)
            self.assertEqual(path.read_bytes(), before)

    def test_stale_topology_order_and_new_tasks_reject_but_title_status_edits_survive(self):
        a = self.add('A')
        b = self.add('B')
        stale = self.request(a)
        self.move(b, a, 'before')
        with self.assertRaises(StaleTodoError):
            save_todo_action(self.root, stale)
        stale = self.request(a)
        self.add('C')
        with self.assertRaises(StaleTodoError):
            save_todo_action(self.root, stale)
        request = self.request(a, b, 'inside')
        save_todo_action(self.root, {'action': 'edit', 'id': a['id'], 'base_title': 'A', 'title': 'Renamed'})
        save_todo_action(self.root, {'action': 'complete', 'id': b['id']})
        result = save_todo_action(self.root, request)
        self.assertEqual(result['item']['title'], 'Renamed')
        self.assertEqual(next(row for row in result['todos'] if row['id'] == b['id'])['status'], 'completed')

    def test_manual_order_survives_stars_additions_and_empty_store(self):
        a = self.add('A')
        b = self.add('B', important=True)
        self.assertEqual(self.titles(), ['B', 'A'])
        self.move(a, b, 'before')
        self.assertEqual(self.titles(), ['A', 'B'])
        save_todo_action(self.root, {'action': 'set_importance', 'id': b['id'], 'important': False})
        save_todo_action(self.root, {'action': 'set_importance', 'id': b['id'], 'important': True})
        c = self.add('C', important=True)
        child = self.add('Child', a['id'], important=True)
        self.assertEqual(self.titles(), ['A', 'Child', 'B', 'C'])
        save_todo_action(self.root, {'action': 'clear', 'ids': [a['id'], b['id'], c['id'], child['id']], 'status': 'all'})
        self.assertEqual(self.state()['version'], 3)
        self.add('New')
        self.assertEqual(load_todos(self.root)[0]['position'], 0)

    def test_same_preorder_with_changed_parent_is_stale(self):
        a = self.add('A')
        b = self.add('B')
        request = self.request(b, a, 'after')
        self.move(b, a, 'inside')
        self.assertEqual(self.titles(), ['A', 'B'])
        before = (self.root / 'todos/state.json').read_bytes()
        with self.assertRaises(StaleTodoError):
            save_todo_action(self.root, request)
        self.assertEqual((self.root / 'todos/state.json').read_bytes(), before)

    def test_clear_undo_restores_order_and_relationships_and_keeps_archived_positions(self):
        a = self.add('A')
        child = self.add('Child', a['id'])
        b = self.add('B')
        self.move(b, a, 'before')
        original = load_todos(self.root)
        cleared = save_todo_action(self.root, {'action': 'clear', 'ids': [a['id']], 'status': 'all'})
        self.assertEqual(cleared['archive'][0]['position'], 1)
        self.assertIsNone(next(row for row in cleared['todos'] if row['id'] == child['id'])['parent_id'])
        save_todo_action(self.root, {'action': 'undo', 'id': cleared['batch_id']})
        self.assertEqual([(row['id'], row['parent_id'], row['position']) for row in load_todos(self.root)],
                         [(row['id'], row['parent_id'], row['position']) for row in original])

    def test_restoring_conflicting_legacy_or_archived_positions_appends_safely(self):
        a = self.add('A')
        b = self.add('B')
        c = self.add('C')
        self.move(c, a, 'before')
        save_todo_action(self.root, {'action': 'remove', 'id': a['id']})
        self.move(b, c, 'before')
        self.assertEqual(self.state()['archive'][0]['items'][0]['position'], 1)
        save_todo_action(self.root, {'action': 'restore', 'id': a['id']})
        self.assertEqual(self.titles(), ['B', 'C', 'A'])
        save_todo_action(self.root, {'action': 'remove', 'id': a['id']})
        state = self.state()
        del state['archive'][0]['items'][0]['position']
        (self.root / 'todos/state.json').write_text(json.dumps(state))
        save_todo_action(self.root, {'action': 'restore', 'id': a['id']})
        self.assertEqual(self.titles(), ['B', 'C', 'A'])

    def test_restore_parent_preserves_a_surviving_childs_later_move(self):
        a = self.add('A')
        child = self.add('Child', a['id'])
        b = self.add('B')
        self.move(b, a, 'before')
        cleared = save_todo_action(self.root, {'action': 'remove', 'id': a['id']})
        self.move(child, b, 'inside')
        save_todo_action(self.root, {'action': 'undo', 'id': cleared['batch_id']})
        current = next(entry for entry in load_todos(self.root) if entry['id'] == child['id'])
        self.assertEqual(current['parent_id'], b['id'])

    def test_disk_failure_and_concurrent_stale_moves_preserve_atomic_state(self):
        a = self.add('A')
        b = self.add('B')
        c = self.add('C')
        request = self.request(c, a, 'before')
        path = self.root / 'todos/state.json'
        before = path.read_bytes()
        with patch('todo_state.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                save_todo_action(self.root, request)
        self.assertEqual(path.read_bytes(), before)
        def attempt(_):
            try:
                save_todo_action(self.root, request)
                return 'saved'
            except StaleTodoError:
                return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(attempt, range(2))), ['saved', 'stale'])
        self.assertEqual(len([event for event in self.state()['history'] if event['action'] == 'move']), 1)
        self.assertEqual(self.titles(), ['C', 'A', 'B'])

    def test_invalid_v3_position_or_move_history_is_preserved_and_rejected(self):
        a = self.add('A')
        b = self.add('B')
        self.move(b, a, 'before')
        valid = self.state()
        path = self.root / 'todos/state.json'
        for bad in (None, -1, True, 1.5):
            state = json.loads(json.dumps(valid))
            if bad is None:
                del state['items'][0]['position']
            else:
                state['items'][0]['position'] = bad
            path.write_text(json.dumps(state))
            before = path.read_bytes()
            with self.assertRaises(TodoError):
                self.add('Do not overwrite')
            self.assertEqual(path.read_bytes(), before)
        state = json.loads(json.dumps(valid))
        state['history'][-1]['move']['placement'] = 'bad'
        path.write_text(json.dumps(state))
        with self.assertRaises(TodoError):
            self.add('Do not overwrite bad history')


if __name__ == '__main__':
    unittest.main()
