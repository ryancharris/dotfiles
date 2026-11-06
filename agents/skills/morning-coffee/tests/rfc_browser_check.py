"""Real browser checks for RFC surfaces and independent durable review completion.

Run: uv run --with playwright --python 3.12 tests/rfc_browser_check.py
All source rows and writes are synthetic, under a temporary root.
"""
from copy import deepcopy
from datetime import datetime
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright, expect

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_plan_server import handler_for
from report_history import publish
from workspace_state import open_workspace
from test_report_history import snapshot
from test_rfc_selection import row, discovery, surface
from select_rfcs import select
from review_state import load_review_state, review_key


def main():
    with tempfile.TemporaryDirectory(prefix='coffee-rfc-browser-') as temporary:
        root = Path(temporary)
        data = snapshot(day='2026-11-06')
        selection = select(discovery([row(1), row(2), row(3, 'Drafting'), row(4, 'Approved')]),
                           datetime.fromisoformat('2026-11-06T09:00:00-05:00'))
        data['rfcs'] = surface(selection)
        for i, item in enumerate(data['rfcs']['items']):
            item['title'] = 'Old open review' if i == 0 else 'Review with unavailable proposal'
            item['request_label'] = 'Request status unknown'
        data['rfcs']['items'][1]['summary'] = 'Proposal content unavailable; source metadata retained.'
        data['rfcs']['activity'][0]['title'] = 'Recently approved RFC'
        data['rfcs']['activity'][1]['title'] = 'Recently edited draft'
        published = publish(root, data, 'morning-coffee')
        open_workspace(root, published['snapshot'])
        token = 'synthetic-rfc-browser-token-' + 'x' * 40
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(data, root, token, workspace=True))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=os.environ.get('CHROME_PATH', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'), headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/report/{token}')
                activity = page.locator('#rfc-activity')
                expect(activity).to_have_attribute('open', '')
                expect(activity.get_by_text('Recently edited draft', exact=True)).to_be_visible()
                expect(activity.get_by_text('Recently approved RFC', exact=True)).to_be_visible()
                expect(activity.locator('[data-review-toggle]')).to_have_count(0)
                expect(activity).not_to_contain_text('To review')
                expect(page.locator('[data-rfc-pending]')).to_contain_text('Old open review')
                expect(page.locator('[data-rfc-pending]')).to_contain_text('Proposal content unavailable')
                page.locator('[data-rfc-pending] [data-review-toggle]').first.click()
                expect(page.locator('[data-rfc-pending-count]')).to_have_text('1')
                expect(activity.locator('.rfc-activity-row')).to_have_count(2)
                mark = load_review_state(root)[review_key('rfc', selection['items'][0]['url'])]
                assert mark['done'] is True
                page.reload()
                expect(page.locator('[data-rfc-pending-count]')).to_have_text('1')
                expect(activity.locator('.rfc-activity-row')).to_have_count(2)
                page.locator('[data-rfc-completed] > summary').click()
                page.locator('[data-rfc-completed] [data-review-toggle]').click()
                expect(page.locator('[data-rfc-pending-count]')).to_have_text('2')
                for width in (1440, 390, 320):
                    page.set_viewport_size({'width': width, 'height': 1000})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), width
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.locator('#rfcs-to-review').screenshot(path='/tmp/coffee-rfc-desktop.png')
                page.set_viewport_size({'width': 390, 'height': 1000})
                page.locator('#rfcs-to-review').screenshot(path='/tmp/coffee-rfc-mobile.png')
                assert not errors, errors
                browser.close()
            print('PASS: old open reviews and failed-read placeholders visible; recent drafts/approved RFCs separate without review controls; local completion/undo persists and activity counts stay independent; desktop/mobile layouts.')
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__': main()
