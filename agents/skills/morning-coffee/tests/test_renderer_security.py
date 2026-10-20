"""Untrusted report values must remain text in the rendered HTML document."""
import unittest

from test_report_history import ReportSurface, snapshot
from render_brief import render


class RendererSecurityTests(unittest.TestCase):
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
