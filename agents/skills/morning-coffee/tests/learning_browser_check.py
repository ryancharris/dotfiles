"""Browser QA with an isolated workspace: uv run --with playwright --python 3.12 tests/learning_browser_check.py"""
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
import os, sys, tempfile, threading
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright, expect

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_plan_server import handler_for
from plan_submission import latest_plan
from report_history import publish
from workspace_state import open_workspace
from test_report_history import snapshot


def main():
    with tempfile.TemporaryDirectory(prefix='coffee-learning-qa-') as temporary:
        root = Path(temporary)
        day = datetime.now(ZoneInfo('America/Toronto')).date().isoformat()
        data = snapshot('09:00', day=day)
        data['availability'] = {'status':'complete', 'checked_at':data['collected_at'], 'coverage':'Synthetic calendar',
            'window_start':'09:00', 'window_end':'17:00', 'coverage_start':day+'T00:00:00-04:00',
            'coverage_end':day+'T23:59:00-04:00', 'busy':[]}
        published = publish(root, data, 'morning-coffee')
        open_workspace(root, published['snapshot'])
        token = 'synthetic-learning-capability-' + 'x'*40
        server = ThreadingHTTPServer(('127.0.0.1',0), handler_for(data,root,token,workspace=True))
        worker = threading.Thread(target=server.serve_forever,daemon=True); worker.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=os.environ.get('CHROME_PATH','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
                page = browser.new_page(viewport={'width':1440,'height':1000})
                errors=[]; page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/report/{token}')
                if page.locator('#focus-exercise').is_hidden(): page.locator('[data-edit-schedule]').click()
                duration=page.locator('#day-duration-learning'); start=page.locator('#day-time-learning')
                expect(duration).to_have_value('30')
                duration.fill('45'); duration.dispatch_event('change')
                start.fill('14:30'); start.dispatch_event('change')
                expect(start).to_have_value('14:30')
                focus=page.locator('#day-time-focus')
                page.locator('#day-duration-focus').fill('30'); page.locator('#day-duration-focus').dispatch_event('change')
                focus.fill('15:15'); focus.dispatch_event('change')
                expect(focus).to_have_value('15:15')
                duration.fill('60'); duration.dispatch_event('change')
                expect(duration).to_have_value('45')
                expect(page.locator('.day-warning')).to_contain_text('overlaps')
                page.locator('.day-control[data-kind=focus] [data-remove]').click()
                duration.fill('16'); duration.dispatch_event('change')
                expect(duration).to_have_value('45')
                expect(page.locator('.day-warning')).to_contain_text('15-minute increments')
                page.locator('.plan-submit-button').click()
                expect(page.locator('.plan-submit-review')).to_contain_text('Reading / learning · 14:30–15:15')
                page.get_by_role('button',name='Submit plan',exact=True).click()
                expect(page.locator('#focus-exercise')).to_be_hidden()
                assert latest_plan(root,day,'America/Toronto')['blocks']==[{'kind':'learning','start':870,'minutes':45}]
                expect(page.locator('#today')).to_contain_text('Reading / learning')
                page.reload();page.locator('[data-edit-schedule]').click()
                expect(duration).to_have_value('45');expect(start).to_have_value('14:30')
                duration.fill('60');duration.dispatch_event('change')
                page.locator('.day-cancel').click();page.locator('[data-edit-schedule]').click()
                expect(duration).to_have_value('45')
                for width in [1440,728,390,320]:
                    page.set_viewport_size({'width':width,'height':1000})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), width
                    assert duration.is_visible()
                page.locator('#focus-exercise').screenshot(path='/tmp/morning-coffee-learning-qa.png')
                page.locator('.day-cancel').click()
                row=page.locator('#today [data-plan-source=local]').filter(has_text='Reading / learning')
                row.locator('[data-calendar-toggle]').click()
                expect(row.locator('[data-calendar-toggle]')).to_have_text('Undo done')
                row.locator('.day-remove-submitted').click()
                expect(page.locator('#today [data-plan-source=local]')).to_have_count(0)
                assert latest_plan(root,day,'America/Toronto')['blocks']==[]
                assert not errors, errors
                browser.close()
                print('PASS: default, validation, conflicts, authenticated save, reload, cancel, completion, removal and responsive widths 320–1440.')
        finally:
            server.shutdown();server.server_close();worker.join()


if __name__=='__main__': main()
