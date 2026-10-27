"""The visible brief omits removed chrome and repeats each PR fact only once."""
from copy import deepcopy
import unittest

from test_report_history import ReportSurface, snapshot
from render_brief import render, render_reviews


def all_text(node):
    if isinstance(node, str):
        return node
    if node['tag'] in ('script', 'style'):
        return ''
    return ' '.join(all_text(child) for child in node['children'])


class ReportCleanupTests(unittest.TestCase):
    def test_coffee_and_tea_remove_quarter_plan_footer_and_global_save_notice(self):
        for kind in ('morning-coffee', 'tea-time'):
            with self.subTest(kind=kind):
                data = snapshot()
                original = deepcopy(data)
                data['history'] = {'kind': kind}
                page = ReportSurface(render(data))
                self.assertNotIn('quarterly-plan', page.by_id)
                self.assertNotIn('Quarter plan', page.visible_text())
                self.assertNotIn('About this report', page.visible_text())
                classes = [node['attrs'].get('class', '') for node in page.elements()]
                self.assertNotIn('local-review-save-status', classes)
                self.assertIn('local-review-message', classes)
                self.assertEqual(data['okr'], original['okr'], 'UI removal preserves archived source facts')

    def test_pr_details_do_not_repeat_visible_author_summary_or_size_inputs(self):
        for expanded in (True, False):
            with self.subTest(expanded=expanded):
                data = snapshot()['reviews']
                row = data['items'][0]
                page = ReportSurface(render_reviews(data, expanded=expanded))
                pr_row = next(node for node in page.elements() if node['tag'] == 'tr' and 'data-local-review' in node['attrs'])
                content = all_text(pr_row)
                for value in ('Author: @fixture-author', row['summary'], row['effort']['label'],
                              row['effort']['inputs'], row['effort']['driver'], row['readiness']['facts']):
                    self.assertEqual(content.count(value), 1, value)
                details = next(node for node in page.elements() if node['attrs'].get('class') == 'pr-review-details')
                disclosure = all_text(details)
                self.assertNotIn('Author:', disclosure)
                self.assertNotIn(row['effort']['label'], disclosure)
                self.assertNotIn(row['effort']['inputs'], disclosure)
                if expanded:
                    self.assertNotIn(row['summary'], disclosure)
                    self.assertIn(row['summary'], page.visible_text())

    def test_long_summary_is_available_once_and_empty_details_are_omitted(self):
        data = snapshot()['reviews']
        row = data['items'][0]
        row['summary'] = 'A long verified explanation. ' * 15
        page = ReportSurface(render_reviews(data, expanded=True))
        self.assertEqual(all_text(page.root).count(row['summary'].strip()), 1)
        self.assertNotIn('A long verified explanation.', page.visible_text())
        row['summary'] = 'Concise summary.'
        row['effort']['driver'] = ''
        row['readiness']['facts'] = 'BLOCKED; UNSTABLE; REVIEW_REQUIRED; CI 2/3 completed without failure; 1 failing'
        row['updatedAt'] = 'unavailable'
        page = ReportSurface(render_reviews(data, expanded=True))
        self.assertFalse(any(node['attrs'].get('class') == 'pr-review-details' for node in page.elements()))

    def test_today_edit_schedule_only_for_coffee_with_successful_saved_plan(self):
        for kind in ('morning-coffee', 'tea-time'):
            for saved in (False, True):
                with self.subTest(kind=kind, saved=saved):
                    data = snapshot()
                    data['history'] = {'kind': kind}
                    if saved:
                        data['submitted_plan'] = {'version': 1, 'date': data['report']['date'],
                            'timezone': data['report']['timezone'], 'submitted_at': '2026-10-19T09:15:00-04:00', 'blocks': []}
                    page = ReportSurface(render(data))
                    edits = [node for node in page.elements(page.by_id['today']) if 'data-edit-schedule' in node['attrs']]
                    self.assertEqual(len(edits), 0 if kind == 'tea-time' else 1)
                    if edits:
                        self.assertNotIn('hidden', edits[0]['attrs'])
                        self.assertEqual(edits[0]['attrs']['aria-controls'], 'focus-exercise')
                        self.assertEqual(edits[0]['attrs']['aria-expanded'], 'false')
                        self.assertIn('hidden', page.by_id['focus-exercise']['attrs'])
                        self.assertIn(page.by_id['today'], page.ancestors[page.by_id['focus-exercise']['attrs']['id']])


if __name__ == '__main__':
    unittest.main()
