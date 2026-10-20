"""Notes survive report generations and reject stale browser overwrites."""
from http.server import HTTPServer
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from notes_state import NotesError, NotesConflict, load_notes, save_notes, render_notes
from local_plan_server import handler_for, session_snapshot
from report_history import prepare, publish
from test_report_history import snapshot, ReportSurface

SKILL = Path(__file__).resolve().parents[1]


class NotesTests(unittest.TestCase):
    def test_shared_store_revision_clear_and_private_files(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(load_notes(root)['revision'], 0)
            self.assertFalse((Path(root) / 'notes').exists())
            note = save_notes(root, {'text': 'Learned <details>\nRemember café 🎉', 'revision': 0})['notes']
            self.assertEqual(note['revision'], 1)
            self.assertEqual(load_notes(root), note)
            with self.assertRaises(NotesConflict):
                save_notes(root, {'text': 'Stale overwrite', 'revision': 0})
            self.assertEqual(load_notes(root), note)
            cleared = save_notes(root, {'text': '', 'revision': 1})['notes']
            self.assertEqual(cleared['text'], '')
            self.assertEqual(cleared['revision'], 2)
            self.assertEqual((Path(root) / 'notes').stat().st_mode & 0o777, 0o700)
            self.assertEqual((Path(root) / 'notes/state.json').stat().st_mode & 0o777, 0o600)

    def test_invalid_or_corrupt_notes_are_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            for value in ('x' * 25001, None, 'bad\0control'):
                with self.subTest(value=str(value)[:20]), self.assertRaises(NotesError):
                    save_notes(root, {'text': value, 'revision': 0})
            for revision in (True, -1, '0'):
                with self.assertRaises(NotesError):
                    save_notes(root, {'text': 'text', 'revision': revision})
            folder = Path(root) / 'notes'
            folder.mkdir(exist_ok=True)
            path = folder / 'state.json'
            path.write_text('{')
            self.assertTrue(load_notes(root, True)['warnings'])
            with self.assertRaises(NotesError):
                save_notes(root, {'text': 'replacement', 'revision': 0})
            self.assertEqual(path.read_text(), '{')

    def test_coffee_tea_across_dates_reload_notes_but_archives_are_readonly(self):
        with tempfile.TemporaryDirectory() as root:
            saved = save_notes(root, {'text': 'Remember </textarea><script>details</script>', 'revision': 0})['notes']
            for date, kind in [('2026-10-19', 'morning-coffee'), ('2026-10-20', 'tea-time')]:
                self.assertEqual(prepare(root, date, 'America/Toronto', kind)['notes'], saved)
            data = snapshot()
            data['notes'] = {'text': 'stale input'}
            data['notes_interaction'] = {'endpoint': 'http://127.0.0.1:1/notes', 'token': 'private-notes-token'}
            result = publish(root, data, 'morning-coffee')
            archived = json.loads(Path(result['snapshot']).read_text())
            self.assertEqual(archived['notes'], saved)
            self.assertNotIn('notes_interaction', archived)
            html = Path(result['html']).read_text()
            surface = ReportSurface(html)
            self.assertIn('readonly', surface.by_id['local-notes-text']['attrs'])
            self.assertIn('&lt;/textarea&gt;&lt;script&gt;', html)
            self.assertNotIn('private-notes-token', html)
            new = save_notes(root, {'text': 'Updated learning', 'revision': 1})['notes']
            self.assertEqual(session_snapshot(archived, root)['notes'], new)
            self.assertEqual(json.loads(Path(result['snapshot']).read_text())['notes'], saved)
            tea = publish(root, snapshot('14:00'), 'tea-time')
            self.assertEqual(json.loads(Path(tea['snapshot']).read_text())['notes'], new)

    def test_authenticated_http_notes_limit_conflict_and_tea(self):
        with tempfile.TemporaryDirectory() as root:
            data = snapshot()
            data['history'] = {'kind': 'tea-time'}
            data['notes_interaction'] = {'endpoint': 'unused', 'token': 'capability'}
            server = HTTPServer(('127.0.0.1', 0), handler_for(data, root, 'capability'))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def post(payload, token='capability', origin=None):
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    connection.request('POST', '/notes', json.dumps(payload), {'Content-Type': 'application/json',
                        'Origin': origin or 'http://127.0.0.1:' + str(server.server_port), 'X-Brief-Token': token})
                    response = connection.getresponse()
                    result = response.status, json.loads(response.read())
                    connection.close()
                    return result
                self.assertEqual(post({'text': 'Unauthorized', 'revision': 0}, 'wrong')[0], 403)
                self.assertEqual(post({'text': 'Unauthorized', 'revision': 0}, origin='https://evil.example')[0], 403)
                text = '🎉' * 25000
                status, result = post({'text': text, 'revision': 0})
                self.assertEqual(status, 200)
                self.assertEqual(result['notes']['text'], text)
                self.assertEqual(post({'text': 'stale page', 'revision': 0})[0], 409)
                self.assertEqual(load_notes(root)['text'], text)
                self.assertEqual(post({'text': 'x' * 25001, 'revision': 1})[0], 400)
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                connection.request('GET', '/report/capability')
                response = connection.getresponse()
                page = response.read().decode()
                connection.close()
                self.assertEqual(response.status, 200)
                config = json.loads(ReportSurface(page).by_id['notes-config']['children'][0])
                self.assertEqual(config['notes']['revision'], 1)
                self.assertEqual(config['token'], 'capability')
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for local interaction tests')
    def test_browser_debounce_ack_races_failure_and_conflict(self):
        result = subprocess.run(['node', str(SKILL / 'tests/test_local_notes.js')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
