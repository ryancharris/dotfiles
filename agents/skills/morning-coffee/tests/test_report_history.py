"""Behavioral scenarios for the shared Morning Coffee / Tea Time workflow.

Run with --artifacts DIR to keep every scenario's HTML and JSON for review.
All content in these scenarios is explicitly synthetic, never live evidence.
"""
import argparse
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report_history import changes, history, prepare, publish, resolve_date, resolve_root, select_report, SOURCES
from render_brief import render

ARTIFACTS = None


class ReportSurface(HTMLParser):
    """Inspect the default HTML surface, accounting for closed disclosures."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, source):
        super().__init__()
        self.root = {'tag': 'document', 'attrs': {}, 'children': []}
        self.stack = [self.root]
        self.by_id = {}
        self.ancestors = {}
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = {'tag': tag, 'attrs': dict(attrs), 'children': []}
        self.stack[-1]['children'].append(node)
        if node['attrs'].get('id'):
            self.by_id[node['attrs']['id']] = node
            self.ancestors[node['attrs']['id']] = list(self.stack)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]['tag'] == tag:
                del self.stack[index:]
                break

    def handle_data(self, value):
        self.stack[-1]['children'].append(value)

    def visible_text(self, node=None):
        node = self.root if node is None else node
        if isinstance(node, str):
            return node
        if node['tag'] in ('script', 'style') or 'hidden' in node['attrs']:
            return ''
        children = node['children']
        if node['tag'] == 'details' and 'open' not in node['attrs']:
            children = [child for child in children if isinstance(child, dict) and child['tag'] == 'summary']
        return ' '.join(self.visible_text(child) for child in children)

    def closed_ancestors(self, identifier):
        return [node['attrs'].get('id') or '(anonymous details)' for node in self.ancestors[identifier]
                if node['tag'] == 'details' and 'open' not in node['attrs']]

    def elements(self, node=None):
        node = self.root if node is None else node
        if isinstance(node, str):
            return
        yield node
        for child in node['children']:
            yield from self.elements(child)


def snapshot(time='09:00', day='2026-10-19'):
    collected = f'{day}T{time}:00-04:00'
    evidence = {'paragraphs': ['Synthetic fixture evidence.'], 'links': [{'label': 'Fixture source', 'url': 'https://example.com/fixture'}]}
    return {
        'schema_version': 1, 'collected_at': collected,
        'report': {'title': 'Morning Coffee', 'page_title': 'Fixture', 'eyebrow': 'Engineering brief',
                   'date': day, 'time': time, 'timezone': 'America/Toronto',
                   'preview_label': 'SYNTHETIC SCENARIO — validation data', 'footer': 'Synthetic validation report. No live work is represented.'},
        'sources': {source: {'status': 'complete', 'checked_at': collected, 'note': 'Synthetic fixture provider.'} for source in SOURCES},
        'coverage': '',
        'priorities': [{'id': 'priority:rollout', 'title': 'Verify fixture rollout', 'context': 'A fixture check is failing.',
                        'action': 'Inspect the failing check.', 'done': 'The fixture check passes.', 'evidence': evidence}],
        'okr': {'label': 'Fixture Transport plan', 'url': 'https://example.com/planning', 'period': 'Fixture quarter'},
        'agenda': {'coverage': 'Synthetic primary calendar', 'events': [
            {'id': 'calendar:primary:event:standup:2026-10-19', 'title': 'Fixture stand-up', 'time': '10:00–10:30',
             'start': f'{day}T10:00:00-04:00', 'end': f'{day}T10:30:00-04:00',
             'url': 'https://example.com/event', 'join_url': 'https://example.com/join', 'join_label': 'Join call'}]},
        'oncall': {'schedule': 'Transport On-Call', 'state': 'Not on call', 'responder': 'Fixture user',
                   'shift_label': 'Next shift', 'shift': 'Tomorrow, 09:00', 'dashboard_url': 'https://example.com/incidents',
                   'counts': {'active': 1, 'triage': 0}, 'note': 'Synthetic incident coverage.'},
        'rfcs': {'window_label': 'Past two weeks', 'database_url': 'https://example.com/rfcs',
                 'coverage_label': 'Fixture RFC coverage', 'coverage': 'Synthetic eligible RFC.', 'items': [
                     {'id': 'RFC-FIXTURE', 'title': 'Fixture queue isolation', 'url': 'https://example.com/rfc/1',
                      'author': 'Fixture author', 'submitted_local': day, 'request_emoji': '👀', 'request_label': 'Optional',
                      'user_approved': False, 'approval_status': 'In review', 'summary': 'Separates fixture queues.',
                      'relationship': 'Fixture infrastructure relevance.', 'next_action': 'Read the fixture proposal.', 'approval_url': ''}]},
        'reviews': {'collected_label': time + ' EDT', 'scopes': [{'label': 'Fixture scope', 'url': 'https://example.com/reviews'}],
                    'authorRoster': {'status': 'complete', 'note': 'Synthetic complete roster.'},
                    'personalReview': {'excludedCount': 0, 'reRequestedCount': 0, 'unknownCount': 0}, 'items': [
                        {'repository': 'dbt-labs/example-fixture', 'number': 42, 'url': 'https://github.com/dbt-labs/example-fixture/pull/42',
                         'title': 'Synthetic retry fixture', 'queue': 'direct', 'teams': [], 'author': {'login': 'fixture-author'},
                         'authorOnTransport': True, 'readiness': {'status': 'BLOCKED', 'facts': 'One fixture check is failing.'},
                         'reviewDecision': 'REVIEW_REQUIRED', 'mergeStateStatus': 'UNSTABLE',
                         'ci': {'passing': 2, 'failing': 1, 'pending': 0, 'total': 3},
                         'effort': {'size': 'S', 'label': 'Low (S)', 'inputs': '2 files, +60/-5, 1 commit', 'driver': 'Localized fixture change.'},
                         'updatedAt': collected, 'summary': 'Adds retry handling to a synthetic fixture.',
                         'changedFiles': 2, 'commitCount': 1, 'additions': 60, 'deletions': 5}]},
        'yesterday': {'date': '2026-10-16', 'coverage': 'Synthetic previous-weekday evidence.',
                      'items': [{'id': 'outcome:fixture', 'title': 'Fixture prepared', 'content': evidence}]},
    }


class HistoryScenarios(unittest.TestCase):
    def test_optional_date_uses_user_timezone_and_validates_iso_day(self):
        from datetime import datetime
        now = datetime.fromisoformat('2026-10-20T01:30:00+00:00')
        self.assertEqual(resolve_date(None, 'America/Toronto', now), '2026-10-19')
        self.assertEqual(resolve_date(None, 'Asia/Tokyo', now), '2026-10-20')
        self.assertEqual(resolve_date('2024-02-29', 'America/Toronto', now), '2024-02-29')
        for value in ('2026-2-01', '2026-02-30', '../2026-10-19', '', 'today'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_date(value, 'America/Toronto', now)

    def test_archive_selection_is_read_only_and_falls_back_within_requested_day(self):
        baseline, _ = self.save(snapshot(), 'morning-coffee')
        latest, _ = self.save(snapshot('14:00'), 'refresh')
        self.save(snapshot(day='2026-10-20'), 'morning-coffee')
        before = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        selected = select_report(self.root, '2026-10-19', 'America/Toronto')
        self.assertEqual(selected['html'], latest['html'])
        self.assertIsNone(select_report(self.root, '2026-10-21', 'America/Toronto')['html'])
        self.assertEqual({path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}, before)
        damaged = json.loads(Path(latest['snapshot']).read_text())
        damaged.pop('agenda')
        Path(latest['snapshot']).write_text(json.dumps(damaged))
        selected = select_report(self.root, '2026-10-19', 'America/Toronto')
        self.assertEqual(selected['html'], baseline['html'])
        self.assertEqual(len(selected['warnings']), 1)

    def test_date_cli_defaults_to_local_today_and_selects_explicit_archive(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        script = Path(__file__).resolve().parents[1] / 'scripts/report_history.py'
        command = [sys.executable, str(script), '--root', str(self.root)]
        result, _ = self.save(snapshot(), 'morning-coffee')
        selected = subprocess.run([*command, 'select', '--timezone', 'America/Toronto', '--date', '2026-10-19'],
                                  check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(selected.stdout)['html'], result['html'])
        expected = datetime.now(ZoneInfo('Pacific/Kiritimati')).date().isoformat()
        selected = subprocess.run([*command, 'select', '--timezone', 'Pacific/Kiritimati'],
                                  check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(selected.stdout)['date'], expected)
        prepared = subprocess.run([*command, 'prepare', '--timezone', 'Pacific/Kiritimati', '--kind', 'morning-coffee'],
                                  check=True, capture_output=True, text=True)
        self.assertEqual(Path(json.loads(prepared.stdout)['directory']).name, expected)
        invalid = subprocess.run([*command, 'select', '--timezone', 'America/Toronto', '--date', '2026-02-30'],
                                 capture_output=True, text=True)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertNotIn('Traceback', invalid.stderr)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(ARTIFACTS or self.temp.name) / self._testMethodName
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp.cleanup()

    def save(self, data, kind):
        result = publish(self.root, data, kind)
        self.assertTrue(Path(result['html']).is_file())
        self.assertIn('SYNTHETIC SCENARIO', Path(result['html']).read_text())
        return result, json.loads(Path(result['snapshot']).read_text())

    def test_01_morning_standalone(self):
        result, data = self.save(snapshot(), 'morning-coffee')
        self.assertEqual(result['kind'], 'morning-coffee')
        self.assertNotIn('updates', data)

    def test_02_tea_without_morning(self):
        self.assertEqual(prepare(self.root, '2026-10-19', 'America/Toronto', 'tea-time')['route'], 'morning-coffee')
        result, data = self.save(snapshot('14:00'), 'tea-time')
        self.assertEqual(result['kind'], 'morning-coffee')
        self.assertIn('no morning brief', data['report']['preview_label'])
        self.assertIsNone(prepare(self.root, '2026-10-19', 'America/Toronto', 'tea-time')['tea'])

    def test_03_morning_then_tea(self):
        baseline, _ = self.save(snapshot(), 'morning-coffee')
        original = Path(baseline['snapshot']).read_bytes()
        current = snapshot('14:00')
        current['reviews']['items'][0]['ci'].update(passing=3, failing=0)
        current['reviews']['items'][0]['readiness'] = {'status': 'READY', 'facts': 'All fixture checks pass.'}
        current['reviews']['items'][0]['mergeStateStatus'] = 'CLEAN'
        current['agenda']['events'][0]['time'] = '15:00–15:30'
        current['agenda']['events'][0]['start'] = '2026-10-19T15:00:00-04:00'
        current['agenda']['events'][0]['end'] = '2026-10-19T15:30:00-04:00'
        result, data = self.save(current, 'tea-time')
        self.assertEqual(result['kind'], 'tea-time')
        self.assertEqual({row['section'] for row in data['updates']['items']}, {'Reviews waiting', 'Today'})
        self.assertEqual(Path(baseline['snapshot']).read_bytes(), original)

    def test_04_repeat_tea_reads_both(self):
        morning, _ = self.save(snapshot(), 'morning-coffee')
        first = snapshot('14:00')
        first['oncall']['counts']['active'] = 2
        tea, _ = self.save(first, 'tea-time')
        second = deepcopy(first)
        second['collected_at'] = '2026-10-19T16:00:00-04:00'
        second['sources'] = snapshot('16:00')['sources']
        second['reviews']['items'] = []
        second['resolutions'] = [{'section': 'reviews', 'id': 'https://github.com/dbt-labs/example-fixture/pull/42',
                                  'verified': True, 'outcome': 'merged', 'detail': 'Merged, verified in synthetic PR evidence.',
                                  'url': 'https://github.com/dbt-labs/example-fixture/pull/42'}]
        _, data = self.save(second, 'tea-time')
        self.assertEqual(data['history']['morning'], morning['snapshot'])
        self.assertEqual(data['history']['tea'], tea['snapshot'])
        self.assertEqual(data['history']['previous'], tea['snapshot'])
        self.assertEqual(len(data['updates']['items']), 1)
        self.assertEqual(data['updates']['items'][0]['status'], 'Resolved')
        self.assertEqual(len(data['updates']['since_morning']), 2)

    def test_05_no_change_and_timestamp_noise(self):
        self.save(snapshot(), 'morning-coffee')
        _, data = self.save(snapshot('14:00'), 'tea-time')
        self.assertEqual(data['updates']['items'], [])

    def test_06_source_outage_retains_context(self):
        self.save(snapshot(), 'morning-coffee')
        failed = snapshot('14:00')
        failed['sources']['github'].update(status='unavailable', note='Synthetic GitHub outage.')
        failed['reviews']['items'] = []
        failed['coverage'] = 'GitHub unavailable — synthetic outage.'
        _, data = self.save(failed, 'tea-time')
        self.assertEqual(len(data['reviews']['items']), 1)
        self.assertIn('Reviews waiting', data['stale_sections'])
        self.assertFalse(any(row['status'] == 'Resolved' for row in data['updates']['items']))

    def test_07_new_day_requires_morning(self):
        self.save(snapshot(), 'morning-coffee')
        self.assertEqual(prepare(self.root, '2026-10-20', 'America/Toronto', 'tea-time')['route'], 'morning-coffee')
        result, _ = self.save(snapshot('14:00', '2026-10-20'), 'tea-time')
        self.assertEqual(result['kind'], 'morning-coffee')
        self.assertEqual(prepare(self.root, '2026-10-19', 'UTC', 'tea-time')['route'], 'morning-coffee')

    def test_08_disappearance_is_not_completion(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        current['rfcs']['items'] = []
        _, data = self.save(current, 'tea-time')
        self.assertEqual(data['updates']['items'][0]['status'], 'No longer listed')

    def test_09_corrupt_history_is_disclosed(self):
        result, _ = self.save(snapshot(), 'morning-coffee')
        Path(result['snapshot']).write_text('{broken')
        plan = prepare(self.root, '2026-10-19', 'America/Toronto', 'tea-time')
        self.assertEqual(plan['route'], 'morning-coffee')
        self.assertEqual(len(plan['warnings']), 1)
        self.save(snapshot('14:00'), 'tea-time')

    def test_10_safe_rendering(self):
        data = snapshot()
        data['priorities'][0]['title'] = '<script>alert(1)</script>'
        data['agenda']['events'][0]['url'] = 'javascript:alert(1)'
        result, _ = self.save(data, 'morning-coffee')
        html = Path(result['html']).read_text()
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('href="javascript:', html)

    def test_11_reject_wrong_day_or_naive_timestamp(self):
        data = snapshot()
        data['collected_at'] = '2026-10-20T14:00:00-04:00'
        with self.assertRaises(ValueError):
            publish(self.root, data, 'morning-coffee')
        data['collected_at'] = '2026-10-19T14:00:00'
        with self.assertRaises(ValueError):
            publish(self.root, data, 'morning-coffee')

    def test_12_morning_rerun_then_tea(self):
        self.save(snapshot(), 'morning-coffee')
        self.save(snapshot('13:00'), 'tea-time')
        morning, _ = self.save(snapshot('14:00'), 'morning-coffee')
        _, data = self.save(snapshot('16:00'), 'tea-time')
        self.assertEqual(data['history']['previous'], morning['snapshot'])
        self.assertEqual(data['updates']['morning_at'], '2026-10-19T14:00:00-04:00')


    def test_13_partial_incidents_keep_verified_counts(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        current['sources']['incidentio']['status'] = 'partial'
        current['oncall']['counts']['active'] = 4
        current['oncall']['state'] = 'Unavailable placeholder'
        current['refreshed_fields'] = {'oncall': ['counts']}
        result, data = self.save(current, 'tea-time')
        self.assertEqual(data['oncall']['counts']['active'], 4)
        self.assertEqual(data['oncall']['state'], 'Not on call')
        self.assertTrue(any(row['section'] == 'On call & incidents' for row in data['updates']['items']))
        self.assertTrue('last verified' in Path(result['html']).read_text(), 'Retained singleton needs a visible verification timestamp')

    def test_14_partial_queue_does_not_revive_resolved_pr(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        current['sources']['github']['status'] = 'partial'
        current['reviews']['items'] = []
        current['resolutions'] = [{'section': 'reviews', 'id': 'https://github.com/dbt-labs/example-fixture/pull/42',
                                  'verified': True, 'outcome': 'merged', 'detail': 'Fixture merged.',
                                  'url': 'https://github.com/dbt-labs/example-fixture/pull/42'}]
        _, data = self.save(current, 'tea-time')
        self.assertEqual(data['reviews']['items'], [])
        self.assertEqual(data['updates']['items'][0]['status'], 'Resolved')

    def test_15_malformed_metadata_is_recoverable(self):
        result, data = self.save(snapshot(), 'morning-coffee')
        data['history']['created_at'] = None
        Path(result['snapshot']).write_text(json.dumps(data))
        plan = prepare(self.root, '2026-10-19', 'America/Toronto', 'tea-time')
        self.assertEqual(plan['route'], 'morning-coffee')
        self.assertEqual(len(plan['warnings']), 1)
        recovered, _ = self.save(snapshot('14:00'), 'tea-time')
        self.assertIn('History recovery:', Path(recovered['html']).read_text())

    def test_16_changed_fields_are_visible(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        current['reviews']['items'][0]['summary'] = 'Updated fixture behavior summary.'
        current['rfcs']['items'][0]['user_approved'] = True
        current['priorities'][0]['done'] = 'Updated fixture checkpoint.'
        result, data = self.save(current, 'tea-time')
        fields = [field for row in data['updates']['items'] for field in row['fields']]
        self.assertTrue(all(field['before'] != field['after'] for field in fields))
        html = Path(result['html']).read_text()
        self.assertIn('Updated fixture behavior summary.', html)
        self.assertIn('Updated fixture checkpoint.', html)

    def test_17_reprioritization_is_a_change(self):
        morning = snapshot()
        second = deepcopy(morning['priorities'][0])
        second.update(id='priority:second', title='Second fixture outcome')
        morning['priorities'].append(second)
        self.save(morning, 'morning-coffee')
        current = deepcopy(morning)
        current['collected_at'] = '2026-10-19T14:00:00-04:00'
        current['sources'] = snapshot('14:00')['sources']
        current['priorities'].reverse()
        _, data = self.save(current, 'tea-time')
        self.assertEqual(len(data['updates']['items']), 2)
        self.assertTrue(all(row['fields'][0]['label'] == 'Priority rank' for row in data['updates']['items']))

    def test_18_private_history_and_successful_recovery(self):
        result, _ = self.save(snapshot(), 'morning-coffee')
        self.assertEqual(Path(result['snapshot']).stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(result['html']).stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(result['html']).parent.stat().st_mode & 0o777, 0o700)
        failed = snapshot('14:00')
        failed['sources']['github']['status'] = 'unavailable'
        failed['reviews']['items'] = []
        _, stale = self.save(failed, 'tea-time')
        self.assertEqual(stale['reviews']['items'][0]['_retained_at'], '2026-10-19T09:00:00-04:00')
        _, recovered = self.save(snapshot('16:00'), 'tea-time')
        self.assertNotIn('_retained_at', recovered['reviews']['items'][0])
        self.assertEqual(recovered['stale_sections'], [])

    def test_19_partial_queue_keeps_canonical_order(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        current['sources']['github']['status'] = 'partial'
        new = current['reviews']['items'][0]
        new.update(number=43, url='https://github.com/dbt-labs/example-fixture/pull/43', title='New fixture request')
        _, data = self.save(current, 'tea-time')
        self.assertEqual([row['number'] for row in data['reviews']['items']], [42, 43])

    def test_20_priority_overflow_preserves_unresolved_work(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        base = current['priorities'][0]
        current['priorities'] = []
        for number in range(4):
            item = deepcopy(base)
            item.update(id='new:' + str(number), title='New fixture outcome ' + str(number))
            current['priorities'].append(item)
        current['sources']['slack']['status'] = 'unavailable'
        result, data = self.save(current, 'tea-time')
        self.assertEqual(len(data['priorities']), 4)
        self.assertEqual(data['unverified_priorities'][0]['id'], 'priority:rollout')
        self.assertIn('Earlier priorities to recheck', Path(result['html']).read_text())


    def test_21_resolution_survives_later_refresh(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        current['reviews']['items'] = []
        current['resolutions'] = [{'section': 'reviews', 'id': 'https://github.com/dbt-labs/example-fixture/pull/42',
                                  'verified': True, 'outcome': 'merged', 'detail': 'Fixture merged.',
                                  'url': 'https://github.com/dbt-labs/example-fixture/pull/42'}]
        self.save(current, 'tea-time')
        later = snapshot('16:00')
        later['reviews']['items'] = []
        _, data = self.save(later, 'tea-time')
        self.assertEqual(data['updates']['items'], [])
        self.assertEqual(data['updates']['since_morning'][0]['status'], 'Resolved')
        self.assertEqual(data['resolutions'][0]['verified_at'], '2026-10-19T14:00:00-04:00')


    def availability(self, data, busy=None, start='09:00', end='17:00', status='complete'):
        busy = busy or []
        # Displayed fixture meetings must also be represented in scheduling evidence.
        data['agenda']['events'] = [event for event in data['agenda']['events']
                                    if any(interval['start'] <= event['start'] and interval['end'] >= event['end'] for interval in busy)]
        data['availability'] = {'status': status, 'checked_at': data['collected_at'],
                                'coverage': 'Synthetic primary-only calendar, including anonymous hidden events.',
                                'window_start': start, 'window_end': end, 'busy': busy}
        return data

    def test_22_configurable_retention(self):
        config_root = self.root / 'settings'
        config = config_root / 'engineering-briefs/config.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'report_dir': str(self.root / 'saved reports')}))
        env = {'XDG_CONFIG_HOME': str(config_root), 'XDG_STATE_HOME': str(self.root / 'state')}
        self.assertEqual(resolve_root(environ=env), self.root / 'saved reports')
        env['ENGINEERING_BRIEFS_DIR'] = str(self.root / 'env reports')
        self.assertEqual(resolve_root(environ=env), self.root / 'env reports')
        self.assertEqual(resolve_root(self.root / 'override', env), self.root / 'override')
        env.pop('ENGINEERING_BRIEFS_DIR')
        config.unlink()
        self.assertEqual(resolve_root(environ=env), Path.home() / 'daily-briefs')

    def test_23_compact_tea_preserves_every_change(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        original = current['reviews']['items'][0]
        current['reviews']['items'] = []
        for number in range(100, 115):
            item = deepcopy(original)
            item.update(number=number, url='https://github.com/dbt-labs/example-fixture/pull/' + str(number), title='Synthetic new request ' + str(number))
            current['reviews']['items'].append(item)
        result, data = self.save(current, 'tea-time')
        from html.parser import HTMLParser
        class Inspector(HTMLParser):
            def __init__(self):
                super().__init__(); self.details = {}
            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == 'details' and values.get('id'):
                    self.details[values['id']] = values
        html = Path(result['html']).read_text()
        parsed = Inspector(); parsed.feed(html)
        self.assertIn('full-context', parsed.details)
        self.assertNotIn('open', parsed.details['full-context'])
        self.assertEqual(len(data['updates']['items']), 16)
        self.assertIn('TL;DR', html)
        self.assertNotIn('class="more-changes"', html)
        self.assertTrue(all(item['title'] in html for item in current['reviews']['items']))
        self.assertIn('body class="tea"', html)
        self.assertIn('🫖', html)

    def test_24_coffee_suggests_exercise_and_focus(self):
        current = self.availability(snapshot(), [{'start': '2026-10-19T10:00:00-04:00', 'end': '2026-10-19T10:30:00-04:00'}])
        result, data = self.save(current, 'morning-coffee')
        plan = data['day_plan']
        self.assertEqual(plan['status'], 'suggested')
        self.assertEqual({slot['kind']: slot['minutes'] for slot in plan['suggestions']}, {'focus': 120, 'exercise': 60, 'dog_walk': 30, 'lunch': 30})
        self.assertTrue(all(left['end'] <= right['start'] for left,right in zip(plan['suggestions'],plan['suggestions'][1:])))
        self.assertIn('focus-exercise', Path(result['html']).read_text())
        self.assertIn('day-calendar', Path(result['html']).read_text())

    def test_25_fragmented_day_does_not_invent_focus(self):
        current = self.availability(snapshot(), [
            {'start': '2026-10-19T10:30:00-04:00', 'end': '2026-10-19T11:00:00-04:00'},
            {'start': '2026-10-19T12:30:00-04:00', 'end': '2026-10-19T13:00:00-04:00'},
            {'start': '2026-10-19T14:30:00-04:00', 'end': '2026-10-19T15:00:00-04:00'},
            {'start': '2026-10-19T16:30:00-04:00', 'end': '2026-10-19T17:00:00-04:00'}])
        _, data = self.save(current, 'morning-coffee')
        self.assertEqual(data['day_plan']['status'], 'insufficient')
        self.assertTrue(any(slot['kind']=='exercise' for slot in data['day_plan']['suggestions']))
        self.assertFalse(any(slot['kind']=='focus' for slot in data['day_plan']['suggestions']))

    def test_26_partial_availability_withholds_blocks(self):
        _, data = self.save(self.availability(snapshot(), status='partial'), 'morning-coffee')
        self.assertEqual(data['day_plan']['status'], 'unverified')
        self.assertEqual(data['day_plan']['suggestions'], [])

    def test_27_hidden_busy_and_all_day_boundaries(self):
        # Anonymous intervals include otherwise undisplayed events.
        current = self.availability(snapshot(), [{'start': '2026-10-19', 'end': '2026-10-20'}])
        _, data = self.save(current, 'morning-coffee')
        self.assertEqual(data['day_plan']['suggestions'], [])
        previous_day = self.availability(snapshot(), [{'start': '2026-10-18', 'end': '2026-10-19'}])
        result = publish(self.root / 'exclusive-end', previous_day, 'morning-coffee')
        self.assertEqual(json.loads(Path(result['snapshot']).read_text())['day_plan']['status'], 'suggested')

    def test_28_remaining_day_and_check_time(self):
        current = self.availability(snapshot('09:00'))
        current['availability']['checked_at'] = '2026-10-19T16:00:00-04:00'
        _, data = self.save(current, 'morning-coffee')
        self.assertTrue(all(slot['start'] >= '2026-10-19T16:00:00-04:00' for slot in data['day_plan']['suggestions']))
        self.assertEqual([slot['kind'] for slot in data['day_plan']['suggestions']], ['exercise'])

    def test_29_pair_search_avoids_greedy_conflict(self):
        current = self.availability(snapshot(), [{'start': '2026-10-19T11:00:00-04:00', 'end': '2026-10-19T12:00:00-04:00'},
                                                {'start': '2026-10-19T13:00:00-04:00', 'end': '2026-10-19T17:00:00-04:00'}])
        _, data = self.save(current, 'morning-coffee')
        self.assertEqual(data['day_plan']['status'], 'insufficient')
        slots = {slot['kind']: slot for slot in data['day_plan']['suggestions']}
        self.assertEqual(slots['focus']['start'], '2026-10-19T09:00:00-04:00')
        self.assertEqual(slots['exercise']['start'], '2026-10-19T12:00:00-04:00')

    def test_30_invalid_configuration_is_explicit(self):
        config_root = self.root / 'settings'
        config = config_root / 'engineering-briefs/config.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'report_dir': 'relative/path'}))
        with self.assertRaises(ValueError):
            resolve_root(environ={'XDG_CONFIG_HOME': str(config_root)})

    def test_31_day_plan_updates_in_tea(self):
        self.save(self.availability(snapshot()), 'morning-coffee')
        _, data = self.save(self.availability(snapshot('16:00')), 'tea-time')
        updates = [row for row in data['updates']['items'] if row['section'] == 'Focus & exercise']
        self.assertEqual(updates, [])


    def test_32_tea_leads_with_unfinished_work(self):
        current = snapshot()
        completed = deepcopy(current['priorities'][0])
        completed.update(id='finished', title='Already completed fixture', status='completed')
        current['priorities'].insert(0, completed)
        self.save(current, 'morning-coffee')
        current['collected_at'] = '2026-10-19T14:00:00-04:00'
        current['sources'] = snapshot('14:00')['sources']
        result, data = self.save(current, 'tea-time')
        from render_brief import render_focus
        focus = render_focus(data, True)
        self.assertNotIn('Already completed fixture', focus)
        self.assertIn('Verify fixture rollout', focus)
        html = Path(result['html']).read_text()
        self.assertLess(html.index('id="current-focus"'), html.index('id="what-changed"'))
        self.assertIn('read-only', html)
        self.assertNotIn('id="day-time-', html)

    def test_33_change_summary_does_not_grow_into_a_log(self):
        from render_brief import render_updates
        current = snapshot()
        current['updates'] = {'since': current['collected_at'], 'previous_kind': 'morning-coffee',
                              'morning_at': current['collected_at'], 'since_morning': [],
                              'items': [{'section': 'Reviews waiting', 'title': 'A fixture change ' + str(number),
                                         'status': 'Updated', 'importance': 5, 'fields': []} for number in range(100)]}
        summary = render_updates(current)
        self.assertLess(len(summary.split()), 80)
        self.assertNotIn('A fixture change', summary)
        self.assertIn('100 review updates', summary)
        self.assertNotIn('<details', summary)


    def test_34_tea_finds_new_work_outside_coffee(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        new_review = deepcopy(current['reviews']['items'][0])
        new_review.update(number=43, url='https://github.com/dbt-labs/example-fixture/pull/43', title='New afternoon review')
        current['reviews']['items'].append(new_review)
        new_event = deepcopy(current['agenda']['events'][0])
        new_event.update(id='calendar:afternoon:new', title='New afternoon decision', url='https://example.com/event/new')
        current['agenda']['events'].append(new_event)
        new_rfc = deepcopy(current['rfcs']['items'][0])
        new_rfc.update(id='RFC-NEW', title='New infrastructure decision', url='https://example.com/rfc/new')
        current['rfcs']['items'].append(new_rfc)
        result, data = self.save(current, 'tea-time')
        new_rows = [row for row in data['updates']['since_morning'] if row['status']=='New']
        self.assertEqual({row['section'] for row in new_rows}, {'Reviews waiting', 'Today', 'RFCs to review'})
        html = Path(result['html']).read_text()
        self.assertIn('New since Coffee:', html)
        self.assertIn('read-only', html)
        self.assertNotIn('id="day-time-', html)
        current['collected_at'] = '2026-10-19T16:00:00-04:00'
        current['sources'] = snapshot('16:00')['sources']
        repeated, data = self.save(current, 'tea-time')
        self.assertEqual(data['updates']['items'], [])
        self.assertEqual(len([row for row in data['updates']['since_morning'] if row['status']=='New']), 3)
        self.assertIn('New since Coffee:', Path(repeated['html']).read_text())

    def test_35_tea_questions_require_actual_validation_attempts(self):
        from status_confirmation import pending_checks, render_confirmation_questions
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        current['status_checks'] = [
            {'section': 'priorities', 'id': 'priority:rollout', 'title': 'Fixture rollout',
             'outcome': 'uncertain', 'question': 'Completed, in progress, blocked, or deferred?',
             'attempts': [{'source': 'GitHub', 'method': 'Read linked run and issue',
                           'checked_at': current['collected_at'], 'result': 'Run passed; acceptance decision is not recorded.'}]},
            {'section': 'priorities', 'id': 'unchecked', 'title': 'No checks yet',
             'outcome': 'uncertain', 'question': 'Done?', 'attempts': []},
            {'section': 'priorities', 'id': 'verified', 'title': 'Known complete',
             'outcome': 'verified', 'question': 'Must not ask this',
             'attempts': [{'source': 'GitHub', 'method': 'Read issue', 'checked_at': current['collected_at'], 'result': 'Closed.'}]},
        ]
        self.assertEqual(len(pending_checks(current)), 1)
        questions = render_confirmation_questions(current)
        self.assertNotIn('No checks yet', questions)
        self.assertNotIn('Must not ask this', questions)
        self.assertIn('Run passed', questions)
        result, _ = self.save(current, 'tea-time')
        html = Path(result['html']).read_text()
        self.assertLess(html.index('id="current-focus"'), html.index('id="status-confirmation"'))
        self.assertIn('Completed, in progress, blocked, or deferred?', html)
        # A later Tea cannot reuse earlier failed checks as a fresh reason to ask.
        current['updates'] = {'since': '2026-10-19T15:00:00-04:00'}
        self.assertEqual(pending_checks(current), [])

    def test_36_calendar_session_capability_is_not_archived(self):
        current = snapshot()
        current['calendar_confirmation'] = {'endpoint': 'http://127.0.0.1:1234', 'token': 'ephemeral-secret-test'}
        current['plan_submission'] = {'endpoint': 'http://127.0.0.1:1234/submit', 'token': 'ephemeral-local-save-test'}
        result, data = self.save(current, 'morning-coffee')
        self.assertNotIn('calendar_confirmation', data)
        self.assertNotIn('plan_submission', data)
        self.assertNotIn('ephemeral-secret-test', Path(result['html']).read_text())
        self.assertNotIn('ephemeral-local-save-test', Path(result['html']).read_text())

    def test_37_tea_reads_latest_local_submission_after_coffee(self):
        from datetime import datetime
        from plan_submission import save_plan
        current = self.availability(snapshot())
        coffee, _ = self.save(current, 'morning-coffee')
        request = {'date': current['report']['date'], 'timezone': current['report']['timezone'],
                   'blocks': [{'kind': 'focus', 'start': 630, 'minutes': 120},
                              {'kind': 'lunch', 'start': 750, 'minutes': 30}]}
        save_plan(self.root, current, request, now=datetime.fromisoformat('2026-10-19T09:15:00-04:00'))
        _, tea = self.save(self.availability(snapshot('14:00')), 'tea-time')
        self.assertEqual(tea['submitted_plan']['blocks'], request['blocks'])
        self.assertNotIn('submitted_plan', json.loads(Path(coffee['snapshot']).read_text()))
        request['blocks'] = [{'kind': 'dog_walk', 'start': 960, 'minutes': 30}]
        saved = save_plan(self.root, current, request, now=datetime.fromisoformat('2026-10-19T14:15:00-04:00'))
        prep = prepare(self.root, '2026-10-19', 'America/Toronto', 'tea-time')
        self.assertEqual(prep['submitted_plan'], saved['path'])
        result, tea = self.save(self.availability(snapshot('16:00')), 'tea-time')
        self.assertEqual(tea['submitted_plan']['blocks'], request['blocks'])
        self.assertTrue(tea['updates']['plan_changed'])
        html = Path(result['html']).read_text()
        self.assertIn('Your submitted plan changed.', html)
        self.assertNotIn('id="day-time-', html)

    def test_38_coffee_is_a_visible_complete_daily_overview(self):
        current = self.availability(snapshot(), [{'start': '2026-10-19T10:00:00-04:00', 'end': '2026-10-19T10:30:00-04:00'}])
        prototype = current['priorities'][0]
        for index in range(2, 6):
            row = deepcopy(prototype)
            row.update(id='priority:fixture:' + str(index), title='Fixture outcome ' + str(index),
                       action='Take fixture action ' + str(index) + '.', done='Fixture acceptance ' + str(index) + '.')
            current['priorities'].append(row)
        result, data = self.save(current, 'morning-coffee')
        page = ReportSurface(Path(result['html']).read_text())
        for identifier in ('daily-priorities', 'focus-exercise', 'today', 'on-call',
                           'rfcs-to-review', 'reviews-waiting', 'yesterday'):
            with self.subTest(section=identifier):
                self.assertIn(identifier, page.by_id)
                self.assertEqual(page.closed_ancestors(identifier), [], 'Core daily context must not need a disclosure click')
        visible = page.visible_text()
        for row in data['priorities']:
            with self.subTest(priority=row['id']):
                self.assertIn(row['title'], visible)
                self.assertIn(row['action'], visible)
                self.assertIn(row['done'], visible)
        self.assertNotIn('quarterly-plan', page.by_id)
        self.assertIn(current['agenda']['events'][0]['title'], visible)
        self.assertIn(current['oncall']['state'], visible)
        self.assertIn(current['oncall']['shift'], visible)
        self.assertIn(current['rfcs']['items'][0]['next_action'], visible)
        self.assertIn(current['reviews']['items'][0]['title'], visible)
        self.assertIn(current['yesterday']['items'][0]['title'], visible)

    def test_39_tea_visible_snapshot_covers_the_whole_day(self):
        from datetime import datetime
        from plan_submission import save_plan
        morning = self.availability(snapshot(), [{'start': '2026-10-19T10:00:00-04:00', 'end': '2026-10-19T10:30:00-04:00'}])
        self.save(morning, 'morning-coffee')
        request = {'date': morning['report']['date'], 'timezone': morning['report']['timezone'],
                   'blocks': [{'kind': 'focus', 'start': 630, 'minutes': 120},
                              {'kind': 'lunch', 'start': 750, 'minutes': 30}]}
        save_plan(self.root, morning, request, now=datetime.fromisoformat('2026-10-19T09:15:00-04:00'))
        current = deepcopy(morning)
        current['collected_at'] = '2026-10-19T14:00:00-04:00'
        current['sources'] = snapshot('14:00')['sources']
        current['availability']['checked_at'] = current['collected_at']
        current['rfcs']['items'][0]['next_action'] = 'Waiting on Cole.'
        result, data = self.save(current, 'tea-time')
        html = Path(result['html']).read_text()
        page = ReportSurface(html)
        self.assertIn('day-overview', page.by_id)
        self.assertEqual(page.closed_ancestors('day-overview'), [])
        overview = page.by_id['day-overview']
        cards = [node for node in page.elements(overview) if 'check-in-card' in node['attrs'].get('class', '').split()]
        self.assertEqual(len(cards), 5, 'The requested context domains need a visible check-in')
        destinations = {node['attrs'].get('href') for node in page.elements(overview) if node['tag'] == 'a'}
        expected = {'#reviews-waiting', '#rfcs-to-review', '#on-call', '#today', '#yesterday'}
        self.assertTrue(expected.issubset(destinations))
        for destination in destinations:
            if destination and destination.startswith('#'):
                self.assertIn(destination[1:], page.by_id, 'Overview link must reveal an actual report section')
        visible = page.visible_text(overview)
        for text in (current['reviews']['items'][0]['title'], current['rfcs']['items'][0]['title'],
                     current['rfcs']['items'][0]['next_action'], current['oncall']['state'],
                     current['yesterday']['items'][0]['title']):
            with self.subTest(text=text):
                self.assertIn(text, visible)
        self.assertLess(html.index('id="current-focus"'), html.index('id="day-overview"'))
        self.assertLess(html.index('id="what-changed"'), html.index('id="day-overview"'))
        self.assertEqual(data['submitted_plan']['blocks'], request['blocks'])
        self.assertIn('read-only', html)
        self.assertNotIn('id="day-time-', html)
        self.assertNotIn('plan-submit-button', html.split('<main>', 1)[1].split('</main>', 1)[0])
        self.assertNotIn('completed', data['submitted_plan'], 'Elapsed chosen blocks are not completion evidence')

    def test_40_tea_snapshot_marks_retained_context_where_it_is_shown(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        current['sources']['github'].update(status='unavailable', note='Synthetic GitHub outage.')
        current['reviews']['items'] = []
        result, data = self.save(current, 'tea-time')
        page = ReportSurface(Path(result['html']).read_text())
        visible = page.visible_text(page.by_id['day-overview'])
        self.assertIn(data['reviews']['items'][0]['title'], visible)
        self.assertIn('last verified', visible, 'Retained snapshot facts need freshness at their visible point of use')
        self.assertIn('09:00', visible)

    def test_41_tea_shortlists_disclose_full_queue_counts(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        rfc, event = current['rfcs']['items'][0], current['agenda']['events'][0]
        current['rfcs']['items'], current['agenda']['events'] = [], []
        for index in range(7):
            extra_rfc = deepcopy(rfc)
            extra_rfc.update(id='RFC-extra:' + str(index), title='Extra RFC ' + str(index),
                             url='https://example.com/rfc/extra/' + str(index))
            current['rfcs']['items'].append(extra_rfc)
            extra_event = deepcopy(event)
            extra_event.update(id='event:extra:' + str(index), title='Extra event ' + str(index),
                               url='https://example.com/event/extra/' + str(index))
            current['agenda']['events'].append(extra_event)
        result, _ = self.save(current, 'tea-time')
        html = Path(result['html']).read_text()
        page = ReportSurface(html)
        overview = page.visible_text(page.by_id['day-overview'])
        self.assertIn('7 RFCs', overview)
        self.assertRegex(overview, r'7 (?:listed |calendar )?events')
        self.assertNotIn('Extra RFC 6', overview)
        self.assertNotIn('Extra event 6', overview)
        for row in current['rfcs']['items'] + current['agenda']['events']:
            self.assertIn(row['title'], html, 'Shortlisting must not remove any full-context detail')

    def test_42_refresh_creates_missing_baseline_then_keeps_it_immutable(self):
        before = prepare(self.root, '2026-10-19', 'America/Toronto', 'refresh')
        self.assertEqual(before['route'], 'morning-coffee')
        baseline, data = self.save(snapshot(), 'refresh')
        self.assertEqual(baseline['kind'], 'morning-coffee')
        self.assertIn('no morning brief', data['report']['preview_label'])
        original = Path(baseline['snapshot']).read_bytes()
        first, refreshed = self.save(snapshot('14:00'), 'refresh')
        self.assertEqual(first['kind'], 'refresh')
        self.assertEqual(refreshed['report']['title'], 'Morning Coffee')
        self.assertEqual(refreshed['history']['morning'], baseline['snapshot'])
        self.assertEqual(refreshed['history']['previous'], baseline['snapshot'])
        self.assertEqual(Path(baseline['snapshot']).read_bytes(), original)
        prep = prepare(self.root, '2026-10-19', 'America/Toronto', 'refresh')
        self.assertEqual(prep['route'], 'refresh')
        self.assertEqual(prep['morning'], baseline['snapshot'])
        self.assertEqual(prep['refresh'], first['snapshot'])
        self.assertEqual(prep['previous'], first['snapshot'])
        second, repeated = self.save(snapshot('16:00'), 'refresh')
        self.assertEqual(repeated['updates']['previous_kind'], 'refresh')
        self.assertEqual(repeated['history']['previous'], first['snapshot'])
        self.assertEqual(repeated['history']['morning'], baseline['snapshot'])
        self.assertEqual(repeated['updates']['morning_at'], '2026-10-19T09:00:00-04:00')
        self.assertEqual(Path(baseline['snapshot']).read_bytes(), original)
        entries, warnings = history(self.root, '2026-10-19', 'America/Toronto')
        self.assertEqual([row['history']['kind'] for row, path in entries], ['morning-coffee', 'refresh', 'refresh'])
        self.assertEqual(warnings, [])

    def test_history_preparation_renders_only_latest_candidate_per_kind(self):
        self.save(snapshot(), 'morning-coffee')
        for hour in range(10, 22):
            self.save(snapshot(f'{hour:02d}:00'), 'refresh')
        import report_history
        with patch('report_history.render', wraps=render) as render_snapshot:
            plan = prepare(self.root, '2026-10-19', 'America/Toronto', 'refresh')
        self.assertEqual(plan['route'], 'refresh')
        self.assertEqual(render_snapshot.call_count, 2, 'one baseline and one latest refresh, independent of archive length')

    def test_malformed_deep_candidate_warns_and_falls_back(self):
        result, _ = self.save(snapshot(), 'morning-coffee')
        path = Path(result['snapshot'])
        damaged = json.loads(path.read_text())
        damaged.pop('agenda')
        path.write_text(json.dumps(damaged))

        plan = prepare(self.root, '2026-10-19', 'America/Toronto', 'tea-time')
        self.assertEqual(plan['route'], 'morning-coffee')
        self.assertEqual(len(plan['warnings']), 1)
        self.assertIn(path.parent.name, plan['warnings'][0])

        recovered, _ = self.save(snapshot('14:00'), 'tea-time')
        self.assertIn('History recovery:', Path(recovered['html']).read_text())

    def test_43_refresh_uses_latest_legacy_tea_or_refresh_for_comparison(self):
        baseline, _ = self.save(snapshot(), 'morning-coffee')
        tea, _ = self.save(snapshot('12:00'), 'tea-time')
        refreshed, data = self.save(snapshot('14:00'), 'refresh')
        self.assertEqual(data['history']['previous'], tea['snapshot'])
        self.assertEqual(data['history']['tea'], tea['snapshot'])
        self.assertEqual(data['updates']['previous_kind'], 'tea-time')
        later_tea, data = self.save(snapshot('15:00'), 'tea-time')
        self.assertEqual(data['history']['previous'], refreshed['snapshot'])
        final, data = self.save(snapshot('16:00'), 'refresh')
        self.assertEqual(data['history']['previous'], later_tea['snapshot'])
        self.assertEqual(data['history']['morning'], baseline['snapshot'])
        self.assertEqual(data['history']['refresh'], refreshed['snapshot'])
        with self.assertRaisesRegex(ValueError, 'newer'):
            self.save(snapshot('15:30'), 'refresh')

    def test_44_workspace_capabilities_and_private_config_never_enter_history(self):
        self.save(snapshot(), 'morning-coffee')
        current = snapshot('14:00')
        capabilities = ('calendar_confirmation', 'plan_submission', 'plan_removal', 'review_interaction', 'todo_interaction', 'workspace_interaction')
        for key in capabilities:
            current[key] = {'endpoint': 'http://127.0.0.1:1234/' + key, 'token': 'synthetic-session-secret-' + key}
        current['workspace'] = {'refresh': {'id': 'synthetic-request'}, 'webhook_url': 'https://example.com/synthetic-private-webhook',
                                'thread_url': 't3-thread://synthetic-private-thread', 'scheduled_task_id': 'synthetic-private-task'}
        result, archived = self.save(current, 'refresh')
        for key in (*capabilities, 'workspace'):
            self.assertNotIn(key, archived)
        text = Path(result['snapshot']).read_text() + Path(result['html']).read_text()
        for secret in ('synthetic-session-secret', 'synthetic-private-webhook', 'synthetic-private-thread', 'synthetic-private-task'):
            self.assertNotIn(secret, text)
        self.assertIn('id="coffee-context"', Path(result['html']).read_text())
        self.assertEqual(archived['history']['kind'], 'refresh')

    def test_45_refresh_cli_prepare_and_publish(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/report_history.py'
        command = [sys.executable, str(script), '--root', str(self.root)]
        prepared = subprocess.run([*command, 'prepare', '--date', '2026-10-19', '--timezone', 'America/Toronto', '--kind', 'refresh'],
                                  check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(prepared.stdout)['route'], 'morning-coffee')
        source = self.root / 'synthetic-input.json'
        source.write_text(json.dumps(snapshot()))
        created = subprocess.run([*command, 'publish', str(source), '--kind', 'refresh'], check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(created.stdout)['kind'], 'morning-coffee')
        source.write_text(json.dumps(snapshot('14:00')))
        created = subprocess.run([*command, 'publish', str(source), '--kind', 'refresh'], check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(created.stdout)['kind'], 'refresh')


def index_artifacts(root):
    from html import escape
    reports = sorted(root.glob('test_*/**/report.html'))
    sections = []
    for scenario in sorted(root.glob('test_*')):
        links = []
        for report in sorted(scenario.rglob('report.html')):
            try:
                data = json.loads(report.with_name('snapshot.json').read_text())
                label = data['report']['title'] + ' · ' + data['report']['date'] + ' ' + data['report']['time']
            except (ValueError, KeyError):
                label = 'Earlier report · intentionally corrupted history snapshot'
            links.append('<li><a href="' + escape(str(report.relative_to(root)), quote=True) + '">' + escape(label) + '</a></li>')
        title = scenario.name.replace('test_', '', 1).replace('_', ' ')
        sections.append('<section><h2>' + escape(title) + '</h2>' + ('<ul>' + ''.join(links) + '</ul>' if links else '<p>Assertions completed; no report published.</p>') + '</section>')
    (root / 'index.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Brief scenario gallery</title><style>body{background:#282828;color:#ebdbb2;font:17px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 20px}a{color:#d8a657}h2{font-size:19px}section{border-top:1px solid #665c54;padding:12px 0}li{margin:8px 0;overflow-wrap:anywhere}a:focus-visible{outline:3px solid #d8a657;outline-offset:4px}</style></head><body><h1>Morning Coffee &amp; Tea Time</h1><p>' + str(len(sections)) + ' controlled behavioral scenarios · ' + str(len(reports)) + ' HTML reports. All linked reports use synthetic fixture data.</p>' + ''.join(sections) + '</body></html>')
    return len(reports)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', type=Path)
    args, rest = parser.parse_known_args()
    ARTIFACTS = args.artifacts
    result = unittest.main(argv=[sys.argv[0], *rest], exit=False)
    if ARTIFACTS:
        print(f'{index_artifacts(ARTIFACTS)} HTML reports: {ARTIFACTS / "index.html"}')
    sys.exit(not result.result.wasSuccessful())
