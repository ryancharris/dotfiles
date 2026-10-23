"""Exercise removal/restore and draft preservation in an isolated browser session.

Run: uv run --with playwright --python 3.12 tests/calendar_removal_browser_check.py
"""
from http.server import ThreadingHTTPServer
from pathlib import Path
import os
import sys
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect

SKILL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SKILL/'scripts'))
from local_plan_server import handler_for
from report_history import publish
from workspace_state import open_workspace
from test_report_history import snapshot


def main():
    with tempfile.TemporaryDirectory(prefix='coffee-calendar-remove-') as temporary:
        root=Path(temporary);data=snapshot()
        data['agenda']['events']=[{'id':'moved-meeting','title':'Moved 1:1','start':'2026-10-19T13:00:00-04:00',
            'end':'2026-10-19T13:30:00-04:00','time':'13:00–13:30','url':'https://example.com/meeting'}]
        data['availability']={'status':'complete','checked_at':data['collected_at'],'coverage':'Synthetic calendar',
            'window_start':'09:00','window_end':'17:00','busy':[{'start':'2026-10-19T13:00:00-04:00','end':'2026-10-19T13:30:00-04:00'}]}
        token='synthetic-removal-'+'x'*32
        published=publish(root,data,'morning-coffee');open_workspace(root,published['snapshot'])
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(data,root,token,workspace=True))
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROME_PATH','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
                page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/report/{token}')
                page.locator('#day-duration-focus').fill('30');page.locator('#day-duration-focus').dispatch_event('change')
                page.locator('#day-name-focus').fill('Keep my draft');page.locator('#day-name-focus').dispatch_event('input')
                page.locator('#day-time-focus').fill('13:00')
                page.locator('#day-time-focus').dispatch_event('change')
                assert page.locator('#focus-exercise').evaluate('(el)=>el.getDayPlan().blocks.find(b=>b.kind==="focus").start') is None
                task_input=page.locator('#todos input[name="title"]')
                if not task_input.count():task_input=page.locator('#todos input[type="text"]').first
                task_input.fill('Unsubmitted task draft')
                # Simulate saved mutation followed by failed report reload.
                original_fetch='window.originalFetch=window.fetch; window.failReport=true; window.fetch=(input,opts)=>{if(window.failReport&&String(input)===location.href&&(!opts?.method||opts.method==="GET"))return Promise.reject(Error("Synthetic view failure"));return window.originalFetch(input,opts);}'
                page.evaluate(original_fetch)
                page.get_by_role('button',name='Cancel: Moved 1:1',exact=True).click()
                expect(page.get_by_role('button',name='Refresh today',exact=True)).to_be_visible()
                expect(page.locator('.calendar-removal-status')).to_contain_text('saved locally')
                page.evaluate('window.failReport=false')
                page.get_by_role('button',name='Refresh today',exact=True).click()
                expect(page.locator('#today > .agenda [data-plan-source="calendar"]')).to_have_count(0)
                expect(page.locator('#day-name-focus')).to_have_value('Keep my draft')
                expect(task_input).to_have_value('Unsubmitted task draft')
                expect(page.locator('.day-fixed')).to_have_count(0)
                page.locator('#day-time-focus').fill('13:00')
                page.locator('#day-time-focus').dispatch_event('change')
                assert page.locator('#focus-exercise').evaluate('(el)=>el.getDayPlan().blocks.find(b=>b.kind==="focus").start')==780
                page.get_by_role('button',name='Review & submit plan').click()
                page.get_by_role('button',name='Submit plan',exact=True).click()
                expect(page.locator('#today [data-plan-source="local"]')).to_have_count(1)
                page.reload()
                expect(page.locator('#today > .agenda [data-plan-source="calendar"]')).to_have_count(0)
                page.locator('#removed-calendar-events summary').click()
                page.get_by_role('button',name='Restore to today: Moved 1:1',exact=True).click()
                expect(page.locator('#today > .agenda [data-plan-source="calendar"]')).to_have_count(1)
                expect(page.locator('#today [data-plan-source="local"]')).to_contain_text('Overlaps calendar')
                page.locator('#today [data-plan-source="local"] .day-remove-submitted').click()
                expect(page.locator('#today [data-plan-source="local"]')).to_have_count(0)
                expect(page.locator('#today > .agenda [data-plan-source="calendar"]')).to_have_count(1)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert not errors,errors
                browser.close()
                print('Browser removal, saved-view retry, draft preservation, freed-slot submission, reload, restore, conflict and mobile checks passed.')
        finally:server.shutdown();server.server_close();worker.join()

if __name__=='__main__':main()
