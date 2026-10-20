"""Personal review marks persist independently of immutable source report history."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report_history import publish
from review_state import load_review_state, review_key, save_review_state
from test_report_history import snapshot


class ReviewHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = snapshot()

    def mark(self, kind, done, at):
        section = 'reviews' if kind == 'pr' else 'rfcs'
        url = self.data[section]['items'][0]['url']
        return save_review_state(self.root, self.data, {'kind': kind, 'url': url, 'done': done},
                                 now=datetime.fromisoformat(at))

    def test_coffee_and_tea_read_latest_marks_without_rewriting_source_or_archives(self):
        self.mark('pr', True, '2026-10-19T09:05:00-04:00')
        self.mark('rfc', True, '2026-10-19T09:06:00-04:00')
        original = deepcopy(self.data)
        coffee = publish(self.root, self.data, 'morning-coffee')
        coffee_file = Path(coffee['snapshot'])
        archived = coffee_file.read_bytes()
        archived_html = coffee_file.with_name('report.html').read_bytes()
        saved_coffee = json.loads(archived)
        self.assertEqual(saved_coffee['review_state'], load_review_state(self.root))
        for section in ('reviews', 'rfcs'):
            self.assertEqual(saved_coffee[section], self.data[section])
        self.assertEqual(self.data, original)

        self.mark('pr', False, '2026-10-19T11:55:00-04:00')
        afternoon = snapshot('12:00')
        afternoon['review_state'] = saved_coffee['review_state']
        afternoon['review_interaction'] = {'endpoint': 'http://127.0.0.1:1234/review', 'token': 'private-capability'}
        tea = publish(self.root, afternoon, 'tea-time')
        saved_tea = json.loads(Path(tea['snapshot']).read_text())
        pr = review_key('pr', afternoon['reviews']['items'][0]['url'])
        rfc = review_key('rfc', afternoon['rfcs']['items'][0]['url'])
        self.assertFalse(saved_tea['review_state'][pr]['done'])
        self.assertTrue(saved_tea['review_state'][rfc]['done'])
        self.assertNotIn('review_interaction', saved_tea)
        self.assertNotIn('private-capability', Path(tea['html']).read_text())
        self.assertEqual(saved_tea['updates']['items'], [])
        self.assertEqual(len(saved_tea['reviews']['items']), 1)
        self.assertEqual(len(saved_tea['rfcs']['items']), 1)
        self.assertFalse(saved_tea['rfcs']['items'][0]['user_approved'])
        self.assertEqual(saved_tea['reviews']['items'][0]['reviewDecision'], 'REVIEW_REQUIRED')
        self.assertEqual(coffee_file.read_bytes(), archived)
        self.assertEqual(coffee_file.with_name('report.html').read_bytes(), archived_html)

    def test_marks_span_days_and_source_timestamp_noise(self):
        marked = self.mark('pr', True, '2026-10-19T09:05:00-04:00')
        next_day = snapshot('09:00', day='2026-10-20')
        next_day['review_state'] = {}
        next_day['reviews']['items'][0]['updatedAt'] = '2026-10-20T12:59:59Z'
        report = publish(self.root, next_day, 'morning-coffee')
        saved = json.loads(Path(report['snapshot']).read_text())
        key = review_key('pr', marked['url'])
        self.assertEqual(saved['review_state'][key], marked)
        self.assertEqual(saved['reviews']['items'], next_day['reviews']['items'])
        self.assertEqual(saved['report']['date'], '2026-10-20')

    def test_corrupt_mark_warns_and_keeps_other_valid_local_state(self):
        marked = self.mark('pr', True, '2026-10-19T09:05:00-04:00')
        (self.root / 'review-state' / 'bad.json').write_text('{invalid')
        report = publish(self.root, self.data, 'morning-coffee')
        saved = json.loads(Path(report['snapshot']).read_text())
        self.assertEqual(saved['review_state'][review_key('pr', marked['url'])], marked)
        self.assertTrue(any('local review mark' in warning for warning in report['warnings']))
        self.assertEqual(saved['reviews']['items'], self.data['reviews']['items'])

    def test_unavailable_store_never_restores_incoming_stale_marks(self):
        self.data['review_state'] = {'stale': {'done': True}}
        with patch('report_history.load_review_state', side_effect=OSError('store unreadable')):
            report = publish(self.root, self.data, 'morning-coffee')
        saved = json.loads(Path(report['snapshot']).read_text())
        self.assertEqual(saved['review_state'], {})
        self.assertTrue(any('Local review marks unavailable' in warning for warning in report['warnings']))
        self.assertEqual(saved['reviews']['items'], self.data['reviews']['items'])


if __name__ == '__main__':
    unittest.main()
