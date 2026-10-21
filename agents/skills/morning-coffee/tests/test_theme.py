"""Time-based presentation preserves the full workspace and scheduling controls."""
from copy import deepcopy
from datetime import datetime
import re
import unittest

from test_report_history import ReportSurface, snapshot
from render_brief import dashboard_theme, render


class ThemeTests(unittest.TestCase):
    def test_boundaries_use_report_timezone_in_winter_and_summer(self):
        data = snapshot()
        for day, offset in [('2026-01-19', '-05:00'), ('2026-07-20', '-04:00')]:
            for clock, expected in [('00:00:00', 'coffee'), ('09:59:59', 'coffee'),
                                    ('10:00:00', 'tea'), ('16:59:59', 'tea'),
                                    ('17:00:00', 'coffee'), ('23:59:59', 'coffee')]:
                with self.subTest(day=day, clock=clock):
                    instant = datetime.fromisoformat(day + 'T' + clock + offset)
                    self.assertEqual(dashboard_theme(data, instant), expected)
        instant = datetime.fromisoformat('2026-10-21T14:00:00+00:00')
        self.assertEqual(dashboard_theme(data, instant), 'tea')  # 10:00 Toronto
        data['report']['timezone'] = 'America/Los_Angeles'
        self.assertEqual(dashboard_theme(data, instant), 'coffee')  # 07:00 LA

    def test_palette_changes_without_changing_content_or_controls(self):
        data = snapshot()
        data['workspace'] = {'version': 1}
        # A migrated Tea snapshot retains the unified workspace in either palette.
        data['history'] = {'kind': 'tea-time'}
        before = deepcopy(data)
        coffee = render(data, now=datetime.fromisoformat('2026-10-21T09:59:59-04:00'))
        tea = render(data, now=datetime.fromisoformat('2026-10-21T10:00:00-04:00'))
        def dashboard_content(page):
            page = re.sub(r'<header class="shop-sign">.*?</header>', '', page, flags=re.S)
            page = re.sub(r'<title>.*?</title>', '', page)
            return page.replace('<body class="tea">', '<body class="coffee">')
        self.assertEqual(dashboard_content(coffee), dashboard_content(tea))
        self.assertIn('<h1>Tea Time</h1>', tea)
        self.assertIn('TEA BREAK', tea)
        self.assertIn('Steeped at ', tea)
        self.assertIn('<h1>Morning Coffee</h1>', coffee)
        surface = ReportSurface(tea)
        self.assertIn('coffee-context', surface.by_id)
        self.assertNotIn('full-context', surface.by_id)
        self.assertIn('day-duration-focus', surface.by_id)
        self.assertEqual(data, before)

    def test_snapshot_render_uses_collection_time_and_preserves_legacy_archives(self):
        data = snapshot('13:00')
        self.assertEqual(dashboard_theme(data), 'tea')
        data['history'] = {'kind': 'tea-time'}
        data['collected_at'] = '2026-10-19T18:00:00-04:00'
        self.assertEqual(dashboard_theme(data), 'tea')
        self.assertEqual(dashboard_theme({'report': data['report']}), 'coffee')
