"""Live todo lifecycle with synthetic data, an isolated store and installed Chrome.

Run: uv run --with playwright python tests/todo_lifecycle_browser_check.py
"""
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright, expect

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_plan_server import handler_for
from report_history import publish
from todo_state import save_todo_action
from workspace_state import open_workspace
from test_report_history import snapshot


def main():
    with tempfile.TemporaryDirectory(prefix='coffee-todo-lifecycle-') as temporary:
        root = Path(temporary)
        zone = 'America/Toronto'
        data = snapshot('09:00', day=datetime.now(ZoneInfo(zone)).date().isoformat())
        published = publish(root, data, 'morning-coffee')
        open_workspace(root, published['snapshot'])
        for title, action in [('Update runbook', 'complete'), ('Old alert', 'cancel')]:
            item = save_todo_action(root, {'action': 'add', 'title': title})['item']
            save_todo_action(root, {'action': action, 'id': item['id']})
        token = 'synthetic-todo-lifecycle-capability'
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(data, root, token, workspace=True))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROME_PATH', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
                page=browser.new_page(viewport={'width':1440,'height':1100})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/report/{token}#todos')
                todos=page.locator('#todos')
                expect(todos.get_by_role('tab')).to_have_count(2)
                expect(todos.locator('[data-todo-group=completed]')).to_be_visible()
                expect(todos.locator('[data-todo-group=cancelled]')).to_be_visible()
                todos.locator('#todo-title').fill('Browser dated task')
                expect(todos.locator('input[type=date]')).to_have_count(0)
                today = datetime.now(ZoneInfo(zone)).date().isoformat()
                todos.get_by_role('button',name='Add task',exact=True).click()
                row=todos.locator('.todo-row').filter(has=page.locator('.todo-title',has_text='Browser dated task'))
                expect(todos.locator('.todo-day-heading')).to_have_text('Today')
                row.locator('summary').click()
                edit_action = row.get_by_role('button', name='Edit task', exact=True)
                edit_action.focus()
                save_todo_action(root, {'action': 'add', 'title': 'Menu update task'})
                expect(todos.locator('.todo-title', has_text='Menu update task')).to_be_visible(timeout=12000)
                expect(row.locator('.todo-more')).to_have_attribute('open', '')
                expect(edit_action).to_be_focused()
                edit_action.click()
                expect(row.locator('input[type=date]')).to_have_count(0)
                title_input = row.locator('.todo-edit-form [name=title]')
                title_input.fill('Browser dated task edited')
                title_input.focus()
                title_input.evaluate("node=>node.setSelectionRange(1,4,'forward')")
                # Another session changes an unrelated task while the editor is open.
                item = save_todo_action(root, {'action': 'add', 'title': 'Other session task'})['item']
                expect(todos.locator('.todo-title', has_text='Other session task')).to_be_visible(timeout=12000)
                expect(title_input).to_be_focused()
                assert title_input.evaluate('node=>[node.selectionStart,node.selectionEnd,node.selectionDirection]') == [1, 4, 'forward']
                expect(title_input).to_have_value('Browser dated task edited')
                row.get_by_role('button',name='Save changes',exact=True).click()
                expect(todos.locator('.todo-day-heading')).to_have_text('Today')
                row.get_by_role('button',name='Complete',exact=True).click()
                expect(row).to_be_visible()
                expect(row).to_have_attribute('data-todo-group','completed')
                page.reload()
                expect(todos.locator('.todo-day-heading')).to_have_text('Today')
                # Simulate yesterday's closure; the real status poll should archive it without a reload.
                store=root/'todos/state.json'
                data=json.loads(store.read_text())
                for item in data['items']:
                    if item['title'].startswith('Browser dated task'):item['closed_at']=(datetime.now(ZoneInfo(zone))-timedelta(days=1)).isoformat()
                tmp=root/'todos/test-state.tmp';tmp.write_text(json.dumps(data));tmp.replace(store)
                expect(todos.locator('.todo-title',has_text='Browser dated task')).to_have_count(0,timeout=12000)
                todos.get_by_role('tab',name='Archived').click()
                archived=todos.locator('.todo-row').filter(has=page.locator('.todo-title',has_text='Browser dated task'))
                expect(archived).to_be_visible()
                expect(todos.locator('.todo-day-heading')).to_have_count(0)
                expect(archived.locator('.todo-date').nth(0)).to_have_text('Scheduled: '+today)
                expect(archived.locator('.todo-date').nth(1)).to_have_text('Completed: '+(datetime.now(ZoneInfo(zone))-timedelta(days=1)).date().isoformat())
                cleared=save_todo_action(root, {'action':'add','title':'Alpha archived task','task_date':'2020-01-01'},timezone_name=zone)['item']
                save_todo_action(root, {'action':'remove','id':cleared['id']},timezone_name=zone)
                alpha=todos.locator('.todo-row').filter(has=page.locator('.todo-title',has_text='Alpha archived task'))
                expect(alpha).to_be_visible(timeout=12000)
                expect(alpha.locator('.todo-date').nth(1)).to_have_text('Not completed or cancelled')
                cancelled=save_todo_action(root, {'action':'add','title':'Cancelled archived task'},timezone_name=zone)['item']
                save_todo_action(root, {'action':'cancel','id':cancelled['id']},timezone_name=zone)
                save_todo_action(root, {'action':'remove','id':cancelled['id']},timezone_name=zone)
                expect(todos.locator('.todo-title',has_text='Cancelled archived task')).to_be_visible(timeout=12000)
                titles=lambda: todos.locator('.todo-list > .todo-row .todo-title').all_text_contents()
                expect(todos.get_by_label('Sort archive').locator('option')).to_have_text(['Action','Date ascending','Date descending'])
                todos.get_by_label('Sort archive').select_option('action-asc')
                assert titles()==['Cancelled archived task','Browser dated task edited','Alpha archived task']
                todos.get_by_label('Sort archive').select_option('closed-asc')
                assert titles()==['Browser dated task edited','Cancelled archived task','Alpha archived task']
                todos.get_by_label('Sort archive').select_option('closed-desc')
                assert titles()==['Cancelled archived task','Browser dated task edited','Alpha archived task']
                archived.get_by_role('button',name='Restore',exact=True).click()
                expect(todos.get_by_role('tab',name='To do')).to_have_attribute('aria-selected','true')
                expect(row).to_be_visible()
                yesterday=(datetime.now(ZoneInfo(zone)).date()-timedelta(days=1)).isoformat()
                tomorrow=(datetime.now(ZoneInfo(zone)).date()+timedelta(days=1)).isoformat()
                save_todo_action(root, {'action':'add','title':'Overdue browser task','task_date':yesterday},timezone_name=zone)
                future=save_todo_action(root, {'action':'add','title':'Future browser task','task_date':tomorrow},timezone_name=zone)['item']
                save_todo_action(root, {'action':'complete','id':future['id']},timezone_name=zone)
                late=todos.locator('.todo-row').filter(has=page.locator('.todo-title',has_text='Overdue browser task'))
                expect(late).to_be_visible(timeout=12000)
                expect(late.locator('.todo-date')).to_have_text('Overdue · '+yesterday)
                expect(todos.locator('.todo-day-heading')).to_have_text('Today')
                expect(todos.locator('.todo-title',has_text='Future browser task')).to_be_visible()
                todos.scroll_into_view_if_needed()
                todos.screenshot(path='/tmp/coffee-todo-desktop.png')
                page.set_viewport_size({'width':390,'height':844})
                todos.scroll_into_view_if_needed()
                todos.screenshot(path='/tmp/coffee-todo-mobile.png')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile overflow'
                assert not errors,errors
                print('Browser passed: automatic today date, no date pickers, title editing, persist/reload, same-day completion, live rollover, archive/restore, desktop/mobile.')
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
