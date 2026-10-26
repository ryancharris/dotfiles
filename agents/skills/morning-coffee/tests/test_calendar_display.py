"""Calendar display projections preserve provider evidence and full-day safety."""
from copy import deepcopy
from datetime import datetime, time
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from zoneinfo import ZoneInfo

from test_report_history import ReportSurface, snapshot
from day_calendar import calendar_data, render_calendar
from local_plan_server import handler_for
from plan_day import suggest
from plan_submission import PlanError, validate_plan
from render_brief import agenda_counts, render, render_updates, today_rows
from report_history import changes, publish, select_report
from workspace_state import open_workspace


def event(title, start, end, **extra):
    return dict(id=title, title=title, start=start, end=end, time='Source label', **extra)


class CalendarDisplayTests(unittest.TestCase):
    def with_updates(self, current, previous):
        current['updates'] = dict(items=changes(current, previous),
            since_morning=changes(current, previous), since=previous['collected_at'],
            previous_kind='morning-coffee')
        return current

    def test_outside_events_are_absent_from_rendered_changes_and_counts(self):
        old = snapshot()
        old['agenda']['events'] = []
        current = deepcopy(old)
        current['agenda']['events'] = [event('AFTER_HOURS_SECRET',
            '2026-10-19T20:00:00-04:00', '2026-10-19T21:00:00-04:00')]
        self.with_updates(current, old)
        before = deepcopy(current)
        self.assertEqual(len(current['updates']['items']), 1)
        for kind in ('morning-coffee', 'tea-time'):
            current['history'] = {'kind': kind}
            text = ReportSurface(render(current)).visible_text()
            self.assertNotIn('AFTER_HOURS_SECRET', text)
            self.assertNotIn('1 agenda update', text)
            self.assertNotIn('New since Coffee: 1 event', text)
        current.pop('history')
        self.assertEqual(current, before)

    def test_removed_event_changes_use_original_intervals_without_losing_audit(self):
        old = snapshot()
        old['agenda']['events'] = [
            event('visible-removed', '2026-10-19T10:00:00-04:00', '2026-10-19T11:00:00-04:00'),
            event('hidden-removed', '2026-10-19T20:00:00-04:00', '2026-10-19T21:00:00-04:00')]
        current = deepcopy(old)
        current['agenda']['events'] = []
        self.with_updates(current, old)
        before = deepcopy(current)
        text = ReportSurface(render_updates(current)).visible_text()
        self.assertNotIn('hidden-removed', text)
        self.assertIn('1 agenda update', text)
        self.assertEqual(len(current['updates']['items']), 2)
        self.assertEqual(current['updates']['items'][0]['calendar_event']['start'],
                         old['agenda']['events'][0]['start'])
        self.assertEqual(current, before)

    def test_legacy_change_rows_use_current_identity_or_require_interval_evidence(self):
        old = snapshot()
        old['agenda']['events'] = []
        current = deepcopy(old)
        current['agenda']['events'] = [
            event('legacy-inside', '2026-10-19T10:00:00-04:00', '2026-10-19T11:00:00-04:00'),
            event('legacy-outside', '2026-10-19T20:00:00-04:00', '2026-10-19T21:00:00-04:00')]
        self.with_updates(current, old)
        for rows in (current['updates']['items'], current['updates']['since_morning']):
            for row in rows:
                row.pop('calendar_event')
            rows.append(dict(section='Today', status='No longer listed', id='legacy-unknown',
                             title='UNKNOWN_INTERVAL', fields=[]))
        text = ReportSurface(render_updates(current)).visible_text()
        self.assertIn('legacy-inside', text)
        self.assertNotIn('legacy-outside', text)
        self.assertNotIn('UNKNOWN_INTERVAL', text)
        self.assertIn('1 agenda update', text)

    def assert_today(self, data, expected):
        before = deepcopy(data)
        for kind in ('morning-coffee', 'tea-time'):
            source = deepcopy(data)
            source['history'] = {'kind': kind}
            page = ReportSurface(render(source))
            titles = [row['title'] for row in today_rows(source) if not row['_local_plan']]
            self.assertCountEqual(titles, expected)
            text = page.visible_text(page.by_id['today'])
            for row in data['agenda']['events']:
                self.assertEqual(row['title'] in text, row['title'] in expected, row['title'])
        self.assertEqual(data, before)

    def test_boundaries_spanning_events_and_original_intervals(self):
        data = snapshot()
        cases = [
            ('early', '2026-10-19T06:00:00-04:00', '2026-10-19T07:00:00-04:00', False),
            ('ends-at-eight', '2026-10-19T07:00:00-04:00', '2026-10-19T08:00:00-04:00', False),
            ('crosses-eight', '2026-10-19T07:00:00-04:00', '2026-10-19T08:00:01-04:00', True),
            ('subsecond-overlap', '2026-10-19T07:59:59-04:00', '2026-10-19T08:00:00.000001-04:00', True),
            ('starts-at-eight', '2026-10-19T08:00:00-04:00', '2026-10-19T09:00:00-04:00', True),
            ('ends-at-nineteen', '2026-10-19T18:00:00-04:00', '2026-10-19T19:00:00-04:00', True),
            ('crosses-nineteen', '2026-10-19T18:59:59-04:00', '2026-10-19T20:00:00-04:00', True),
            ('starts-at-nineteen', '2026-10-19T19:00:00-04:00', '2026-10-19T20:00:00-04:00', False),
            ('overnight', '2026-10-18T23:00:00-04:00', '2026-10-19T08:30:00-04:00', True),
            ('spanning', '2026-10-18T23:00:00-04:00', '2026-10-20T01:00:00-04:00', True),
            ('other-day', '2026-10-20T10:00:00-04:00', '2026-10-20T11:00:00-04:00', False),
        ]
        data['agenda']['events'] = [event(name, start, end) for name, start, end, _ in cases]
        self.assert_today(data, [name for name, _, _, visible in cases if visible])
        calendar = ReportSurface(render_calendar(data, read_only=True)).visible_text()
        for name, _, _, visible in cases:
            self.assertEqual(name in calendar, visible, name)
        rows = today_rows(data)
        for row in rows:
            original = next(item for item in data['agenda']['events'] if item['id'] == row['id'])
            self.assertEqual((row['start'], row['end']), (original['start'], original['end']))
        self.assertEqual(agenda_counts(data, rows), '7 events from calendar · 0 local plan blocks')

    def test_iana_timezone_and_dst_transitions_use_each_local_day(self):
        for day, utc_hour in [('2026-03-08', 12), ('2026-11-01', 13), ('2026-10-19', 12)]:
            with self.subTest(day=day):
                data = snapshot(day=day)
                data['agenda']['events'] = [
                    event('before', f'{day}T{utc_hour-1:02}:00:00Z', f'{day}T{utc_hour:02}:00:00Z'),
                    event('inside', f'{day}T{utc_hour:02}:00:00Z', f'{day}T{utc_hour+1:02}:00:00Z'),
                ]
                self.assert_today(data, ['inside'])
        data['report']['timezone'] = 'Asia/Tokyo'
        data['agenda']['events'] = [event('tokyo-morning', '2026-10-18T23:00:00Z', '2026-10-19T00:00:00Z'),
                                    event('toronto-morning', '2026-10-19T12:00:00Z', '2026-10-19T13:00:00Z')]
        self.assert_today(data, ['tokyo-morning'])

    def test_all_day_privacy_status_and_free_tentative_rules(self):
        data = snapshot()
        data['agenda']['events'] = [event('all-day-dates', '2026-10-19', '2026-10-20'),
            event('all-day-flag', '2026-10-19T00:00:00', '2026-10-20T00:00:00', all_day=True),
            event('  🏡 FAMILY TIME ', '2026-10-19', '2026-10-20', all_day=True),
            event('daycare dropoff', '2026-10-19T09:00:00-04:00', '2026-10-19T10:00:00-04:00'),
            event('cancelled', '2026-10-19T09:00:00-04:00', '2026-10-19T10:00:00-04:00', cancelled=True),
            event('declined', '2026-10-19T09:00:00-04:00', '2026-10-19T10:00:00-04:00', declined=True),
            event('free-tentative', '2026-10-19T09:00:00-04:00', '2026-10-19T10:00:00-04:00', free=True, tentative=True)]
        self.assert_today(data, ['all-day-dates', 'all-day-flag', 'free-tentative'])
        page = ReportSurface(render(data))
        text = page.visible_text(page.by_id['today'])
        self.assertIn('All day', text)
        self.assertIn('free', text)
        self.assertIn('tentative', text)
        calendar = render_calendar(data, read_only=True)
        self.assertNotIn('FAMILY TIME', calendar)
        self.assertNotIn('daycare dropoff', calendar)
        self.assertNotIn('cancelled', calendar)
        self.assertNotIn('declined', calendar)

    def test_malformed_missing_naive_and_nonpositive_times_are_not_display_evidence(self):
        data = snapshot()
        data['agenda']['events'] = [event('broken', 'bad', 'bad'), event('null', None, None),
            event('numeric', 123, 456), event('naive', '2026-10-19T09:00:00', '2026-10-19T10:00:00'),
            event('zero', '2026-10-19T09:00:00Z', '2026-10-19T09:00:00Z'),
            event('backward', '2026-10-19T15:00:00Z', '2026-10-19T14:00:00Z'),
            {'id': 'missing', 'title': 'missing', 'time': '09:00–10:00'}]
        self.assert_today(data, [])
        data['availability'] = dict(status='complete', checked_at=data['collected_at'], busy=[dict(start='bad', end='bad')])
        self.assertEqual(suggest(data)['status'], 'unverified')

    def test_hidden_full_day_busy_still_rejects_saves_and_retains_local_choices(self):
        data = snapshot('06:00')
        data['agenda']['events'] = [event('early-private', '2026-10-19T06:00:00-04:00', '2026-10-19T08:00:00-04:00'),
                                    event('late-private', '2026-10-19T19:00:00-04:00', '2026-10-19T21:00:00-04:00')]
        data['availability'] = dict(status='complete', checked_at=data['collected_at'], coverage='Full day',
            coverage_start='2026-10-19T00:00:00-04:00', coverage_end='2026-10-20T00:00:00-04:00', busy=[])
        data['submitted_plan'] = dict(date='2026-10-19', timezone='America/Toronto', submitted_at=data['collected_at'],
                                     blocks=[dict(kind='dog_walk', start=19*60, minutes=30)])
        before = deepcopy(data)
        self.assertTrue(today_rows(data)[0]['_local_plan'])
        self.assertIn('Overlaps calendar', ReportSurface(render(data)).visible_text())
        model = calendar_data(data)
        self.assertEqual([(row['start'], row['end']) for row in model['fixed']], [(360, 480), (1140, 1260)])
        self.assertTrue(all(row['anonymous'] and row['label'] == 'Busy' for row in model['fixed']))
        self.assertEqual(next(row['start'][11:16] for row in suggest(data)['suggestions'] if row['kind'] == 'dog_walk'), '08:00')
        for start in (360, 1140):
            with self.assertRaisesRegex(PlanError, 'overlaps a calendar event'):
                validate_plan(data, dict(date='2026-10-19', timezone='America/Toronto', blocks=[dict(kind='dog_walk', start=start, minutes=30)]))
        for read_only in (False, True):
            page = ReportSurface(render_calendar(data, read_only=read_only))
            self.assertFalse(any('day-fixed' in node['attrs'].get('class', '').split() for node in page.elements()))
        self.assertEqual(data, before)

    def test_live_http_projects_existing_snapshot_without_rewriting_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            day = datetime.now(ZoneInfo('America/Toronto')).date()
            data = snapshot(day=str(day))
            zone = ZoneInfo(data['report']['timezone'])
            data['collected_at'] = datetime.combine(day, time(9), zone).isoformat()
            data['agenda']['events'] = [event(name, datetime.combine(day, time(hour), zone).isoformat(),
                datetime.combine(day, time(hour+1), zone).isoformat()) for name, hour in [('early', 6), ('inside', 10), ('late', 19)]]
            published = publish(root, data, 'morning-coffee')
            path = Path(published['snapshot'])
            self.assertEqual(len(json.loads(path.read_text())['agenda']['events']), 3)
            # Simulate an immutable HTML archive produced before this display rule.
            Path(published['html']).write_text('<html>Historical early and late events</html>')
            open_workspace(root, path)
            before = {item: item.read_bytes() for item in root.rglob('*') if item.is_file()}
            token = 'synthetic-calendar-window-' + 'x' * 32
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(data, root, token, workspace=True))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                connection.request('GET', '/report/' + token)
                response = connection.getresponse()
                markup = response.read().decode()
                connection.close()
                self.assertEqual(response.status, 200)
                page = ReportSurface(markup)
                text = page.visible_text(page.by_id['today'])
                self.assertIn('inside', text)
                self.assertNotIn('early', text)
                self.assertNotIn('late', text)
                selected = select_report(root, str(day), str(zone))
                self.assertEqual(selected['html'], published['html'])
                self.assertEqual({item: item.read_bytes() for item in before}, before)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
