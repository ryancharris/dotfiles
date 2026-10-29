"""Overview visibility and on-call alerts use only verified timing evidence."""
from copy import deepcopy
from datetime import datetime
import unittest
from test_report_history import ReportSurface, snapshot
from report_history import changes
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
        self.assertIn('Recommended priorities', visible)
        self.assertIn('Previous weekday', visible)
        self.assertNotIn('chosen priorities', visible)
        self.assertIn('Why today', visible)
        self.assertIn(data['priorities'][0]['context'], visible)
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
        self.assertIn('No recommended priorities.', visible)
        self.assertIn('No verified outcomes for ' + data['yesterday']['date'], visible)

    def test_suggestions_do_not_define_whether_source_changes_are_visible(self):
        data = snapshot()
        data['workspace'] = {'suggestions': [{'id': 'fixture', 'fingerprint': 'f', 'item': {'title': 'Suggested work'}}]}
        data['updates'] = {'items': [], 'since': data['collected_at']}
        section = ReportSurface(workspace_changes(data)).by_id['what-changed']
        self.assertIn('hidden', section['attrs'])
        data['workspace']['suggestions'] = []
        data['updates']['items'] = [{'section': 'Reviews waiting', 'id': 'review:42',
            'title': 'Fixture review', 'status': 'Updated', 'importance': 1,
            'url': 'https://example.com/review',
            'fields': [{'label': 'Readiness', 'before': 'status: BLOCKED', 'after': 'status: READY'}]}]
        section = ReportSurface(workspace_changes(data)).by_id['what-changed']
        self.assertNotIn('hidden', section['attrs'])
        self.assertIn('Fixture review', ReportSurface(workspace_changes(data)).visible_text())

    def test_rank_or_generated_wording_is_not_a_source_change(self):
        data = snapshot()
        data['workspace'] = {'suggestions': []}
        data['updates'] = {'since': data['collected_at'], 'items': [
            {'section': 'Daily priorities', 'id': 'p', 'status': 'Updated', 'title': 'Priority',
             'fields': [{'label': 'Priority rank', 'before': '2', 'after': '1'},
                        {'label': 'Context', 'before': 'old prose', 'after': 'new prose'}]}]}
        section = ReportSurface(workspace_changes(data)).by_id['what-changed']
        self.assertIn('hidden', section['attrs'])

    def test_unverified_or_legacy_priority_status_is_not_presented_as_fact(self):
        previous = snapshot()
        previous['priorities'][0]['status'] = 'open'
        current = deepcopy(previous)
        current['priorities'][0].update(status='completed', verified=False)
        current['workspace'] = {'suggestions': []}
        current['updates'] = {'since': previous['collected_at'], 'items': changes(current, previous)}
        section = ReportSurface(workspace_changes(current)).by_id['what-changed']
        self.assertIn('hidden', section['attrs'])
        current['updates']['items'][0].pop('verified')
        self.assertIn('hidden', ReportSurface(workspace_changes(current)).by_id['what-changed']['attrs'])
        current['priorities'][0]['verified'] = True
        current['updates']['items'] = changes(current, previous)
        self.assertIn('Status: open → completed', ReportSurface(workspace_changes(current)).visible_text())

    def test_matching_suggestion_actions_stay_with_priority_and_other_work_remains_available(self):
        data = snapshot()
        priority = data['priorities'][0]
        data['workspace'] = {'suggestions': [
            {'id': priority['id'], 'fingerprint': 'one', 'item': deepcopy(priority)},
            {'id': 'other', 'fingerprint': 'two', 'item': {'id': 'other', 'title': 'Different work', 'action': 'Follow up'}}]}
        page = ReportSurface(render(data))
        priorities = page.by_id['daily-priorities']
        other = page.by_id['other-suggested-work']
        priority_actions = [node['attrs'] for node in page.elements(priorities)
                            if node['attrs'].get('data-suggestion-id') == priority['id']]
        other_actions = [node['attrs'] for node in page.elements(other)
                         if node['attrs'].get('data-suggestion-id') == 'other']
        self.assertEqual({row['data-suggestion-action'] for row in priority_actions}, {'accept', 'dismiss'})
        self.assertEqual({row['data-suggestion-action'] for row in other_actions}, {'accept', 'dismiss'})
        self.assertFalse(any(node['attrs'].get('data-suggestion-id') == priority['id'] for node in page.elements(other)))
        self.assertIn('hidden', page.by_id['what-changed']['attrs'])
        self.assertIn(data['yesterday']['items'][0]['title'], page.visible_text(page.by_id['daily-briefing']))

    def test_same_title_different_id_does_not_hide_unrelated_suggestion(self):
        data = snapshot()
        priority = data['priorities'][0]
        data['workspace'] = {'suggestions': [{'id': 'unrelated', 'fingerprint': 'distinct-event',
            'item': {'id': 'unrelated', 'title': priority['title'], 'action': 'Different follow-up'}}]}
        page = ReportSurface(render(data))
        other = page.by_id['other-suggested-work']
        self.assertNotIn('hidden', other['attrs'])
        self.assertTrue(any(node['attrs'].get('data-suggestion-id') == 'unrelated' for node in page.elements(other)))
        self.assertFalse(any(node['attrs'].get('data-suggestion-id') == 'unrelated'
                             for node in page.elements(page.by_id['daily-priorities'])))

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
