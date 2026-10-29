"""Priority refresh and local completion in a real browser with temporary storage.

Run: uv run --with playwright --python 3.12 tests/priority_recommendations_browser_check.py
"""
from copy import deepcopy
from datetime import datetime
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import sys
import tempfile
import threading
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_plan_server import handler_for
from report_history import publish
from todo_state import load_todos, save_todo_action
from workspace_state import complete_refresh, load_workspace, open_workspace
from test_report_history import snapshot


def main():
    with tempfile.TemporaryDirectory(prefix='coffee-priorities-browser-') as temporary:
        root = Path(temporary)
        day = datetime.now(ZoneInfo('America/Toronto')).date().isoformat()
        original = snapshot('09:00', day=day)
        original['priorities'][0]['id'] = 'legacy'
        original['priorities'][0]['title'] = 'Earlier source work'
        source = publish(root, original, 'morning-coffee')
        initial = open_workspace(root, source['snapshot'])
        saved = save_todo_action(root, {'action': 'add', 'title': 'Keep my task'})['item']
        token = 'synthetic-priorities-capability-' + 'x' * 32
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(original, root, token, workspace=True))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=os.environ.get(
                    'CHROME_PATH', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'), headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                url = f'http://127.0.0.1:{server.server_port}/report/{token}'
                page.goto(url)
                draft = page.locator('.todo-add [name=title]')
                draft.fill('Keep this unsaved text')
                fresh = snapshot('10:00', day=day)
                fresh['priorities'] = [dict(deepcopy(original['priorities'][0]),
                    id=f'fresh:{index}', title=f'Current recommendation {index}',
                    context='A verified decision is needed today.') for index in range(4)]
                fresh['work_suggestions'] = [{'id': 'other:fixture', 'title': 'Additional fixture work',
                    'action': 'Check an independent source', 'material_key': 'other-event'}]
                fresh['reviews']['items'][0]['readiness']['status'] = 'READY'
                complete_refresh(root, publish(root, fresh, 'refresh')['snapshot'])
                page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
                rows = page.locator('#daily-priorities .priority-row')
                expect(rows).to_have_count(4)
                expect(rows.locator('h4')).to_have_text([row['title'] for row in fresh['priorities']])
                expect(draft).to_have_value('Keep this unsaved text')
                expect(page.locator('#retained-priorities')).to_contain_text('Earlier source work')
                expect(page.locator('#what-changed')).to_be_visible()
                expect(page.locator('#what-changed')).to_contain_text('Synthetic retry fixture')
                expect(page.locator('#other-suggested-work')).to_be_visible()
                page.locator('#other-suggested-work > summary').click()
                expect(page.locator('#other-suggested-work')).to_contain_text('Additional fixture work')
                expect(page.locator('#other-suggested-work')).not_to_contain_text('Current recommendation 0')
                expect(page.locator('#daily-priorities [data-suggestion-action=accept][data-suggestion-id="fresh:0"]')).to_have_count(1)
                assert page.url == url
                page.locator('#daily-priorities [data-suggestion-action=accept][data-suggestion-id="fresh:0"]').click()
                expect(page.locator('.workspace-suggestion-status')).to_have_text('Added to your local tasks.')
                expect(rows).to_have_count(4)
                expect(page.locator('#other-suggested-work')).to_have_attribute('open', '')
                page.locator('#other-suggested-work [data-suggestion-action=dismiss][data-suggestion-id="other:fixture"]').click()
                expect(page.locator('.workspace-suggestion-status')).to_have_text('Suggestion dismissed.')
                expect(page.locator('#what-changed')).to_be_visible()
                expect(draft).to_have_value('Keep this unsaved text')
                state = load_workspace(root)
                task_id = state['accepted']['fresh:0']['task_id']
                version = state['version']
                page.locator(f'[data-todo-id="{task_id}"] [data-todo-action=complete]').click()
                expect(page.locator('.todo-status')).to_contain_text('Saved locally')
                page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
                expect(rows).to_have_count(3)
                expect(rows.locator('h4')).to_have_text([row['title'] for row in fresh['priorities'][1:]])
                expect(draft).to_have_value('Keep this unsaved text')
                assert load_workspace(root)['version'] == version
                assert load_workspace(root)['selected_priorities'] == initial['selected_priorities']
                assert any(task['id'] == saved['id'] and task['status'] == 'pending' for task in load_todos(root))
                for width in (1440, 390):
                    page.set_viewport_size({'width': width, 'height': 1100})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
    print('PASS: fresh priorities, acceptance, completion, draft preservation, and desktop/mobile layout')


if __name__ == '__main__':
    main()
