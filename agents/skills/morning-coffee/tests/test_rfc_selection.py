"""RFC discovery and publication keep old open reviews and recent activity visible."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_report_history import snapshot, ReportSurface
from report_history import publish
from render_brief import render
from select_rfcs import select, validate_surface

SOURCE = 'collection://aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
NOW = datetime.fromisoformat('2026-11-06T09:00:00-05:00')


def row(number=1, status='In-Review', **extra):
    return {'url': 'https://app.notion.com/p/' + f'{number:032x}', 'Name': 'RFC-' + str(number),
            'RFC Status': status, 'Created time': '2026-08-01T00:00:00Z',
            'Last edited time': '2026-11-05T15:00:00Z',
            'date:Submitted for review:start': '2026-10-01T12:00:00Z', 'Approvals ': '[]', **extra}


def discovery(rows, **extra):
    return {'data_source_url': SOURCE, 'has_more': False, 'expected_count': len(rows), 'rows': rows,
            'checked_at': NOW.isoformat(), **extra}


def surface(selection):
    result = deepcopy(selection)
    template = snapshot()['rfcs']['items'][0]
    result['items'] = [dict(deepcopy(template), **r) for r in selection['items']]
    result.update(database_url='https://app.notion.com/p/' + 'a' * 32,
                  coverage_label='RFC coverage', coverage='Synthetic complete discovery')
    return result


class RfcSelectionTests(unittest.TestCase):
    def test_old_missing_and_future_submission_dates_do_not_hide_open_reviews(self):
        rows = [row(1), row(2, **{'date:Submitted for review:start': None}),
                row(3, **{'date:Submitted for review:start': 'broken'}),
                row(4, **{'date:Submitted for review:start': '2027-01-01'})]
        selected = select(discovery(rows), NOW)
        self.assertEqual({r['url'] for r in selected['items']}, {r['url'] for r in rows})
        self.assertEqual(selected['activity'], [])
        self.assertTrue(selected['discovery']['complete'])
        self.assertEqual(len(selected['warnings']), 3)
        self.assertIn('Submission date unavailable', selected['items'][1]['date_label'])

    def test_recent_drafts_paused_and_terminal_states_are_activity_only(self):
        states = ('Drafting', 'Paused', 'Approved', 'Superseded', 'Obsolete', 'Withdrawn')
        rows = [row(n + 1, status) for n, status in enumerate(states)]
        selected = select(discovery(rows), NOW)
        self.assertEqual(selected['items'], [])
        self.assertEqual({r['lifecycle'] for r in selected['activity']}, set(states))
        validate_surface(selected)

    def test_activity_window_uses_actual_edit_instant_not_submission_or_creation(self):
        rows = [row(1, 'Drafting', **{'Last edited time': '2026-10-23T09:00:00-05:00'}),
                row(2, 'Drafting', **{'Last edited time': '2026-10-23T08:59:59-05:00'}),
                row(3, 'Drafting', **{'Last edited time': '2026-11-06T14:00:01Z'}),
                row(4, 'Drafting', **{'Last edited time': None, 'Created time': NOW.isoformat()}),
                row(5, 'Approved', **{'Last edited time': NOW.isoformat()})]
        selected = select(discovery(rows), NOW)
        self.assertEqual([r['url'] for r in selected['activity']], [rows[4]['url'], rows[0]['url']])

    def test_same_rfc_never_appears_in_both_surfaces(self):
        source = row(1)
        duplicate = dict(source, url=source['url'] + '?pvs=204')
        selected = select(discovery([source, duplicate], expected_count=1), NOW)
        self.assertEqual(len(selected['items']), 1)
        self.assertEqual(selected['activity'], [])
        self.assertEqual(selected['discovery']['discovered_count'], 1)

    def test_conflicting_duplicates_and_wrong_source_are_rejected(self):
        for rows in ([row(1), row(1, 'Drafting')], [row(1, data_source_url='collection://other')]):
            with self.assertRaises(ValueError):
                select(discovery(rows), NOW)

    def test_partial_pagination_count_mismatch_and_unknown_lifecycle_are_explicit(self):
        for changes in ({'has_more': True}, {'expected_count': 2}, {'rows': [row(1, 'New unknown state')]}):
            selected = select({**discovery([row(1)]), **changes}, NOW)
            self.assertFalse(selected['discovery']['complete'])
            self.assertTrue(selected['warnings'])

    def test_bad_approval_metadata_does_not_drop_a_review(self):
        selected = select(discovery([row(1, **{'Approvals ': '{broken'})]), NOW)
        self.assertEqual(len(selected['items']), 1)
        self.assertIsNone(selected['items'][0]['approval_urls'])
        self.assertTrue(selected['warnings'])
        validate_surface(selected)

    def test_date_only_values_and_rich_titles_are_normalized(self):
        selected = select(discovery([row(1, Name='RFC-1: <b>Queue &amp; workers</b>',
                                       **{'date:Submitted for review:start': '2026-11-05'})]), NOW)
        item = selected['items'][0]
        self.assertEqual(item['title'], 'RFC-1: Queue & workers')
        self.assertEqual(item['date_label'], 'Submitted 2026-11-05 00:00')

    def test_manifest_rejects_missing_duplicate_wrong_group_and_changed_lifecycle(self):
        selection = select(discovery([row(1), row(2, 'Drafting')]), NOW)
        validate_surface(selection)
        for kind in ('missing', 'duplicate', 'group', 'lifecycle'):
            data = deepcopy(selection)
            if kind == 'missing': data['items'] = []
            if kind == 'duplicate': data['items'].append(deepcopy(data['items'][0]))
            if kind == 'group': data['activity'].append(data['items'].pop())
            if kind == 'lifecycle': data['items'][0]['lifecycle'] = 'Approved'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_surface(data)

    def test_recent_activity_is_separate_visible_and_has_no_review_save_controls(self):
        data = snapshot()
        data['rfcs'] = surface(select(discovery([row(1), row(2, 'Drafting'), row(3, 'Approved')]), NOW))
        data['rfcs']['activity'][0]['summary'] = '<script>alert(1)</script>'
        for kind in ('morning-coffee', 'tea-time'):
            data['history'] = {'kind': kind}
            page = ReportSurface(render(data))
            activity = page.by_id['rfc-activity']
            self.assertIn('open', activity['attrs'])
            self.assertIn('Drafting', page.visible_text(activity))
            self.assertIn('Approved', page.visible_text(activity))
            self.assertFalse(any('data-local-review' in n['attrs'] for n in page.elements(activity)))
            self.assertFalse(any(n['tag'] == 'script' for n in page.elements(activity)))
            self.assertEqual(sum('data-local-review' in n['attrs'] for n in page.elements(page.by_id['rfcs-to-review'])), 1)

    def test_failed_hydration_placeholder_is_publishable_but_omission_is_not(self):
        data = snapshot(day='2026-11-06')
        data['rfcs'] = surface(select(discovery([row(1), row(2, 'Drafting')]), NOW))
        data['rfcs']['items'][0].update(summary='Proposal content unavailable.', request_label='Request status unknown')
        with tempfile.TemporaryDirectory() as tmp:
            publish(Path(tmp), data, 'morning-coffee')
            data['collected_at'] = '2026-11-06T10:00:00-05:00'
            data['rfcs']['activity'] = []
            before = list(Path(tmp).rglob('snapshot.json'))
            with self.assertRaises(ValueError): publish(Path(tmp), data, 'morning-coffee')
            self.assertEqual(list(Path(tmp).rglob('snapshot.json')), before)

    def test_fresh_lifecycle_discovery_removes_closed_review_despite_partial_notion_approval_reads(self):
        old = snapshot(day='2026-11-06')
        old['rfcs'] = surface(select(discovery([row(1)]), NOW))
        with tempfile.TemporaryDirectory() as tmp:
            first = publish(Path(tmp), old, 'morning-coffee')
            saved_before = Path(first['snapshot']).read_bytes()
            new = deepcopy(old)
            new['collected_at'] = '2026-11-06T10:00:00-05:00'
            new['sources']['notion']['status'] = 'partial'
            new['rfcs'] = surface(select(discovery([row(1, 'Approved')]), NOW))
            second = publish(Path(tmp), new, 'morning-coffee')
            saved = json.loads(Path(second['snapshot']).read_text())
            self.assertEqual(saved['rfcs']['items'], [])
            self.assertEqual(saved['rfcs']['activity'][0]['lifecycle'], 'Approved')
            self.assertEqual(Path(first['snapshot']).read_bytes(), saved_before)

    def test_mixed_offsets_sort_by_instant_for_review_and_activity(self):
        rows = [row(1, 'Drafting', **{'Last edited time': '2026-11-05T14:00:00Z'}),
                row(2, 'Drafting', **{'Last edited time': '2026-11-05T10:00:00-05:00'}),
                row(3, **{'date:Submitted for review:start': '2026-11-05T14:00:00Z'}),
                row(4, **{'date:Submitted for review:start': '2026-11-05T10:00:00-05:00'})]
        selected = select(discovery(rows), NOW)
        self.assertEqual([r['url'] for r in selected['activity']], [rows[1]['url'], rows[0]['url']])
        self.assertEqual([r['url'] for r in selected['items']], [rows[2]['url'], rows[3]['url']])

    def test_partial_discovery_honors_observed_lifecycle_and_retains_unknown_activity(self):
        old = snapshot(day='2026-11-06')
        old['rfcs'] = surface(select(discovery([row(1), row(2, 'Drafting')]), NOW))
        with tempfile.TemporaryDirectory() as tmp:
            publish(Path(tmp), old, 'morning-coffee')
            new = deepcopy(old)
            new['collected_at'] = '2026-11-06T10:00:00-05:00'
            new['sources']['notion']['status'] = 'partial'
            new['rfcs'] = surface(select(discovery([row(1, 'Approved')], expected_count=2, has_more=True), NOW))
            second = publish(Path(tmp), new, 'morning-coffee')
            saved = json.loads(Path(second['snapshot']).read_text())
            self.assertEqual(saved['rfcs']['items'], [])
            self.assertEqual(len(saved['rfcs']['activity']), 2)
            retained = next(r for r in saved['rfcs']['activity'] if r['url'] == row(2)['url'])
            self.assertEqual(retained['_retained_at'], old['collected_at'])
            self.assertIn('RFCs to review', saved['stale_sections'])
            validate_surface(saved['rfcs'])
            # Reusing a partial snapshot must preserve valid retained evidence.
            saved['collected_at'] = '2026-11-06T11:00:00-05:00'
            third = publish(Path(tmp), saved, 'morning-coffee')
            validate_surface(json.loads(Path(third['snapshot']).read_text())['rfcs'])

    def test_partial_discovery_retains_unknown_open_review_with_original_timestamp(self):
        old = snapshot(day='2026-11-06')
        old['rfcs'] = surface(select(discovery([row(1)]), NOW))
        with tempfile.TemporaryDirectory() as tmp:
            publish(Path(tmp), old, 'morning-coffee')
            new = deepcopy(old)
            new['collected_at'] = '2026-11-06T10:00:00-05:00'
            new['sources']['notion']['status'] = 'partial'
            new['rfcs'] = surface(select(discovery([], expected_count=1, has_more=True), NOW))
            saved = json.loads(Path(publish(Path(tmp), new, 'morning-coffee')['snapshot']).read_text())
            self.assertEqual(saved['rfcs']['items'][0]['_retained_at'], old['collected_at'])
            validate_surface(saved['rfcs'])

    def test_unknown_observed_lifecycle_cannot_retire_a_previously_open_review(self):
        old = snapshot(day='2026-11-06')
        old['rfcs'] = surface(select(discovery([row(1)]), NOW))
        with tempfile.TemporaryDirectory() as tmp:
            publish(Path(tmp), old, 'morning-coffee')
            new = deepcopy(old)
            new['collected_at'] = '2026-11-06T10:00:00-05:00'
            # Section discovery takes precedence over an aggregate source flag.
            new['rfcs'] = surface(select(discovery([row(1, 'Unknown new lifecycle')]), NOW))
            saved = json.loads(Path(publish(Path(tmp), new, 'morning-coffee')['snapshot']).read_text())
            self.assertEqual(len(saved['rfcs']['items']), 1)
            self.assertEqual(saved['rfcs']['items'][0]['lifecycle'], 'In-Review')
            self.assertTrue(saved['rfcs']['items'][0]['_retained_at'])
            validate_surface(saved['rfcs'])

    def test_legacy_review_without_lifecycle_survives_partial_discovery(self):
        old = snapshot(day='2026-11-06')
        old['rfcs']['items'][0]['url'] = row(1)['url']
        old['rfcs']['items'][0].pop('lifecycle', None)
        with tempfile.TemporaryDirectory() as tmp:
            publish(Path(tmp), old, 'morning-coffee')
            new = deepcopy(old)
            new['collected_at'] = '2026-11-06T10:00:00-05:00'
            new['rfcs'] = surface(select(discovery([], expected_count=1, has_more=True), NOW))
            saved = json.loads(Path(publish(Path(tmp), new, 'morning-coffee')['snapshot']).read_text())
            self.assertEqual(saved['rfcs']['items'][0]['url'], row(1)['url'])
            self.assertEqual(saved['rfcs']['items'][0]['_retained_at'], old['collected_at'])
            self.assertNotIn('lifecycle', saved['rfcs']['items'][0], 'retention does not fabricate a current lifecycle')
            validate_surface(saved['rfcs'])

    def test_retained_and_fresh_activity_are_ordered_by_actual_edit_time(self):
        old = snapshot(day='2026-11-06')
        old['rfcs'] = surface(select(discovery([row(1, 'Drafting')]), NOW))
        with tempfile.TemporaryDirectory() as tmp:
            publish(Path(tmp), old, 'morning-coffee')
            new = deepcopy(old)
            new['collected_at'] = '2026-11-06T10:00:00-05:00'
            new['rfcs'] = surface(select(discovery([row(2, 'Approved', **{'Last edited time': '2026-11-03T15:00:00Z'})], expected_count=2, has_more=True), NOW))
            saved = json.loads(Path(publish(Path(tmp), new, 'morning-coffee')['snapshot']).read_text())
            self.assertEqual([r['url'] for r in saved['rfcs']['activity']], [row(1)['url'], row(2)['url']])

    def test_cli_selects_all_pages_without_provider_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / 'rows.json', Path(tmp) / 'selection.json'
            source.write_text(json.dumps(discovery([row(1), row(2, 'Drafting')])))
            result = subprocess.run([sys.executable, str(Path(__file__).parents[1] / 'scripts/select_rfcs.py'),
                                     str(source), '--at', NOW.isoformat(), '--timezone', 'America/Toronto', '--output', str(output)],
                                    capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['reviews'], 1)
            self.assertEqual(len(json.loads(output.read_text())['activity']), 1)


if __name__ == '__main__': unittest.main()
