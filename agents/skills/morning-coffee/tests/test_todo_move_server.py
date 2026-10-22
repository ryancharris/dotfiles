"""Task moves persist through the detached service and reject stale tabs."""
import http.client
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlsplit

from test_report_history import snapshot

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_history import export_history
from todo_state import load_todos


class TodoMoveServerTests(unittest.TestCase):
    def test_detached_move_survives_reload_and_stale_rejection_preserves_history(self):
        with tempfile.TemporaryDirectory(prefix='coffee-task-move-server-') as folder:
            root = Path(folder)
            source, output = root / 'snapshot.json', root / 'session.html'
            source.write_text(json.dumps(snapshot()))
            launched = subprocess.run([sys.executable, str(SKILL / 'scripts/local_plan_server.py'),
                '--root', str(root), '--snapshot', str(source), '--output', str(output), '--background'],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(launched.returncode, 0, launched.stderr)
            metadata = json.loads(output.with_suffix('.session.json').read_text())
            target = urlsplit(metadata['url'])
            token = target.path.rsplit('/', 1)[-1]

            def call(payload=None, authenticated=True):
                connection = http.client.HTTPConnection(target.hostname, target.port, timeout=5)
                headers = {'Content-Type': 'application/json', 'Origin': f'http://{target.netloc}'}
                if authenticated:
                    headers['X-Brief-Token'] = token
                try:
                    connection.request('POST' if payload is not None else 'GET',
                                       '/todo' if payload is not None else target.path,
                                       json.dumps(payload) if payload is not None else None, headers)
                    response = connection.getresponse()
                    body = response.read().decode()
                    return response.status, json.loads(body) if payload is not None else body
                finally:
                    connection.close()

            try:
                a = call({'action': 'add', 'title': 'Parent task'})[1]['item']
                b = call({'action': 'add', 'title': 'Move this task'})[1]['item']
                base = [[item['id'], item.get('parent_id')] for item in load_todos(root)]
                payload = {'action': 'move', 'id': b['id'], 'target_id': a['id'],
                           'placement': 'inside', 'base_order': base}
                self.assertEqual(call(payload, authenticated=False)[0], 403)
                code, result = call(payload)
                self.assertEqual(code, 200, result)
                self.assertEqual(result['item']['parent_id'], a['id'])
                store = root / 'todos/state.json'
                saved = store.read_bytes()
                self.assertEqual(json.loads(saved)['version'], 3)
                code, page = call()
                self.assertEqual(code, 200)
                self.assertIn('"parent_id": "' + a['id'] + '"', page)
                code, result = call(dict(payload, placement='before'))
                self.assertEqual(code, 409, result)
                self.assertEqual(store.read_bytes(), saved)
                current = load_todos(root)
                payload.update(placement='root-end', target_id=None,
                               base_order=[[item['id'], item.get('parent_id')] for item in current])
                code, result = call(payload)
                self.assertEqual(code, 200, result)
                self.assertIsNone(result['item']['parent_id'])
                self.assertEqual([item['id'] for item in load_todos(root)], [a['id'], b['id']])
                exported = export_history(root)
                self.assertEqual(exported['warnings'], [])
                self.assertEqual(exported['counts']['todo:move'], 2)
            finally:
                os.kill(metadata['pid'], signal.SIGTERM)


if __name__ == '__main__':
    unittest.main()
