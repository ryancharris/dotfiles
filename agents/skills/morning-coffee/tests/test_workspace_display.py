"""Overview visibility and on-call alerts use only verified timing evidence."""
from copy import deepcopy
from datetime import datetime
import unittest
from test_report_history import ReportSurface, snapshot
from render_brief import render, render_oncall_banner, workspace_changes, local_plan_note


class WorkspaceDisplayTests(unittest.TestCase):
    def test_combined_briefing_precedes_tasks_with_unique_stable_controls(self):
        data = snapshot()
        data['workspace'] = {'suggestions': []}
        data['priorities'].append(dict(data['priorities'][0], id='second-priority', title='Another priority'))
        markup = render(data)
        page = ReportSurface(markup)
        briefing = page.by_id['daily-briefing']
        visible = page.visible_text(briefing)
        self.assertIn('Priorities', visible)
        self.assertIn('Previous weekday', visible)
        self.assertIn('2 chosen priorities', visible)
        self.assertIn(data['yesterday']['items'][0]['title'], visible)
        self.assertLess(markup.index('id="daily-briefing"'), markup.index('id="todos"'))
        self.assertLess(markup.index('id="today"'), markup.index('id="daily-briefing"'))
        self.assertEqual(markup.count('id="yesterday"'), 1)
        ids = [node['attrs']['id'] for node in page.elements() if node['attrs'].get('id', '').startswith('priority-evidence-')]
        self.assertEqual(len(ids), 4)
        self.assertEqual(len(set(ids)), 4)
        data['priorities'].reverse()
        reordered = render(data)
        for identifier in ids:
            self.assertIn('id="' + identifier + '"', reordered)

    def test_briefing_empty_groups_explain_missing_work(self):
        data = snapshot()
        data['workspace'] = {'suggestions': []}
        data['priorities'] = []
        data['yesterday']['items'] = []
        page = ReportSurface(render(data))
        visible = page.visible_text(page.by_id['daily-briefing'])
        self.assertIn('No chosen priorities.', visible)
        self.assertIn('No verified outcomes for ' + data['yesterday']['date'], visible)

    def test_no_suggestions_hides_whole_section_even_with_source_updates(self):
        data = snapshot()
        data['workspace'] = {'suggestions': []}
        data['updates'] = {'items': [], 'since': data['collected_at']}
        section = ReportSurface(workspace_changes(data)).by_id['what-changed']
        self.assertIn('hidden', section['attrs'])
        self.assertEqual(section['children'], [])
        data['workspace']['suggestions'] = [{'id': 'fixture', 'fingerprint': 'f', 'item': {'title': 'New work'}}]
        section = ReportSurface(workspace_changes(data)).by_id['what-changed']
        self.assertNotIn('hidden', section['attrs'])

    def test_only_conflicts_label_saved_blocks(self):
        self.assertEqual(local_plan_note({'_local_plan': True}), '')
        self.assertEqual(local_plan_note({'_local_plan': False, 'conflict': True}), '')
        self.assertIn('Overlaps calendar', local_plan_note({'_local_plan': True, 'conflict': True}))

    def test_incident_cards_and_counts_are_removed(self):
        data = snapshot()
        for tea in (False, True):
            if tea:data['history'] = {'kind': 'tea-time'}
            page = ReportSurface(render(data))
            self.assertIn('hidden', page.by_id['on-call']['attrs'])
            visible = page.visible_text()
            self.assertNotIn('On call & incidents', visible)
            self.assertNotIn('Incidents dashboard', visible)
            self.assertFalse(any(node['attrs'].get('href') == '#on-call' for node in page.elements()))

    def test_upcoming_banner_boundary_uses_full_aware_interval(self):
        data = snapshot()
        now = datetime.fromisoformat('2026-10-19T09:00:00-04:00')
        original = deepcopy(data)
        cases = [
            ({'start': '2026-10-20T09:00:00-04:00', 'end': '2026-10-21T09:00:00-04:00'}, True),
            ({'start': '2026-10-20T09:00:01-04:00', 'end': '2026-10-21T09:00:00-04:00'}, False),
            ({'start': '2026-10-19T09:00:00-04:00', 'end': '2026-10-20T09:00:00-04:00'}, True),
            ({'start': '2026-10-19T08:59:59-04:00', 'end': '2026-10-20T09:00:00-04:00'}, True),
            ({'start': '2026-10-20T09:00:00', 'end': '2026-10-21T09:00:00'}, False),
            ({'start': '2026-10-20T09:00:00-04:00'}, False),
            ({'start': '2026-10-20T09:00:00-04:00', 'end': '2026-10-19T09:00:00-04:00'}, False),
        ]
        for interval, shown in cases:
            with self.subTest(interval=interval):
                data['oncall']['next_shift'] = interval
                section = ReportSurface(render_oncall_banner(data, now)).by_id['on-call']
                self.assertEqual('hidden' not in section['attrs'], shown)
        self.assertEqual(original['oncall']['shift'], data['oncall']['shift'])

    def test_active_interval_and_legacy_current_duty(self):
        data = snapshot()
        data['oncall']['current_shift'] = {'start': '2026-10-19T09:00:00-04:00', 'end': '2026-10-20T09:00:00-04:00'}
        for stamp, shown in [('2026-10-19T09:00:00-04:00', True), ('2026-10-20T09:00:00-04:00', False)]:
            section = ReportSurface(render_oncall_banner(data, datetime.fromisoformat(stamp))).by_id['on-call']
            self.assertEqual('hidden' not in section['attrs'], shown)
        del data['oncall']['current_shift']
        data['oncall']['state'] = 'On call'
        data['oncall']['shift'] = '<img src=x onerror=alert(1)>'
        page = ReportSurface(render_oncall_banner(data))
        self.assertNotIn('hidden', page.by_id['on-call']['attrs'])
        self.assertIn(data['oncall']['shift'], page.visible_text())
        self.assertFalse(any(node['tag'] == 'img' for node in page.elements()))
        data['oncall']['state'] = 'Not on call'
        data['oncall']['shift'] = 'Tomorrow, 09:00'
        self.assertIn('hidden', ReportSurface(render_oncall_banner(data)).by_id['on-call']['attrs'])

    def test_next_shift_becomes_current_and_ends_without_a_source_refresh(self):
        data = snapshot()
        data['oncall']['current_shift'] = {'start': '2026-10-18T09:00:00-04:00', 'end': '2026-10-19T09:00:00-04:00'}
        data['oncall']['next_shift'] = {'start': '2026-10-20T09:00:00-04:00', 'end': '2026-10-21T09:00:00-04:00'}
        for stamp, message in [
            ('2026-10-20T08:59:59-04:00', 'Your next on-call shift starts'),
            ('2026-10-20T09:00:00-04:00', 'You are on call until Wed 21 Oct, 09:00 EDT'),
            ('2026-10-21T08:59:59-04:00', 'You are on call until Wed 21 Oct, 09:00 EDT'),
        ]:
            with self.subTest(stamp=stamp):
                page = ReportSurface(render_oncall_banner(data, datetime.fromisoformat(stamp)))
                self.assertNotIn('hidden', page.by_id['on-call']['attrs'])
                self.assertIn(message, page.visible_text())
        # Stale legacy state cannot retain the alert beyond the authoritative end.
        data['oncall']['state'] = 'On call'
        del data['oncall']['current_shift']
        page = ReportSurface(render_oncall_banner(data, datetime.fromisoformat('2026-10-21T09:00:00-04:00')))
        self.assertIn('hidden', page.by_id['on-call']['attrs'])

    def test_live_clock_overrides_collection_and_converts_offsets(self):
        data = snapshot()
        data['oncall']['next_shift'] = {'start': '2026-10-21T13:00:00Z', 'end': '2026-10-22T13:00:00Z'}
        self.assertIn('hidden', ReportSurface(render_oncall_banner(data)).by_id['on-call']['attrs'])
        page = ReportSurface(render(data, datetime.fromisoformat('2026-10-20T09:00:00-04:00')))
        self.assertNotIn('hidden', page.by_id['on-call']['attrs'])
        self.assertIn('Wed 21 Oct, 09:00 EDT', page.visible_text(page.by_id['on-call']))


if __name__ == '__main__':unittest.main()
