"""Both dated briefs load the same current tasks without archiving save capabilities."""
import json
from pathlib import Path
import tempfile
import unittest

from test_report_history import snapshot
from report_history import prepare, publish
from todo_state import save_todo_action


class TodoHistoryTests(unittest.TestCase):
    def test_prepare_coffee_and_tea_share_current_tasks_and_strip_live_capability(self):
        with tempfile.TemporaryDirectory() as root:
            task = save_todo_action(root, {'action': 'add', 'title': 'Local history task'})['item']
            prepared = prepare(root, '2026-10-19', 'America/Toronto', 'morning-coffee')
            self.assertEqual(prepared['todos'][0]['id'], task['id'])
            tomorrow = prepare(root, '2026-10-20', 'America/Toronto', 'tea-time')
            self.assertEqual(tomorrow['todos'][0]['id'], task['id'])
            self.assertEqual(tomorrow['todos'][0]['status'], 'pending')
            self.assertNotIn('due_date', tomorrow['todos'][0])
            data = snapshot()
            data['todos'] = [{'title': 'Stale input'}]
            data['todo_interaction'] = {'endpoint': 'http://127.0.0.1:1/todo', 'token': 'private-runtime-capability'}
            morning = publish(root, data, 'morning-coffee')
            archived = json.loads(Path(morning['snapshot']).read_text())
            self.assertEqual(archived['todos'][0]['id'], task['id'])
            self.assertNotIn('todo_interaction', archived)
            self.assertNotIn('private-runtime-capability', Path(morning['html']).read_text())
            save_todo_action(root, {'action': 'complete', 'id': task['id']})
            tea = publish(root, snapshot('14:00'), 'tea-time')
            updated = json.loads(Path(tea['snapshot']).read_text())
            self.assertEqual(updated['todos'][0]['status'], 'completed')
            self.assertEqual(archived['todos'][0]['status'], 'pending')
            self.assertIn('Local history task', Path(tea['html']).read_text())

    def test_corrupt_store_is_disclosed_without_overwriting_it(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'todos'
            folder.mkdir()
            store = folder / 'state.json'
            store.write_text('{')
            prepared = prepare(root, '2026-10-19', 'America/Toronto', 'morning-coffee')
            self.assertTrue(prepared['warnings'])
            result = publish(root, snapshot(), 'morning-coffee')
            archived = json.loads(Path(result['snapshot']).read_text())
            self.assertEqual(archived['todos'], [])
            self.assertTrue(archived['history']['warnings'])
            self.assertEqual(store.read_text(), '{')


if __name__ == '__main__':
    unittest.main()
