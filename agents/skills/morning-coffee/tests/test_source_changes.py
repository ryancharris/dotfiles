"""Regression for collector/schema drift overwhelming the actual refresh summary."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from test_report_history import ReportSurface, snapshot
from render_brief import workspace_changes
from report_history import changes, publish


class SourceChangeTests(unittest.TestCase):
    def display(self, current, previous):
        current = deepcopy(current)
        current['workspace'] = {}
        current['updates'] = {'since': previous['collected_at'], 'items': changes(current, previous)}
        return ReportSurface(workspace_changes(current))

    def test_schema_prose_case_and_hydration_noise_are_not_source_events(self):
        before = snapshot()
        before['reviews']['items'][0].update(mergeStateStatus='UNKNOWN',
            readiness={'status': 'unknown', 'facts': 'unknown — GitHub is still calculating'})
        after = deepcopy(before)
        pr = after['reviews']['items'][0]
        pr.update(mergeStateStatus='BEHIND', readiness={'status': 'PENDING', 'facts': 'MERGEABLE · BEHIND'},
                  summary='A rewritten summary', effort={**pr['effort'], 'driver': 'Reworded driver'})
        # Same numbers, different order and an extra derived field: the real failure.
        pr['ci'] = dict(state='FAILING', **dict(reversed(list(pr['ci'].items()))), unknown=0)
        after['priorities'][0]['status'] = 'open'  # Absent already means open.
        after['rfcs']['items'][0].update(relationship='A longer explanation of the same uncertainty.',
            approval_status='Assignment remains unknown; one unreadable record.')
        after['oncall']['counts']['active'] += 1
        page = self.display(after, before)
        self.assertIn('hidden', page.by_id['what-changed']['attrs'])
        audit = changes(after, before)
        self.assertTrue(audit, 'The complete comparison remains available as evidence')
        self.assertTrue(all(not row['source_fields'] for row in audit))

    def test_case_and_derived_readiness_changes_are_not_provider_changes(self):
        before = snapshot()
        before['reviews']['items'][0]['readiness']['status'] = 'blocked'
        after = deepcopy(before)
        pr = after['reviews']['items'][0]
        pr.update(reviewDecision='review_required', mergeStateStatus='unstable',
                  readiness={'status': 'PENDING', 'facts': 'Different collector classification'})
        self.assertIn('hidden', self.display(after, before).by_id['what-changed']['attrs'])

    def test_real_check_failure_survives_simultaneous_unknown_mergeability(self):
        before = snapshot()
        after = deepcopy(before)
        after['reviews']['items'][0]['mergeStateStatus'] = 'UNKNOWN'
        after['reviews']['items'][0]['ci'].update(passing=1, failing=2)
        page = self.display(after, before)
        text = page.visible_text()
        self.assertNotIn('hidden', page.by_id['what-changed']['attrs'])
        self.assertIn('2 failing', text)
        self.assertNotIn('UNKNOWN', text)

    def test_verified_conflict_clear_and_approval_remain_visible(self):
        before = snapshot()
        before['reviews']['items'][0]['mergeStateStatus'] = 'DIRTY'
        after = deepcopy(before)
        after['reviews']['items'][0].update(mergeStateStatus='CLEAN', reviewDecision='APPROVED')
        text = self.display(after, before).visible_text()
        self.assertIn('Review decision: REVIEW_REQUIRED → APPROVED', text)
        self.assertIn('Merge status: DIRTY → CLEAN', text)
        self.assertIn('example-fixture#42', text)

    def test_same_calendar_instant_in_another_offset_is_not_a_move(self):
        before = snapshot()
        after = deepcopy(before)
        event = after['agenda']['events'][0]
        event.update(start='2026-10-19T14:30:00Z', end='2026-10-19T15:00:00Z', time='Different display wording')
        before['agenda']['events'][0].update(start='2026-10-19T10:30:00-04:00', end='2026-10-19T11:00:00-04:00')
        self.assertIn('hidden', self.display(after, before).by_id['what-changed']['attrs'])

    def test_structured_rfc_decision_without_rewritten_prose_is_detected(self):
        before = snapshot()
        before['rfcs']['items'][0]['approvals'] = [{'url': 'https://example.com/approval/1',
            'status': 'Acknowledge and reviewing', 'scope': 'Transport', 'checked_at': before['collected_at']}]
        after = deepcopy(before)
        after['rfcs']['items'][0]['approvals'][0].update(status='Accept', checked_at=after['collected_at'])
        text = self.display(after, before).visible_text()
        self.assertIn('Transport review: Acknowledge and reviewing → Accept', text)
        self.assertNotIn('Approved by you', text)
        after['rfcs']['items'][0]['approvals'][0]['status'] = 'unavailable'
        self.assertIn('hidden', self.display(after, before).by_id['what-changed']['attrs'])

    def test_resolution_requires_matching_evidence_and_keeps_actual_outcome(self):
        before = snapshot()
        after = deepcopy(before)
        pr = after['reviews']['items'].pop()
        record = {'section': 'reviews', 'id': pr['url'], 'verified': True, 'outcome': 'merged',
                  'evidence': {'links': [{'label': 'PR', 'url': pr['url']}]}}
        after['resolutions'] = [record]
        row = changes(after, before)[0]
        self.assertEqual((row['status'], row['url'], row['resolution_outcome']), ('Resolved', pr['url'], 'merged'))
        self.assertIn('— merged', self.display(after, before).visible_text())
        record['evidence']['links'][0]['url'] = 'https://example.com/unrelated'
        self.assertIn('hidden', self.display(after, before).by_id['what-changed']['attrs'])

    def test_unknown_queue_removals_stay_in_audit_without_false_completion(self):
        before = snapshot()
        after = deepcopy(before)
        after['reviews']['items'] = []
        self.assertEqual(changes(after, before)[0]['status'], 'No longer listed')
        self.assertIn('hidden', self.display(after, before).by_id['what-changed']['attrs'])

    def test_default_summary_is_bounded_and_all_real_changes_stay_accessible(self):
        before = snapshot()
        after = deepcopy(before)
        for n in range(6):
            after['reviews']['items'].append(dict(deepcopy(after['reviews']['items'][0]),
                number=n + 100, url=f'https://example.com/pr/{n}', title=f'New review {n}'))
        page = self.display(after, before)
        visible = page.visible_text()
        self.assertEqual(visible.count('Newly listed:'), 3)
        self.assertIn('3 more source changes', visible)
        details = page.by_id['what-changed-more']
        self.assertEqual(len([n for n in page.elements(details) if n['tag'] == 'li']), 3)

    def test_legacy_audit_handles_ci_schema_noise_and_keeps_real_changes(self):
        data = snapshot()
        data['workspace'] = {}
        noise = {'section': 'Reviews waiting', 'id': 'pr:1', 'title': 'Noise', 'status': 'Updated', 'fields': [
            {'label': 'Readiness', 'before': 'status: unknown; facts: GitHub is still calculating',
             'after': 'status: PENDING; facts: MERGEABLE · BLOCKED'},
            {'label': 'Merge status', 'before': 'UNKNOWN', 'after': 'BLOCKED'},
            {'label': 'Checks', 'before': 'total: 3; passing: 2; failing: 1; pending: 0',
             'after': 'state: FAILING; pending: 0; failing: 1; passing: 2; total: 3; unknown: 0'}]}
        data['updates'] = {'since': data['collected_at'], 'items': [noise]}
        self.assertIn('hidden', ReportSurface(workspace_changes(data)).by_id['what-changed']['attrs'])
        noise['fields'][-1]['after'] = 'total: 3; passing: 1; failing: 2; pending: 0'
        text = ReportSurface(workspace_changes(data)).visible_text()
        self.assertIn('2 failing', text)
        self.assertNotIn('Readiness', text)

    def test_publish_and_render_preserve_audit_and_only_surface_real_source_delta(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = snapshot()
            publish(root, before, 'morning-coffee')
            after = deepcopy(before)
            after['collected_at'] = '2026-10-19T14:00:00-04:00'
            pr = after['reviews']['items'][0]
            pr['ci']['state'] = 'FAILING'
            pr['summary'] = 'The collector wrote a new summary.'
            pr['readiness'] = {'status': 'blocked', 'facts': 'Regenerated readiness text'}
            event = after['agenda']['events'][0]
            event.update(start='2026-10-19T15:00:00-04:00', end='2026-10-19T15:30:00-04:00', time='15:00–15:30')
            result = publish(root, after, 'refresh')
            data = json.loads(Path(result['snapshot']).read_text())
            self.assertEqual(len(data['updates']['items']), 2)
            data['workspace'] = {}
            text = ReportSurface(workspace_changes(data)).visible_text()
            self.assertIn('15:00', text)
            self.assertNotIn('Regenerated', text)
            self.assertNotIn('Synthetic retry fixture', text)


if __name__ == '__main__':
    unittest.main()
