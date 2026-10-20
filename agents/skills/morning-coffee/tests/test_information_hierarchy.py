"""Progressive disclosure keeps the brief readable without hiding source caveats."""
import unittest

from test_report_history import ReportSurface, snapshot
from render_brief import render, render_reviews


def text(node):
    if isinstance(node, str):
        return node
    return ' '.join(text(child) for child in node['children'])


class InformationHierarchyTests(unittest.TestCase):
    def test_secondary_pr_filters_stay_available_inside_the_queue_controls(self):
        page = ReportSurface(render_reviews(snapshot()['reviews']))
        controls = next(node for node in page.elements() if node['attrs'].get('class') == 'pr-controls')
        extra = next(node for node in page.elements(controls) if node['attrs'].get('class') == 'pr-extra-filters')
        self.assertEqual({node['attrs']['data-filter'] for node in page.elements(extra)
                          if 'data-filter' in node['attrs']}, {'request-type', 'status', 'effort', 'team'})
        self.assertEqual(len([node for node in page.elements(controls)
                              if 'data-filter' in node['attrs']]), 7)
        self.assertIn('More filters', page.visible_text(extra))
        self.assertNotIn('All requests', page.visible_text(extra))

    def test_normal_provenance_is_available_once_but_incomplete_roster_warning_stays_visible(self):
        data = snapshot()['reviews']
        data['personalReview'] = {'excludedCount': 3, 'reRequestedCount': 1, 'unknownCount': 0}
        page = ReportSurface(render_reviews(data))
        notes = next(node for node in page.elements() if node['attrs'].get('class') == 'review-queue-notes')
        self.assertIn('Excluded 3 already approved', text(notes))
        self.assertIn('Synthetic complete roster.', text(notes))
        self.assertNotIn('Excluded 3 already approved', page.visible_text())
        self.assertNotIn('Synthetic complete roster.', page.visible_text())
        data['personalReview']['unknownCount'] = 2
        uncertain_approval = ReportSurface(render_reviews(data))
        self.assertIn('2 approval status unknown', uncertain_approval.visible_text())
        self.assertEqual(text(uncertain_approval.root).count('2 approval status unknown'), 1)
        data['items'][0]['authorOnTransport'] = None
        unknown = ReportSurface(render_reviews(data))
        self.assertIn('1 requests have unknown author membership; Everyone includes them.', unknown.visible_text())
        data['authorRoster'] = {'status': 'partial', 'note': 'A source did not return.'}
        partial = ReportSurface(render_reviews(data))
        self.assertIn('Transport author roster incomplete', partial.visible_text())
        self.assertIn('A source did not return.', partial.visible_text())

    def test_rfc_summary_is_retained_once_in_both_briefs(self):
        for kind in ('morning-coffee', 'tea-time'):
            with self.subTest(kind=kind):
                data = snapshot()
                data['history'] = {'kind': kind}
                page = ReportSurface(render(data))
                rfc = page.by_id['rfcs-to-review']
                summary = data['rfcs']['items'][0]['summary']
                self.assertEqual(text(rfc).count(summary), 1)
                self.assertEqual(summary in page.visible_text(rfc), kind == 'morning-coffee')


if __name__ == '__main__':
    unittest.main()
