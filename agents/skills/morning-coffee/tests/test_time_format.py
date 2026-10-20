"""24-hour clock boundaries and legacy Coffee/Tea display compatibility."""
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render_brief import render
from time_format import clock_label, display_snapshot, event_time, local_time
from report_history import event_window
from test_report_history import snapshot


class VisibleText(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.hidden = 0
        self.text = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)


class TimeDisplayTests(unittest.TestCase):
    def test_legacy_clock_boundaries_and_ranges(self):
        for source, expected in [
            ('12 AM', '00:00'), ('12 PM', '12:00'), ('11:59 PM', '23:59'),
            ('9:05 am EDT', '09:05 EDT'), ('9–10 AM', '09:00–10:00'),
            ('11–1 PM', '11:00–13:00'), ('11 PM–1 AM', '23:00–01:00'),
            ('11–12 AM', '23:00–00:00'), ('12–1 PM', '12:00–13:00'),
            ('9:30–10:30', '09:30–10:30'), ('Oct 19, 9 p.m.', 'Oct 19, 21:00'),
            ('Tomorrow, 09:00', 'Tomorrow, 09:00'), ('2026-10-19', '2026-10-19'),
            ('All day', 'All day')]:
            with self.subTest(source=source):
                self.assertEqual(clock_label(source), expected)

    def test_authoritative_instants_use_report_timezone(self):
        for source, expected in [('2026-10-20T04:00:00Z', '00:00'),
                                 ('2026-10-20T16:00:00Z', '12:00'),
                                 ('2026-10-21T03:59:00Z', '23:59')]:
            self.assertEqual(local_time(source, 'America/Toronto'), expected)
        self.assertEqual(event_time({'start': '2026-10-21T03:30:00Z', 'end': '2026-10-21T04:00:00Z',
                                     'time': 'incorrect 3 PM'}, 'America/Toronto'), '23:30–00:00')
        self.assertEqual(event_time({'all_day': True, 'time': '12 AM'}, 'America/Toronto'), 'All day')
        self.assertEqual(event_window({'time': '9–10 AM'}, 'America/Toronto'), '09:00–10:00')

    def test_coffee_and_tea_normalize_only_time_ui(self):
        original = snapshot('12:00')
        original['report']['time'] = '12 PM'
        original['reviews']['collected_label'] = '12:00 PM EDT'
        original['oncall']['shift'] = 'Tomorrow, 9 AM EDT'
        original['rfcs']['items'][0]['submitted_local'] = 'Oct 19, 11:59 PM EDT'
        original['priorities'][0]['context'] = 'Customer said 9 AM in their source message.'
        original['agenda']['events'][0]['time'] = '10–10:30 AM'
        original['agenda']['events'].append({'id': 'legacy', 'title': 'Legacy event', 'time': '11 PM–11:30 PM'})
        original['reviews']['items'][0]['_retained_at'] = '2026-10-19T04:00:00Z'
        before = deepcopy(original)
        for kind in ('morning-coffee', 'tea-time'):
            data = deepcopy(original)
            data['history'] = {'kind': kind}
            data['updates'] = {'since': '2026-10-19T13:00:00Z', 'items': [], 'since_morning': []}
            data['status_checks'] = [{'section': 'priorities', 'id': 'priority:rollout', 'title': 'Verify fixture rollout',
                                     'outcome': 'uncertain', 'question': 'Finished?',
                                     'attempts': [{'source': 'github', 'method': 'Lookup', 'result': 'Unknown',
                                                   'checked_at': '2026-10-19T16:00:00Z'}]}]
            text = ' '.join(VisibleText(render(data)).text)
            with self.subTest(kind=kind):
                self.assertIn('12:00 · America/Toronto', text)
                self.assertIn('Updated Oct 19, 12:00 EDT', text)
                self.assertIn('Tomorrow, 09:00 EDT', text)
                self.assertIn('Oct 19, 23:59 EDT', text)
                self.assertIn('10:00–10:30', text)
                self.assertIn('23:00–23:30', text)
                self.assertIn('Oct 19, 00:00 -0400', text)
                self.assertIn('Customer said 9 AM in their source message.', text)
                self.assertNotIn('12:00 PM', text)
                self.assertNotIn('10–10:30 AM', text)
                if kind == 'tea-time':
                    self.assertIn('Oct 19, 12:00 EDT', text)
        self.assertEqual(original, before)

    def test_timestamp_overrides_legacy_label_and_copy_preserves_facts(self):
        data = snapshot('00:00')
        data['report']['time'] = '12 PM'
        data['agenda']['events'][0]['time'] = '9 PM'
        original = deepcopy(data)
        displayed = display_snapshot(data)
        self.assertEqual(displayed['report']['time'], '00:00')
        self.assertEqual(displayed['agenda']['events'][0]['time'], '10:00–10:30')
        self.assertEqual(data, original)


if __name__ == '__main__':
    unittest.main()
