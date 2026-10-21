"""Authenticated calendar completion stays local and survives view regeneration."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from calendar_state import calendar_key, load_calendar_state
from local_plan_server import handler_for, interactive_snapshot
from plan_submission import save_plan
from report_history import publish
from test_report_history import snapshot


class CalendarCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = snapshot()
        self.data['availability'] = {'status': 'complete', 'checked_at': self.data['collected_at'],
            'coverage': 'Synthetic calendar', 'window_start': '09:00', 'window_end': '17:00', 'busy': []}
        self.token = 'synthetic-calendar-capability-' + 'x' * 32
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.data, self.root, self.token))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = 'http://127.0.0.1:' + str(self.server.server_port)
        self.key = calendar_key(self.data, self.data['agenda']['events'][0])

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def post(self, request, **headers):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        connection.request('POST', '/calendar/done', json.dumps(request), {
            'Content-Type': 'application/json', 'Origin': self.origin,
            'X-Brief-Token': self.token, **headers})
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_authenticated_save_reload_undo_and_invalid_identity(self):
        before = json.dumps(self.data, sort_keys=True)
        self.assertEqual(self.post({'key': self.key, 'done': True}),
                         (200, {'ok': True, 'record': {'key': self.key, 'done': True}}))
        current = interactive_snapshot(self.data, self.root, self.origin, self.token)
        self.assertIs(current['calendar_state'][self.key], True)
        self.assertEqual(json.dumps(self.data, sort_keys=True), before)
        self.data['agenda']['events'][0]['title'] = 'A refreshed title'
        self.assertEqual(self.post({'key': self.key, 'done': False})[0], 200)
        self.assertIs(load_calendar_state(self.root, self.data)[self.key], False)
        self.data['agenda']['events'].clear()
        self.assertEqual(self.post({'key': self.key, 'done': True})[0], 400)

    def test_exact_origin_token_and_boolean_required(self):
        request = {'key': self.key, 'done': True}
        for headers in ({'Origin': 'null'}, {'Origin': 'https://example.com'}, {'X-Brief-Token': 'wrong'}):
            self.assertEqual(self.post(request, **headers)[0], 403)
        self.assertEqual(self.post({'key': self.key, 'done': 1})[0], 400)
        self.assertEqual(self.post({'key': 'arbitrary', 'done': True})[0], 400)
        self.assertEqual(load_calendar_state(self.root, self.data), {})

    def test_latest_local_plan_identity_and_archive_capability_stripping(self):
        block = {'kind': 'focus', 'start': 810, 'minutes': 45}
        save_plan(self.root, self.data, {'date': self.data['report']['date'],
                  'timezone': self.data['report']['timezone'], 'blocks': [block]})
        key = calendar_key(self.data, block, local=True)
        self.assertEqual(self.post({'key': key, 'done': True})[0], 200)
        current = interactive_snapshot(self.data, self.root, self.origin, self.token)
        archived = json.loads(Path(publish(self.root, current, 'morning-coffee')['snapshot']).read_text())
        self.assertNotIn('calendar_interaction', archived)
        self.assertNotIn(self.token, json.dumps(archived))
        self.assertIs(archived['calendar_state'][key], True)
        save_plan(self.root, self.data, {'date': self.data['report']['date'],
                  'timezone': self.data['report']['timezone'], 'blocks': []})
        self.assertEqual(self.post({'key': key, 'done': False})[0], 400)
