"""Real browser checks for accepted suggestions; all storage and browsers are isolated.

Run: uv run --with playwright --python 3.12 tests/suggestion_browser_check.py
"""
from datetime import datetime
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_plan_server import handler_for
from report_history import publish
from todo_state import load_todos, save_todo_action
from workspace_state import complete_refresh, load_workspace, open_workspace
from test_report_history import snapshot


def check(browser, mode):
    with tempfile.TemporaryDirectory(prefix='coffee-suggestion-') as temporary:
        root = Path(temporary)
        day = datetime.now(ZoneInfo('America/Toronto')).date().isoformat()
        data = snapshot(day=day)
        data['work_suggestions'] = [{'id': 'suggested-work', 'title': 'Accepted fixture task',
            'action': 'Check the fixture', 'material_key': 'verified-event', 'project_tags': ['New project']}]
        source = publish(root, data, 'morning-coffee')
        open_workspace(root, source['snapshot'])
        existing = save_todo_action(root, {'action': 'add', 'title': 'Existing task', 'project_tags': ['Existing project']})['item']
        save_todo_action(root, {'action': 'complete', 'id': existing['id']})
        token = 'synthetic-suggestion-capability-' + 'x' * 32
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(data, root, token, workspace=True))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        page = browser.new_page()
        held = []
        requests = []
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append((request.method, request.url)))
        try:
            url = f'http://127.0.0.1:{server.server_port}/report/{token}'
            page.goto(url)
            page.wait_for_timeout(100)
            editing = mode.startswith('edit-')
            edit_title = None
            if editing:
                page.locator('[data-todo-filter=all]').click()
                row = page.locator('[data-todo-id="' + existing['id'] + '"]')
                row.locator('.todo-more > summary').click()
                row.locator('[data-todo-action=edit]').click()
                edit_title = row.locator('.todo-edit-form [name=title]')
                edit_title.fill('Rename retained across acceptance')
                page.locator('.todo-add [name=title]').fill('Unsubmitted new task')
                if mode == 'edit-draft':
                    edit_title.focus()
                    edit_title.evaluate('(input) => input.setSelectionRange(2, 8)')
                    fresh = snapshot('10:00', day=day)
                    fresh['work_suggestions'] = data['work_suggestions']
                    complete_refresh(root, publish(root, fresh, 'refresh')['snapshot'])
                    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
                    expect(page.locator('.shop-sign')).to_contain_text('10:00')
                    expect(edit_title).to_be_focused()
                    assert edit_title.evaluate('(input) => [input.selectionStart, input.selectionEnd]') == [2, 8]
                elif mode == 'edit-lost-ack':
                    def lose_edit_ack(route):
                        response = route.fetch()
                        assert response.ok
                        route.fulfill(status=503, json={'ok': False, 'error': 'Lost edit acknowledgement'})
                    page.route('**/todo', lose_edit_ack)
                    row.locator('.todo-edit-form button[type=submit]').click()
                    expect(page.locator('.todo-status')).to_contain_text('Lost edit acknowledgement')
                    page.unroute('**/todo', lose_edit_ack)
                    assert next(item for item in load_todos(root) if item['id'] == existing['id'])['title'] == 'Rename retained across acceptance'
                expect(edit_title).to_have_value('Rename retained across acceptance')
            if mode in ('filtered', 'failed-save'):
                page.locator('[data-todo-filter=completed]').click()
                page.locator('[data-todo-project-filter]').select_option('tag:Existing project')
                page.locator('.todo-add [name=title]').fill('Preserve unsaved draft')
            elif mode == 'updating':
                # Hold only the background view GET while keeping local POSTs available.
                page.route(url, lambda route: held.append(route))
                fresh = snapshot('10:00', day=day)
                fresh['work_suggestions'] = data['work_suggestions']
                complete_refresh(root, publish(root, fresh, 'refresh')['snapshot'])
                page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
                deadline = time.monotonic() + 3
                while not held and time.monotonic() < deadline:
                    page.wait_for_timeout(20)
                assert held, 'Expected an in-flight background source-view request'
            if mode in ('saving-task', 'edit-saving'):
                page.route('**/todo', lambda route: held.append(route))
                if mode == 'edit-saving':
                    page.locator('.todo-edit-form button[type=submit]').click()
                else:
                    page.locator('.todo-add [name=title]').fill('Concurrent task save')
                    page.locator('.todo-add button[type=submit]').click()
                deadline = time.monotonic() + 3
                while not held and time.monotonic() < deadline:
                    page.wait_for_timeout(20)
                assert held, 'Expected an in-flight task save'
                page.locator('[data-suggestion-action=accept]').click()
                expect(page.locator('.workspace-suggestion-status')).to_contain_text('A task is still saving')
                assert not load_workspace(root)['accepted']
                assert not any(method == 'POST' and target.endswith('/suggestion') for method, target in requests)
                held.pop().continue_()
                page.unroute('**/todo')
                if mode == 'edit-saving':
                    expect(page.locator('.todo-status')).to_have_text('Saved locally: task updated.')
                    expect(page.locator('.todo-edit-form')).to_have_count(0)
                    assert next(task for task in load_todos(root) if task['id'] == existing['id'])['title'] == 'Rename retained across acceptance'
                else:
                    expect(page.locator('.todo-status')).to_have_text('Saved locally: task added.')
                    assert any(task['title'] == 'Concurrent task save' for task in load_todos(root))
            if mode == 'failed-save':
                page.route('**/suggestion', lambda route: route.fulfill(status=500, content_type='application/json',
                    body='{"ok":false,"error":"Fixture save failure"}'))
            elif mode == 'failed-view':
                page.route(url, lambda route: route.fulfill(status=500, body='Fixture view failure'))
            page.locator('[data-suggestion-action=accept]').click()
            page.wait_for_timeout(100)
            accepted = [task for task in load_todos(root) if task['title'] == 'Accepted fixture task']
            if mode == 'failed-save':
                assert not accepted
                expect(page.locator('.workspace-suggestion-status')).to_contain_text('Choice not confirmed')
                expect(page.locator('[data-suggestion-action=accept]')).to_have_count(1)
                expect(page.locator('[data-todo-filter=completed]')).to_have_attribute('aria-selected', 'true')
                expect(page.locator('[data-todo-project-filter]')).to_have_value('tag:Existing project')
                assert not load_workspace(root)['accepted']
                assert not errors, errors
                print('PASS:', mode)
                return
            assert len(accepted) == 1, f'{mode}: clicking Add to today must persist one task even during a background update'
            if held:
                held.pop().continue_()
                page.unroute(url)
            expect(page.locator('.todo-row', has_text='Accepted fixture task')).to_be_visible()
            expect(page.locator('[data-suggestion-action=accept]')).to_have_count(1 if mode == 'failed-view' else 0)
            expect(page.locator('#what-changed')).to_be_hidden()
            expect(page.locator('.todo-status')).to_contain_text('Added to your local tasks: Accepted fixture task')
            assert sum(method == 'POST' and target.endswith('/suggestion') for method, target in requests) == 1
            assert len(load_workspace(root)['accepted']) == 1
            if mode in ('filtered', 'failed-save'):
                expect(page.locator('[data-todo-filter=pending]')).to_have_attribute('aria-selected', 'true')
                expect(page.locator('[data-todo-project-filter]')).to_have_value('')
                expect(page.locator('.todo-add [name=title]')).to_have_value('Preserve unsaved draft')
            if editing:
                expect(page.locator('.todo-add [name=title]')).to_have_value('Unsubmitted new task')
                if mode in ('edit-draft', 'edit-lost-ack'):
                    expect(edit_title).to_have_value('Rename retained across acceptance')
                    page.locator('.todo-edit-form button[type=submit]').click()
                    expect(page.locator('.todo-status')).to_have_text('Saved locally: task updated.')
                    expect(page.locator('.todo-edit-form')).to_have_count(0)
                persisted = next(task for task in load_todos(root) if task['id'] == existing['id'])
                assert persisted['title'] == 'Rename retained across acceptance'
                assert persisted['status'] == 'completed'
                assert persisted['project_tags'] == ['Existing project']
                assert len(load_todos(root)) == 2
            assert not errors, errors
            print('PASS:', mode)
        finally:
            for route in held:
                route.abort()
            page.close()
            server.shutdown()
            server.server_close()
            worker.join()


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get(
            'CHROME_PATH', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'), headless=True)
        try:
            for mode in ('filtered', 'updating', 'failed-save', 'failed-view', 'saving-task', 'edit-draft', 'edit-lost-ack', 'edit-saving'):
                check(browser, mode)
        finally:
            browser.close()


if __name__ == '__main__':
    main()
