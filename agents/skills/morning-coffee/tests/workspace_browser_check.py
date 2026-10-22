"""Browser integration with a synthetic bridge; this does not verify a real T3 connection.

Run: uv run --with playwright --python 3.12 tests/workspace_browser_check.py
Uses an installed Chrome (CHROME_PATH overrides the macOS default). All writes use a temp root.
"""
from copy import deepcopy
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, expect

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_plan_server import handler_for
from plan_submission import latest_plan, save_plan
from report_history import publish
from todo_state import load_todos, save_todo_action
from workspace_state import configure_bridge, complete_refresh, load_workspace, open_workspace
from test_report_history import snapshot


def main():
    with tempfile.TemporaryDirectory(prefix='coffee-workspace-browser-') as temporary:
        root = Path(temporary)
        day = datetime.now(ZoneInfo('America/Toronto')).date().isoformat()
        data = snapshot('09:00', day=day)
        data['report']['preview_label'] = 'A long source coverage label that must wrap without expanding the mobile viewport'
        data['priorities'].append(dict(data['priorities'][0], id='priority:second', title='Second chosen priority'))
        data['availability'] = {'status':'complete', 'checked_at':data['collected_at'], 'coverage':'Synthetic calendar',
            'window_start':'08:30', 'window_end':'17:00', 'coverage_start':day+'T00:00:00-04:00',
            'coverage_end':day+'T23:59:00-04:00', 'busy':[]}
        original = publish(root, data, 'morning-coffee')
        legacy = publish(root, dict(data, collected_at=day+'T09:01:00-04:00'), 'tea-time')
        open_workspace(root, legacy['snapshot'])
        task = save_todo_action(root, {'action':'add','title':'Keep local task','project_tags':['Transport']})['item']
        archived_donor = save_todo_action(root, {'action':'add','title':'Archived tag donor','project_tags':['ArchivedOnly']})['item']
        save_todo_action(root, {'action':'remove','id':archived_donor['id']})
        save_plan(root, data, {'date':day,'timezone':'America/Toronto','blocks':[{'kind':'dog_walk','start':780,'minutes':30}]})
        received = []
        fail_bridge = threading.Event()
        class Bridge(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(503 if fail_bridge.is_set() else 204); self.end_headers()
        bridge = ThreadingHTTPServer(('127.0.0.1',0), Bridge)
        worker = threading.Thread(target=bridge.serve_forever,daemon=True); worker.start()
        configure_bridge(root, {'webhook_url':f'http://127.0.0.1:{bridge.server_port}/private-hook',
                                'thread_url':'t3-thread://v1/synthetic-browser-test'})
        token = 'synthetic-browser-capability-'+'x'*40
        server = ThreadingHTTPServer(('127.0.0.1',0), handler_for(data,root,token,workspace=True))
        serving = threading.Thread(target=server.serve_forever,daemon=True); serving.start()
        # The fixture's source clock advances from 09:00 to 12:00. Keep the
        # request clock at 09:30 so its callback genuinely collects afterward.
        request_clock = patch('workspace_state._now', return_value=datetime.fromisoformat(day+'T09:30:00-04:00'))
        request_clock.start()
        presentation_clock=patch('local_plan_server.datetime')
        presentation_time=presentation_clock.start()
        presentation_time.now.return_value=datetime.fromisoformat(day+'T09:30:00-04:00')
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=os.environ.get('CHROME_PATH','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
                page = browser.new_page(viewport={'width':1440,'height':1000})
                clock=int(datetime.fromisoformat(day+'T09:00:00-04:00').timestamp()*1000)
                page.add_init_script('Date.now = () => '+str(clock))
                errors=[]; page.on('pageerror',lambda error:errors.append(str(error)))
                url=f'http://127.0.0.1:{server.server_port}/report/{token}'
                page.goto(url)
                expect(page.locator('#daily-briefing #daily-priorities')).to_have_count(1)
                expect(page.locator('#daily-briefing #yesterday')).to_have_count(1)
                assert page.locator('#daily-briefing').evaluate('node => Boolean(node.compareDocumentPosition(document.querySelector("#todos")) & Node.DOCUMENT_POSITION_FOLLOWING)')
                expect(page.locator('body')).to_have_class('coffee')
                expect(page.locator('h1')).to_have_text('Morning Coffee')
                presentation_time.now.return_value=datetime.fromisoformat(day+'T10:00:00-04:00')
                page.reload()
                expect(page.locator('body')).to_have_class('tea')
                expect(page.locator('h1')).to_have_text('Tea Time')
                expect(page.locator('.eyebrow')).to_contain_text('TEA BREAK')
                expect(page.locator('.date')).to_contain_text('Steeped at')
                page.locator('.shop-sign').screenshot(path='/tmp/morning-coffee-tea-header.png')
                expect(page.locator('.pixel-mascot')).to_have_class('pixel-mascot tea-sprite')
                expect(page.locator('#today .day-remove-submitted')).to_have_count(1)
                def assert_links_open_safely():
                    links=page.locator('a[href]').evaluate_all("links=>links.map(a=>({href:a.getAttribute('href'),target:a.target,rel:a.rel.toLowerCase().split(/\\s+/)}))")
                    assert all(not link['target'] if link['href'].startswith('#') else link['target']=='_blank' and {'noopener','noreferrer'}.issubset(set(link['rel'])) for link in links), links
                assert_links_open_safely()
                # Finish events early, undo after their end time, and retain
                # explicit choices across reloads without changing source facts.
                calendar_row=page.locator('#today [data-plan-source=calendar]')
                calendar_block=page.locator('.day-fixed[data-calendar-key]')
                expect(calendar_row).not_to_have_class(re.compile('calendar-done'))
                calendar_row.locator('[data-calendar-toggle]').click()
                expect(page.locator('.calendar-completion-status')).to_have_text('Marked done locally.')
                expect(calendar_row).to_have_class(re.compile('calendar-done'))
                expect(calendar_block).to_have_class(re.compile('calendar-done'))
                page.reload()
                expect(calendar_row.locator('[data-calendar-toggle]')).to_have_text('Undo done')
                page.locator('[data-edit-schedule]').click()
                calendar_block.locator('[data-calendar-toggle]').click()
                expect(page.locator('.calendar-completion-status')).to_have_text('Marked not done locally.')
                page.evaluate('Date.now = () => '+str(clock+12*3600000)+'; BriefUI.updateCalendarPast(document)')
                expect(calendar_row).to_have_class(re.compile('calendar-past'))
                expect(calendar_row).not_to_have_class(re.compile('calendar-done'))
                page.reload()
                expect(calendar_row).not_to_have_class(re.compile('calendar-done'))
                # A failed acknowledgement keeps the confirmed mark and editor.
                page.route('**/calendar/done',lambda route:route.fulfill(status=500,json={'error':'Synthetic save failure'}))
                calendar_row.locator('[data-calendar-toggle]').click()
                expect(page.locator('.calendar-completion-status')).to_contain_text('not confirmed')
                expect(calendar_row).not_to_have_class(re.compile('calendar-done'))
                page.unroute('**/calendar/done')
                calendar_row.locator('[data-calendar-toggle]').click()
                expect(page.locator('.calendar-completion-status')).to_have_text('Marked done locally.')
                local_row=page.locator('#today [data-plan-source=local]')
                local_row.locator('[data-calendar-toggle]').click()
                expect(page.locator('.calendar-completion-status')).to_have_text('Marked done locally.')
                expect(local_row).to_have_class(re.compile('calendar-done'))
                expect(page.locator('.day-block[data-kind=dog_walk]')).to_have_class(re.compile('calendar-done'))
                todo=page.locator('#todos')
                todo.locator('.todo-add [name=title]').fill('Unsaved task draft')
                add_picker=todo.locator('.todo-add .project-tag-choices')
                expect(add_picker.locator('option')).to_have_count(4)
                assert set(add_picker.locator('option').evaluate_all('options=>options.map(option=>option.value)'))=={'','tag:Transport','tag:ArchivedOnly','__create__'}
                assert add_picker.get_attribute('aria-label')=='Choose an existing project tag or create one'
                # Selected projects are draft chips, with one picker rather than
                # a duplicate CSV field. Removing one must not edit saved tasks.
                add_picker.select_option('tag:Transport')
                todo.get_by_role('button',name='Remove project tag Transport',exact=True).click()
                expect(todo.locator('.todo-add [name=project_tags]')).to_have_value('')
                assert load_todos(root)[0]['project_tags']==['Transport']
                add_picker.select_option('__create__')
                todo.locator('.todo-add .project-tag-create input').fill('Draft project')
                todo.locator('.todo-add .project-tag-create button').filter(has_text='Add tag').click()
                expect(todo.locator('.todo-add [name=project_tags]')).to_be_hidden()
                expect(todo.get_by_role('button',name='Remove project tag Draft project',exact=True)).to_be_visible()
                position='el=>{const r=el.getBoundingClientRect();return [r.x,r.y+scrollY,r.width,r.height];}'
                title_box=todo.locator('.todo-add [name=title]').evaluate(position)
                button_box=todo.locator('.todo-add button[type=submit]').evaluate(position)
                add_picker.select_option('__create__')
                add_form=todo.locator('.todo-add-projects')
                assert todo.locator('.todo-add [name=title]').evaluate(position)==title_box, 'Opening tag creation must not move the task field'
                assert todo.locator('.todo-add button[type=submit]').evaluate(position)==button_box, 'Opening tag creation must not move Add task'
                artifacts=os.environ.get('COFFEE_BROWSER_ARTIFACTS')
                if artifacts:
                    folder=Path(artifacts);folder.mkdir(parents=True,exist_ok=True)
                    for width in (1440,1000,650,390,320):
                        page.set_viewport_size({'width':width,'height':1100})
                        todo.screenshot(path=str(folder/f'todo-create-{width}.png'))
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'Overflow at {width}px'
                    page.set_viewport_size({'width':1440,'height':1000})
                add_form.locator('.project-tag-create input').fill('Discard this picker draft')
                add_form.locator('.project-tag-create button').filter(has_text='Cancel').click()
                expect(todo.locator('.todo-add [name=project_tags]')).to_have_value('Draft project')
                expect(add_form.locator('.project-tag-create')).to_be_hidden()
                expect(add_picker).to_be_focused()
                if artifacts:
                    for width in (1000,390,320):
                        page.set_viewport_size({'width':width,'height':1100})
                        todo.screenshot(path=str(folder/f'todo-ready-{width}.png'))
                    page.set_viewport_size({'width':1440,'height':1000})
                todo.locator('[data-todo-project-filter]').select_option('tag:Transport')
                entry=todo.locator('[data-todo-id="'+task['id']+'"]')
                more=entry.locator(':scope > .todo-entry .todo-more')
                more.locator('summary').click()
                expect(more).to_have_attribute('open','')
                more.locator('summary').press('Escape')
                expect(more).not_to_have_attribute('open','')
                expect(more.locator('summary')).to_be_focused()
                more.locator('summary').click()
                todo.locator('.todo-add [name=title]').click()
                expect(more).not_to_have_attribute('open','')
                more.locator('summary').click()
                entry.locator('[data-todo-action=edit]').click()
                edit_form=entry.locator('.todo-edit-form')
                edit_title=edit_form.locator('[name=title]')
                expect(edit_title).to_be_focused()
                expect(edit_title).to_have_value('Keep local task')
                edit_title.fill('Discard this rename')
                edit_title.press('Escape')
                expect(edit_form).to_have_count(0)
                expect(more.locator('summary')).to_be_focused()
                expect(entry.locator('.todo-title')).to_have_text('Keep local task')
                more.locator('summary').click()
                entry.locator('[data-todo-action=edit]').click()
                edit_title.fill('Edited local task')
                def reject_edit(route):
                    route.fulfill(status=503,json={'ok':False,'error':'Synthetic task save failure.'})
                page.route('**/todo',reject_edit)
                edit_form.get_by_role('button',name='Save changes').click()
                expect(todo.locator('.todo-status')).to_contain_text('Synthetic task save failure.')
                expect(edit_title).to_have_value('Edited local task')
                expect(entry.locator('.todo-title')).to_have_text('Keep local task')
                page.unroute('**/todo',reject_edit)
                if artifacts:
                    for width in (1000,390,320):
                        page.set_viewport_size({'width':width,'height':1100})
                        entry.screenshot(path=str(folder/f'todo-edit-{width}.png'))
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
                    page.set_viewport_size({'width':1440,'height':1000})
                more.locator('summary').click()
                entry.locator('[data-todo-action=projects]').click()
                project_form=entry.locator('.todo-project-form')
                project_csv=project_form.locator('[name=project_tags]')
                picker=project_form.locator('.project-tag-choices')
                expect(picker.locator('option')).to_have_count(4)
                assert set(picker.locator('option').evaluate_all('options=>options.map(option=>option.value)'))=={'','tag:Transport','tag:ArchivedOnly','__create__'}
                expect(picker.locator('option[value="tag:Transport"]')).to_be_disabled()
                picker.select_option('tag:ArchivedOnly')
                expect(project_csv).to_have_value('Transport, ArchivedOnly')
                picker.select_option('__create__')
                new_tag=project_form.locator('.project-tag-create input')
                create_status=project_form.locator('.project-tag-picker-status')
                new_tag.fill('transport')
                project_form.locator('.project-tag-create button').filter(has_text='Add tag').click()
                expect(create_status).to_have_text('That tag is already selected.')
                expect(project_csv).to_have_value('Transport, ArchivedOnly')
                new_tag.fill('Comma, splits')
                project_form.locator('.project-tag-create button').filter(has_text='Add tag').click()
                expect(create_status).to_have_text('Enter one tag, up to 60 characters, without commas.')
                new_tag.fill('x'*61)
                project_form.locator('.project-tag-create button').filter(has_text='Add tag').click()
                expect(create_status).to_have_text('Enter one tag, up to 60 characters, without commas.')
                new_tag.fill('  Private   Link  ')
                # Keep this new name pending in the picker while tab/star/source
                # rerenders replace the inline form.
                todo.locator('[data-todo-filter=completed]').click()
                expect(entry).to_be_hidden()
                todo.locator('[data-todo-filter=pending]').click()
                expect(project_form.locator('.project-tag-create')).to_be_visible()
                expect(new_tag).to_have_value('  Private   Link  ')
                expect(edit_title).to_have_value('Edited local task')
                entry.locator('[data-todo-action=set_importance]').click()
                expect(todo.locator('.todo-status')).to_have_text('Saved locally: task marked high importance.')
                expect(project_form.locator('.project-tag-create')).to_be_visible()
                expect(new_tag).to_have_value('  Private   Link  ')
                page.locator('[data-edit-schedule]').click()
                page.locator('#day-time-focus').fill('14:00')
                page.locator('#day-time-focus').dispatch_event('change')
                draft_revision=page.evaluate('document.querySelector("#focus-exercise").planSubmission.getBaseRevision()')
                page.locator('[data-filter=text]').fill('retained filter')
                page.evaluate('window.originalTodo=document.querySelector("#todos");window.scrollTo(0,600)')
                before=page.evaluate('scrollY')
                # Trigger through the real authenticated page HTTP path, then keep working locally.
                page.locator('[data-workspace-refresh]').click()
                expect(page.locator('[data-workspace-refresh]')).to_be_disabled()
                other=browser.new_page();other.goto(url)
                expect(other.locator('[data-workspace-refresh]')).to_be_disabled()
                # Another tab saves a newer plan while this tab retains its
                # editor draft. Source replacement must not silently rebase it.
                newer_plan=other.evaluate("""async () => {
                  const config=JSON.parse(document.querySelector('.plan-submit-data').textContent);
                  const response=await fetch(config.endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-Brief-Token':config.token},
                    body:JSON.stringify({date:document.querySelector('#focus-exercise').getDayPlan().date,
                      timezone:'America/Toronto',base_revision:config.base_revision,blocks:[{kind:'dog_walk',start:795,minutes:30}]})});
                  return {status:response.status,...await response.json()};
                }""")
                assert newer_plan['status']==200,newer_plan
                entry.locator('[data-todo-action=set_importance]').click()
                expect(todo.locator('.todo-status')).to_have_text('Saved locally: high importance removed.')
                expect(project_form.locator('.project-tag-create')).to_be_visible()
                expect(new_tag).to_have_value('  Private   Link  ')
                assert len(received)==1, received
                request_id=received[0]['refresh_id']
                assert received[0]['request_id']==request_id
                page.evaluate('window.scrollTo(0,600)');before=page.evaluate('scrollY')
                fresh=deepcopy(data);fresh['collected_at']=day+'T12:00:00-04:00';fresh['report']['time']='12:00'
                fresh['availability'].update(checked_at=fresh['collected_at'],window_end='16:30')
                fresh['agenda']['events'][0]['title']='Refreshed source meeting'
                fresh['priorities']=[dict(data['priorities'][0],title='Updated chosen source fact'), data['priorities'][1]]
                fresh['work_suggestions']=[{'id':'source:new-work','material_key':'request-event:1','title':'Proposed new task',
                    'action':'Check the verified source','source_url':'https://example.com/new','project_tags':['Transport']}]
                published=publish(root,fresh,'refresh')
                presentation_time.now.return_value=datetime.fromisoformat(day+'T17:00:00-04:00')
                disclosures=page.locator('#daily-briefing .priority-action details')
                expect(disclosures).to_have_count(2)
                disclosures.nth(0).locator('summary').focus()
                disclosures.nth(0).locator('summary').press('Enter')
                focused_summary=disclosures.nth(0).locator('summary').get_attribute('id')
                page.evaluate('window.scrollTo(0,600)');before=page.evaluate('scrollY')
                complete_refresh(root,published['snapshot'],request_id)
                expect(page.locator('#today')).to_contain_text('Refreshed source meeting',timeout=10000)
                expect(page.locator('#'+focused_summary)).to_be_focused()
                expect(disclosures.nth(0)).to_have_attribute('open','')
                expect(disclosures.nth(1)).not_to_have_attribute('open','')
                expect(page.locator('#daily-briefing')).to_have_count(1)
                expect(calendar_row).to_have_class(re.compile('calendar-done'))
                expect(page.locator('body')).to_have_class('coffee')
                expect(page.locator('h1')).to_have_text('Morning Coffee')
                assert page.evaluate('originalTodo===document.querySelector("#todos")')
                expect(todo.locator('.todo-add [name=title]')).to_have_value('Unsaved task draft')
                expect(todo.locator('.todo-add [name=project_tags]')).to_have_value('Draft project')
                expect(todo.locator('[data-todo-project-filter]')).to_have_value('tag:Transport')
                expect(project_csv).to_have_value('Transport, ArchivedOnly')
                expect(project_form.locator('.project-tag-create')).to_be_visible()
                expect(new_tag).to_have_value('  Private   Link  ')
                assert_links_open_safely()
                expect(page.locator('[data-filter=text]')).to_have_value('retained filter')
                expect(page.locator('#focus-exercise')).to_be_visible()
                expect(page.locator('#day-time-focus')).to_have_value('14:00')
                assert page.evaluate('document.querySelector("#focus-exercise").planSubmission.getBaseRevision()')==draft_revision
                assert page.evaluate('document.querySelector("#focus-exercise").getDayPlan().blocks.find(row=>row.kind==="focus").max_end')==990, 'draft restoration keeps freshly checked bounds'
                assert abs(page.evaluate('scrollY')-before)<=1, 'source updates preserve window scroll'
                assert page.evaluate('performance.getEntriesByType("navigation").length')==1
                assert len(load_todos(root))==1, 'refresh must not automatically accept proposed tasks'
                page.locator('.plan-submit-button').click()
                page.get_by_role('button',name='Submit plan',exact=True).click()
                expect(page.locator('.plan-submit-status')).to_contain_text('Your saved plan changed.')
                expect(page.locator('#day-time-focus')).to_have_value('14:00')
                expect(page.locator('#focus-exercise')).to_be_visible()
                assert latest_plan(root,day,'America/Toronto')['blocks']==[{'kind':'dog_walk','start':795,'minutes':30}]
                # Submitting while Create new tag is still open commits it into
                # the CSV field and uses the normal acknowledged task-tag save.
                project_form.locator('button[type=submit]').click()
                expect(todo.locator('.todo-status')).to_have_text('Saved locally: project tags saved.')
                saved_task=next(item for item in load_todos(root) if item['id']==task['id'])
                assert saved_task['project_tags']==['Transport','ArchivedOnly','Private Link'], saved_task
                expect(entry.locator('.todo-project-form')).to_have_count(0)
                expect(page.locator('#what-changed')).to_contain_text('Proposed new task')
                # Dismiss survives the same material version; another accepted version creates one tagged task.
                dismissed_fingerprint=page.locator('[data-suggestion-action=dismiss]').get_attribute('data-suggestion-fingerprint')
                page.locator('[data-suggestion-action=dismiss]').click()
                expect(page.locator('#what-changed')).not_to_contain_text('Proposed new task')
                expect(page.locator('#what-changed')).to_be_hidden()
                fresh['collected_at']=day+'T12:01:00-04:00';fresh['work_suggestions'][0]['material_key']='request-event:2'
                complete_refresh(root,publish(root,fresh,'refresh')['snapshot'])
                expect(page.locator('#what-changed')).to_contain_text('Proposed new task',timeout=10000)
                stale_choice=page.evaluate("""async fingerprint => {
                  const config=JSON.parse(document.querySelector('.workspace-interaction-data').textContent);
                  const response=await fetch(config.suggestion_endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-Brief-Token':config.token},
                    body:JSON.stringify({id:'source:new-work',action:'accept',fingerprint})});
                  return response.status;
                }""",dismissed_fingerprint)
                assert stale_choice==409,stale_choice
                assert len(load_todos(root))==1,'a stale action cannot accept unseen material work'
                page.locator('[data-suggestion-action=accept]').click()
                expect(page.locator('#what-changed')).not_to_contain_text('Proposed new task')
                expect(page.locator('#what-changed')).to_be_hidden()
                added=next(item for item in load_todos(root) if item['title']=='Proposed new task')
                assert added['project_tags']==['Transport']
                expect(todo.locator('.todo-add [name=title]')).to_have_value('Unsaved task draft')
                expect(edit_title).to_have_value('Edited local task')
                # A lost response after a durable write must allow the same
                # title edit to be retried without a false stale-title error.
                def lose_edit_ack(route):
                    response=route.fetch()
                    assert response.ok
                    route.fulfill(status=503,json={'ok':False,'error':'Synthetic lost acknowledgement.'})
                page.route('**/todo',lose_edit_ack)
                edit_form.get_by_role('button',name='Save changes').click()
                expect(todo.locator('.todo-status')).to_contain_text('Synthetic lost acknowledgement.')
                expect(edit_title).to_have_value('Edited local task')
                page.unroute('**/todo',lose_edit_ack)
                edit_form.get_by_role('button',name='Save changes').click()
                expect(todo.locator('.todo-status')).to_have_text('Saved locally: task updated.')
                expect(edit_form).to_have_count(0)
                expect(entry.locator('.todo-title')).to_have_text('Edited local task')
                persisted_view=browser.new_page();persisted_view.goto(url)
                expect(persisted_view.locator('[data-todo-id="'+task['id']+'"] .todo-title')).to_have_text('Edited local task')
                persisted_view.close()
                # Cancel discards editor draft; narrow removal updates Today and hides the editor.
                page.locator('.day-cancel').click();expect(page.locator('#focus-exercise')).to_be_hidden()
                page.locator('#today .day-remove-submitted').click()
                expect(page.locator('#today [data-plan-source=local]')).to_have_count(0)
                expect(page.locator('#today [data-plan-source=calendar]')).to_have_count(1)
                assert latest_plan(root,day,'America/Toronto')['blocks']==[]
                expect(todo.locator('.todo-add [name=title]')).to_have_value('Unsaved task draft')
                # Dispatch errors stay honest without exposing assistant setup/backend messages.
                fail_bridge.set()
                page.locator('[data-workspace-refresh]').click()
                expect(page.locator('[data-workspace-status]')).to_have_text('Refresh failed. Your previous report is still shown.',timeout=10000)
                assert 'T3' not in page.locator('#workspace-controls').inner_text()
                expect(page.locator('#today')).to_contain_text('Refreshed source meeting')
                # Missing bridge is explained, while the page's local task path stays operational.
                configure_bridge(root, {'thread_url':'t3-thread://v1/synthetic-browser-test'})
                page.reload();expect(page.locator('[data-workspace-refresh]')).to_be_disabled()
                expect(page.locator('[data-workspace-status]')).to_have_text('Source refresh is currently unavailable.')
                expect(page.locator('[data-workspace-refresh-label]')).to_have_text('Refresh')
                expect(page.locator('[data-workspace-thread]')).to_have_count(0)
                assert 'T3' not in page.locator('#workspace-controls').inner_text()
                # Custom focus durations persist through authenticated saves,
                # reloads and cancellation; resizing still rejects conflicts.
                page.locator('[data-edit-schedule]').click()
                duration=page.locator('#day-duration-focus')
                focus_name=page.locator('#day-name-focus')
                focus_name.fill('Migration review <draft>')
                focus_name.dispatch_event('change')
                expect(duration).to_have_value('120')
                duration.fill('45');duration.dispatch_event('change')
                page.locator('#day-time-focus').fill('13:30')
                page.locator('#day-time-focus').dispatch_event('change')
                page.locator('.plan-submit-button').click()
                page.get_by_role('button',name='Submit plan',exact=True).click()
                expect(page.locator('#focus-exercise')).to_be_hidden()
                assert latest_plan(root,day,'America/Toronto')['blocks']==[{'kind':'focus','start':810,'minutes':45,'name':'Migration review <draft>'}]
                expect(page.locator('#today')).to_contain_text('Migration review <draft>')
                expect(page.locator('#today')).not_to_contain_text('Local chosen plan')
                page.reload()
                page.locator('[data-edit-schedule]').click()
                expect(duration).to_have_value('45')
                expect(focus_name).to_have_value('Migration review <draft>')
                expect(page.locator('#day-time-focus')).to_have_value('13:30')
                exercise=page.locator('#day-time-exercise')
                exercise.fill('14:15');exercise.dispatch_event('change')
                duration.fill('60');duration.dispatch_event('change')
                expect(duration).to_have_value('45')
                expect(page.locator('.day-warning')).to_contain_text('overlaps')
                page.locator('.day-control[data-kind=exercise] [data-remove]').click()
                duration.fill('150');duration.dispatch_event('change')
                focus_name.fill('Unsaved rename');focus_name.dispatch_event('change')
                expect(duration).to_have_value('150')
                page.locator('.day-cancel').click()
                page.locator('[data-edit-schedule]').click()
                expect(duration).to_have_value('45')
                expect(focus_name).to_have_value('Migration review <draft>')
                assert latest_plan(root,day,'America/Toronto')['blocks']==[{'kind':'focus','start':810,'minutes':45,'name':'Migration review <draft>'}]
                focus_name.fill('');focus_name.dispatch_event('change')
                page.locator('.plan-submit-button').click()
                page.get_by_role('button',name='Submit plan',exact=True).click()
                expect(page.locator('#focus-exercise')).to_be_hidden()
                page.reload()
                assert latest_plan(root,day,'America/Toronto')['blocks']==[{'kind':'focus','start':810,'minutes':45}]
                expect(page.locator('#today')).to_contain_text('Focus')
                page.locator('[data-edit-schedule]').click()
                expect(focus_name).to_have_value('')
                # Creating work must reveal it even when the old status/project
                # excludes it. Compatible filters remain the user's choice.
                todo.locator('[data-todo-filter=completed]').click()
                todo.locator('[data-todo-project-filter]').select_option('tag:Transport')
                todo.locator('.todo-add [name=title]').fill('New task outside old filters')
                todo.locator('.todo-add button[type=submit]').click()
                expect(todo.locator('.todo-status')).to_have_text('Saved locally: task added.')
                expect(todo.locator('[data-todo-filter=pending]')).to_have_attribute('aria-selected','true')
                expect(todo.locator('[data-todo-project-filter]')).to_have_value('')
                expect(todo.get_by_text('New task outside old filters',exact=True)).to_be_visible()
                todo.locator('[data-todo-filter=all]').click()
                todo.locator('[data-todo-project-filter]').select_option('tag:Transport')
                todo.locator('.todo-add .project-tag-choices').select_option('tag:Transport')
                todo.locator('.todo-add [name=title]').fill('Offline local task')
                todo.locator('.todo-add button[type=submit]').click()
                expect(todo.locator('.todo-status')).to_have_text('Saved locally: task added.')
                expect(todo.locator('[data-todo-filter=all]')).to_have_attribute('aria-selected','true')
                expect(todo.locator('[data-todo-project-filter]')).to_have_value('tag:Transport')
                expect(todo.get_by_text('Offline local task',exact=True)).to_be_visible()
                for width in [1440,728,650,390,320]:
                    page.set_viewport_size({'width':width,'height':1000})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), width
                page.locator('#focus-exercise').screenshot(path='/tmp/morning-coffee-calendar-mobile.png')
                page.screenshot(path='/tmp/morning-coffee-workspace-mobile.png',full_page=True)
                page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path='/tmp/morning-coffee-workspace-desktop.png',full_page=True)
                page.locator('#today').screenshot(path='/tmp/morning-coffee-today-actions.png')
                assert not errors,errors
                assert Path(original['snapshot']).exists()
                assert load_workspace(root)['date']==day
                browser.close()
                print('PASS: synthetic authenticated refresh, deduped tabs, in-place facts, retained task/tag/plan drafts and review filters, local edits during refresh, explicit suggestions, immutable history, saved plan removal, manual calendar completion/undo/failure/reload/refresh, custom focus duration save/reload/cancel/conflict checks, offline local saves, responsive layouts. Real T3 bridge remains a separate acceptance check.')
        finally:
            server.shutdown();server.server_close();serving.join()
            bridge.shutdown();bridge.server_close();worker.join()
            presentation_clock.stop()
            request_clock.stop()


if __name__=='__main__': main()
