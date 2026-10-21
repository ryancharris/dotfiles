"""Untrusted report values must remain text in the rendered HTML document."""
import unittest

from test_report_history import ReportSurface, snapshot
from render_brief import A, render, render_focus


class RendererSecurityTests(unittest.TestCase):
    def test_source_links_open_new_tabs_and_section_links_stay_on_the_report(self):
        for kind in ('morning-coffee', 'refresh', 'tea-time'):
            with self.subTest(kind=kind):
                data = snapshot()
                data['history'] = {'kind': kind}
                data['priorities'] *= 4
                data['workspace'] = {'suggestions': [{'id': 'slack:synthetic', 'fingerprint': 'a' * 64,
                    'item': {'title': 'Synthetic source suggestion', 'action': 'Inspect the source.',
                             'url': 'https://example.com/suggestion'}}]}
                page = ReportSurface(render(data))
                links = [node['attrs'] for node in page.elements() if node['tag'] == 'a']
                source_links = [attrs for attrs in links if not attrs['href'].startswith('#')]
                section_links = [attrs for attrs in links if attrs['href'].startswith('#')]
                self.assertTrue(source_links)
                self.assertTrue(section_links)
                self.assertIn('https://example.com/suggestion', {attrs['href'] for attrs in source_links})
                self.assertIn('#today', {attrs['href'] for attrs in section_links})
                for attrs in source_links:
                    self.assertEqual(attrs.get('target'), '_blank', attrs)
                    self.assertTrue({'noopener', 'noreferrer'} <= set(attrs.get('rel', '').split()), attrs)
                for attrs in section_links:
                    self.assertNotIn('target', attrs)
                    self.assertIn(attrs['href'][1:], page.by_id)

    def test_priority_shortcut_and_overflow_link_keep_same_page_navigation(self):
        data = snapshot()
        data['priorities'] *= 4
        page = ReportSurface(render_focus(data, False))
        links = [node['attrs'] for node in page.elements() if node['tag'] == 'a']
        self.assertEqual(len(links), 4)
        self.assertTrue(all(attrs['href'] == '#daily-priorities' and 'target' not in attrs for attrs in links))

    def test_source_link_helper_rejects_active_urls_and_escapes_link_content(self):
        for url in ('javascript:alert(1)', 'data:text/html,<script>alert(1)</script>', '//example.com', None):
            with self.subTest(url=url):
                self.assertEqual(A(url, '<unsafe>'), '&lt;unsafe&gt;')
        page = ReportSurface(A('https://example.com/?x="&y=2', '<source>'))
        link = next(node for node in page.elements() if node['tag'] == 'a')
        self.assertEqual(link['attrs']['href'], 'https://example.com/?x="&y=2')
        self.assertEqual(link['children'], ['<source>'])
        self.assertEqual(link['attrs']['target'], '_blank')

    def test_incident_count_markup_cannot_create_active_elements(self):
        data = snapshot()
        payload = '</b><img src="/missing" onerror="window.injected=true"><b>'
        data['oncall']['counts'] = {'active': payload}

        surface = ReportSurface(render(data))
        section = surface.by_id['on-call']
        elements = list(surface.elements(section))
        self.assertFalse(any(node['tag'] in ('img', 'script', 'svg', 'iframe') for node in elements))
        self.assertFalse(any(name.startswith('on') for node in elements for name in node['attrs']))
        count = next(node for node in elements if node['tag'] == 'b' and payload in node['children'])
        self.assertEqual(count['children'], [payload])
        link = next(node for node in elements if node['attrs'].get('class') == 'incident-counts')
        self.assertEqual(link['attrs']['aria-label'], 'Incidents dashboard: ' + payload + ' active')

    def test_titles_and_count_labels_remain_literal_text(self):
        data = snapshot()
        title = '</title><img src=x onerror="window.injected=true">'
        label = '\" onmouseover=\"window.injected=true\"><svg onload=\"window.injected=true\">'
        data['report']['page_title'] = title
        data['oncall']['counts'] = {label: 3}

        surface = ReportSurface(render(data))
        elements = list(surface.elements())
        self.assertFalse(any(node['tag'] in ('img', 'svg', 'iframe') for node in elements))
        self.assertFalse(any(name.startswith('on') for node in elements for name in node['attrs']))
        title_node = next(node for node in elements if node['tag'] == 'title')
        self.assertEqual(title_node['children'], [title])
        link = next(node for node in elements if node['attrs'].get('class') == 'incident-counts')
        self.assertEqual(link['attrs']['aria-label'], 'Incidents dashboard: 3 ' + label)
        self.assertIn(label, surface.visible_text(link))


if __name__ == '__main__':
    unittest.main()
