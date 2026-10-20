"""Local review marks persist without mutating provider review facts."""
from copy import deepcopy
from datetime import datetime
import http.client
from http.server import HTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_plan_server import handler_for, session_snapshot
from review_state import ReviewError, canonical_url, load_review_state, review_key, save_review_state

PR = 'https://github.com/dbt-labs/example/pull/42'
RFC = 'https://www.notion.so/fixture-rfc'


def snapshot(day='2026-10-19', tea=False):
    return {'report': {'date': day, 'timezone': 'America/Toronto', 'title': 'Tea Time' if tea else 'Morning Coffee'},
            'history': {'kind': 'tea-time' if tea else 'morning-coffee'},
            'reviews': {'items': [{'url': PR, 'reviewDecision': 'REVIEW_REQUIRED', 'queue': 'direct'}]},
            'rfcs': {'items': [{'url': RFC, 'user_approved': False}]}}


class ReviewStateTests(unittest.TestCase):
    def test_private_append_only_marks_undo_and_reload_across_report_days(self):
        data = snapshot()
        original = deepcopy(data)
        with tempfile.TemporaryDirectory() as root:
            first = save_review_state(root, data, {'kind': 'pr', 'url': PR + '/?tab=files#diff', 'done': True},
                                      datetime.fromisoformat('2026-10-19T09:00:00-04:00'))
            save_review_state(root, data, {'kind': 'rfc', 'url': RFC, 'done': True},
                              datetime.fromisoformat('2026-10-19T10:00:00-04:00'))
            opened = session_snapshot(snapshot('2026-10-20'), root)
            self.assertEqual(opened['review_state'][review_key('pr', PR)], first)
            undone = save_review_state(root, snapshot('2026-10-20'), {'kind': 'pr', 'url': PR, 'done': False},
                                       datetime.fromisoformat('2026-10-20T09:00:00-04:00'))
            state = load_review_state(root)
            self.assertEqual(state[review_key('pr', PR)], undone)
            self.assertTrue(state[review_key('rfc', RFC)]['done'])
            files = list((Path(root) / 'review-state').glob('*.json'))
            self.assertEqual(len(files), 3)
            self.assertEqual((Path(root) / 'review-state').stat().st_mode & 0o777, 0o700)
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in files))
            self.assertEqual(sum(json.loads(path.read_text())['done'] for path in files), 2)
            self.assertEqual(data, original)

    def test_identity_canonicalization_kind_scope_and_strict_done(self):
        self.assertEqual(canonical_url('https://GitHub.COM:443/DBT-LABS/Example/pull/42/?q=1#file'), PR)
        self.assertNotEqual(review_key('pr', PR), review_key('rfc', PR))
        with tempfile.TemporaryDirectory() as root:
            for request in ({'kind': 'pr', 'url': 'https://github.com/other/repo/pull/42', 'done': True},
                            {'kind': 'rfc', 'url': PR, 'done': True},
                            {'kind': 'issue', 'url': PR, 'done': True},
                            {'kind': 'pr', 'url': PR, 'done': 1},
                            {'kind': 'pr', 'url': PR, 'done': 'true'},
                            {'kind': 'pr', 'url': PR, 'done': None},
                            {'kind': 'pr', 'url': PR, 'done': True, 'reviewDecision': 'APPROVED'},
                            {'kind': 'pr', 'url': 'javascript:alert(1)', 'done': True}, []):
                with self.subTest(request=request), self.assertRaises(ReviewError):
                    save_review_state(root, snapshot(), request)
            self.assertEqual(list(Path(root).rglob('*.json')), [])

    def test_session_reloads_live_marks_and_tea_explicitly_supports_reviews_only(self):
        with tempfile.TemporaryDirectory() as root:
            data = snapshot(tea=True)
            data['review_state'] = {'stale': {'done': True}}
            data['review_interaction'] = {'endpoint': 'http://old-session', 'token': 'old'}
            data['plan_submission'] = {'endpoint': 'http://old-session', 'token': 'old'}
            opened = session_snapshot(data, root, reviews_only=True)
            self.assertEqual(opened['review_state'], {})
            self.assertNotIn('review_interaction', opened)
            self.assertNotIn('plan_submission', opened)
            self.assertEqual(data['review_state'], {'stale': {'done': True}})
            save_review_state(root, data, {'kind': 'pr', 'url': PR, 'done': True})
            reopened = session_snapshot(data, root, reviews_only=True)
            self.assertTrue(reopened['review_state'][review_key('pr', PR)]['done'])

    def test_bad_record_is_disclosed_without_discarding_good_marks(self):
        with tempfile.TemporaryDirectory() as root:
            record = save_review_state(root, snapshot(), {'kind': 'pr', 'url': PR, 'done': True})
            (Path(root) / 'review-state' / '9999-corrupt.json').write_text('{')
            loaded = load_review_state(root, with_warnings=True)
            self.assertEqual(loaded['state'][review_key('pr', PR)], record)
            self.assertEqual(len(loaded['warnings']), 1)
            opened = session_snapshot(snapshot(), root)
            self.assertTrue(opened['history']['warnings'])

    def test_loopback_authorization_persistence_acknowledgement_and_tea_submit_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            server = HTTPServer(('127.0.0.1', 0), handler_for(snapshot(tea=True), root, 'private-capability'))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def post(path='/review', request=None, **changes):
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    headers = {'Origin': 'null', 'Host': '127.0.0.1:' + str(server.server_port),
                               'Content-Type': 'application/json', 'X-Brief-Token': 'private-capability'}
                    headers.update(changes)
                    payload = request if request is not None else {'kind': 'pr', 'url': PR + '?diff=1', 'done': True}
                    connection.request('POST', path, json.dumps(payload), headers)
                    response = connection.getresponse()
                    result = response.status, json.loads(response.read()), response.getheader('Access-Control-Allow-Origin')
                    connection.close()
                    return result
                self.assertEqual(post(**{'X-Brief-Token': 'wrong'})[0], 403)
                self.assertEqual(post(Origin='https://evil.example')[0], 403)
                self.assertEqual(post(Host='evil.example')[0], 403)
                self.assertEqual(post('/review?extra=1')[0], 403)
                self.assertEqual(post('/submit')[0], 403)
                self.assertEqual(list(Path(root).rglob('*.json')), [])
                self.assertEqual(post(request={'kind': 'pr', 'url': RFC, 'done': True})[0], 400)
                self.assertEqual(post(request={'kind': 'pr', 'url': PR, 'done': 1})[0], 400)
                self.assertEqual(post(request={'kind': 'pr', 'url': PR + '?' + 'x' * 17000, 'done': True})[0], 400)
                status, response, cors = post()
                self.assertEqual(status, 200)
                self.assertEqual(cors, 'null')
                self.assertTrue(response['ok'])
                self.assertEqual(response['record']['url'], PR)
                self.assertEqual(response['record'], load_review_state(root)[review_key('pr', PR)])
                status, response, _ = post(request={'kind': 'pr', 'url': PR, 'done': False})
                self.assertEqual(status, 200)
                self.assertFalse(response['record']['done'])
                with patch('local_plan_server.save_review_state', side_effect=OSError('disk full')):
                    status, response, _ = post()
                self.assertEqual(status, 500)
                self.assertNotIn('ok', response)
                self.assertFalse(load_review_state(root)[review_key('pr', PR)]['done'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
