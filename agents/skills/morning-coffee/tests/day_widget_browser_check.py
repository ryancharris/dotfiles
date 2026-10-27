"""Exercise the combined calendar widget and dated tasks in an isolated workspace.

Run: uv run --with playwright python tests/day_widget_browser_check.py
"""
from copy import deepcopy
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
import os
import json
from pathlib import Path
import sys
import tempfile
import threading
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_plan_server import handler_for
from plan_submission import latest_plan
from report_history import publish
from todo_state import load_todos, save_todo_action
from workspace_state import complete_refresh, open_workspace
from test_report_history import snapshot


def main():
    with tempfile.TemporaryDirectory(prefix='coffee-day-widget-') as temporary:
        root = Path(temporary)
        zone = 'America/Toronto'
        day = datetime.now(ZoneInfo(zone)).date()
        data = snapshot('09:00', day=day.isoformat())
        event = data['agenda']['events'][0]
        event.update(start=day.isoformat()+'T10:00:00-04:00', end=day.isoformat()+'T10:30:00-04:00')
        data['availability'] = {'status':'complete', 'checked_at':data['collected_at'],
            'coverage':'Synthetic calendar', 'window_start':'08:30', 'window_end':'17:00',
            'coverage_start':day.isoformat()+'T00:00:00-04:00', 'coverage_end':day.isoformat()+'T23:59:00-04:00',
            'busy':[{'start':event['start'],'end':event['end'],'event_id':event['id']}]}
        original = publish(root, data, 'morning-coffee')
        open_workspace(root, original['snapshot'])
        ids={}
        for name, date in [('Today task', day), ('Old task', day-timedelta(days=1)), ('New task', day), ('Future task', day+timedelta(days=1)), ('Legacy task', day)]:
            request={'action':'add','title':name,'task_date':date.isoformat()}
            if name=='Old task':request['project_tags']=['Older']
            ids[name]=save_todo_action(root, request)['item']['id']
        active_child=save_todo_action(root,{'action':'add','title':'Nested child','parent_id':ids['New task'],'task_date':(day-timedelta(days=2)).isoformat()})['item']
        store_path=root/'todos/state.json';store=json.loads(store_path.read_text())
        next(item for item in store['items'] if item['id']==ids['Legacy task']).pop('task_date')
        store_path.write_text(json.dumps(store))
        for name, offset in [('Archived yesterday',1),('Archived before',2)]:
            instant=datetime.combine(day-timedelta(days=offset),datetime.min.time().replace(hour=12),ZoneInfo(zone))
            task=save_todo_action(root,{'action':'add','title':name},now=instant,timezone_name=zone)['item']
            save_todo_action(root,{'action':'remove','id':task['id']},now=instant,timezone_name=zone)
        instant=datetime.combine(day-timedelta(days=1),datetime.min.time().replace(hour=12),ZoneInfo(zone))
        archived_parent=save_todo_action(root,{'action':'add','title':'Archived parent'},now=instant,timezone_name=zone)['item']
        archived_child=save_todo_action(root,{'action':'add','title':'Archived child','parent_id':archived_parent['id']},now=instant,timezone_name=zone)['item']
        save_todo_action(root,{'action':'clear','ids':[archived_parent['id'],archived_child['id']],'status':'all'},now=instant,timezone_name=zone)
        token='synthetic-day-widget-'+'x'*40
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(data,root,token,workspace=True))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as playwright:
                browser=playwright.chromium.launch(executable_path=os.environ.get(
                    'CHROME_PATH','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True)
                page=browser.new_page(viewport={'width':1000,'height':1000})
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/report/{token}')
                assert page.locator('#reviews-waiting').bounding_box()['y'] < page.locator('#rfcs-to-review').bounding_box()['y']
                today=page.locator('#today');read=today.locator('[data-today-read]');editor=today.locator('#focus-exercise')
                expect(read).to_be_visible();expect(editor).to_be_hidden()
                assert page.locator('#focus-exercise').count()==1
                headings=page.locator('#todos .todo-day-heading').all_text_contents()
                assert headings==['Today',(day-timedelta(days=1)).isoformat(),(day+timedelta(days=1)).isoformat()],headings
                expect(page.locator('#todos [data-todo-id="'+ids['New task']+'"] [data-todo-id="'+active_child['id']+'"]')).to_have_count(1)
                page.locator('#todos [data-todo-project-filter]').select_option('tag:Older')
                filtered=page.locator('#todos .todo-day-heading').all_text_contents()
                assert filtered==['Today',(day-timedelta(days=1)).isoformat()],filtered
                page.locator('#todos [data-todo-project-filter]').select_option('')
                task=page.locator('#todos [data-todo-id="'+ids['Today task']+'"]')
                task.locator('[data-todo-drag]').click()
                task.locator('.todo-move-form [name=target_id]').select_option(ids['Old task'])
                task.locator('.todo-move-form [name=placement]').select_option('after')
                task.get_by_role('button',name='Move task',exact=True).click()
                expect(page.locator('#todos .todo-move-status')).to_contain_text('same day')
                task.locator('.todo-move-form [name=target_id]').select_option(ids['Legacy task'])
                task.locator('.todo-move-form [name=placement]').select_option('after')
                task.get_by_role('button',name='Move task',exact=True).click()
                expect(page.locator('#todos .todo-row').first).to_have_attribute('data-todo-id',ids['New task'])
                order=page.locator('#todos .todo-list > .todo-row').evaluate_all('rows=>rows.map(row=>row.dataset.todoId)')
                assert order==[ids['New task'],ids['Legacy task'],ids['Today task'],ids['Old task'],ids['Future task']],(order,ids)
                headings=page.locator('#todos .todo-day-heading').all_text_contents()
                assert headings==['Today',(day-timedelta(days=1)).isoformat(),(day+timedelta(days=1)).isoformat()],headings
                page.locator('#todos [data-todo-filter=archive]').click()
                headings=page.locator('#todos .todo-day-heading').all_text_contents()
                assert headings==[(day-timedelta(days=1)).isoformat(),(day-timedelta(days=2)).isoformat()],headings
                parent=page.locator('#todos [data-todo-id="'+archived_parent['id']+'"]')
                expect(parent.locator('[data-todo-id="'+archived_child['id']+'"]')).to_have_count(1)
                page.locator('#todos [data-todo-filter=all]').click()
                # An unchanged status poll must still advance Today after local midnight.
                state=load_todos(root,with_warnings=True,timezone_name=zone)
                result={'ok':True,'todos':state['todos'],'archive':state['todo_archive']}
                tomorrow=datetime.combine(day+timedelta(days=1),datetime.min.time().replace(hour=12),ZoneInfo(zone)).isoformat()
                page.evaluate('''value=>{window.realDate=Date;window.Date=class extends Date{constructor(...args){super(...(args.length?args:[value]));}};}''',tomorrow)
                page.evaluate('result=>document.querySelector("#todos").applyConfirmedTasks(result)',result)
                headings=page.locator('#todos .todo-day-heading').all_text_contents()
                assert headings==['Today',day.isoformat(),(day-timedelta(days=1)).isoformat()],headings
                page.evaluate('window.Date=window.realDate')
                page.evaluate('result=>document.querySelector("#todos").applyConfirmedTasks(result)',result)
                expect(page.locator('#todos .todo-day-heading').nth(0)).to_have_text('Today')
                # When a focused event link is replaced, focus falls back to the edit button.
                edit_button=page.locator('[data-edit-schedule]')
                today.locator('[data-plan-source=calendar] a').first.focus()
                first_update=deepcopy(data);first_update['collected_at']=day.isoformat()+'T09:30:00-04:00'
                first_update['agenda']['events'][0]['title']='Earlier source update'
                first=publish(root,first_update,'refresh');complete_refresh(root,first['snapshot'])
                expect(today).to_contain_text('Earlier source update',timeout=12000)
                expect(edit_button).to_be_focused()
                assert edit_button.evaluate('node=>node.tabIndex')==0
                edit_button.click()
                expect(read).to_be_hidden();expect(editor).to_be_visible()
                fixed=editor.locator('.day-fixed-lane');lane=editor.locator('.day-plan-lane')
                fixed_box=fixed.bounding_box();lane_box=lane.bounding_box()
                assert abs(fixed_box['x']-lane_box['x'])<1 and abs(fixed_box['width']-lane_box['width'])<1
                expect(editor.locator('.day-fixed[data-calendar-key]')).to_be_visible()
                # Drag an unplaced block into the single calendar column.
                scroll=editor.locator('.day-scroll');scroll.evaluate('(node)=>node.scrollTop=120')
                source=editor.locator('[data-place=focus]');source.scroll_into_view_if_needed()
                scroll.scroll_into_view_if_needed()
                box=source.bounding_box();board=editor.locator('.day-board').bounding_box();viewport=scroll.bounding_box()
                target_y=board['y']+(690-510)/(1020-510)*board['height']
                assert viewport['y']<target_y<viewport['y']+viewport['height'], (target_y,viewport,board)
                page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2);page.mouse.down()
                page.mouse.move(box['x']+box['width']/2+10,box['y']+box['height']/2,steps=4)
                page.mouse.move(lane_box['x']+lane_box['width']*.5,target_y,steps=15);page.mouse.up()
                expect(editor.locator('#day-time-focus')).to_have_value('11:30')
                editor.locator('.day-cancel').click();expect(read).to_be_visible();expect(editor).to_be_hidden()
                page.locator('[data-edit-schedule]').click()
                expect(editor.locator('#day-time-focus')).to_have_value('')
                editor.locator('#day-time-focus').fill('11:30');editor.locator('#day-time-focus').press('Tab')
                # Keep an open save confirmation and its focus through a source refresh.
                editor.locator('.plan-submit-button').click()
                confirm=editor.get_by_role('button',name='Submit plan',exact=True)
                expect(confirm).to_be_visible();expect(confirm).to_be_focused()
                newer=deepcopy(data);newer['collected_at']=day.isoformat()+'T11:00:00-04:00'
                newer['agenda']['events'][0]['title']='Updated source event'
                fresh=publish(root,newer,'refresh');complete_refresh(root,fresh['snapshot'])
                expect(today).to_contain_text('Updated source event',timeout=12000)
                expect(editor).to_be_visible();expect(read).to_be_hidden()
                expect(editor.locator('#day-time-focus')).to_have_value('11:30')
                expect(confirm).to_be_visible();expect(confirm).to_be_focused()
                page.route('**/submit', lambda route:route.fulfill(status=503,json={'ok':False,'error':'Synthetic save failure'}))
                editor.get_by_role('button',name='Submit plan',exact=True).click()
                expect(editor.locator('.plan-submit-status')).to_contain_text('not confirmed')
                expect(editor).to_be_visible();expect(read).to_be_hidden()
                expect(editor.locator('#day-time-focus')).to_have_value('11:30')
                page.unroute('**/submit')
                editor.get_by_role('button',name='Submit plan',exact=True).click()
                expect(read).to_be_visible(timeout=12000);expect(editor).to_be_hidden()
                expect(today.locator('[data-plan-source=local]')).to_contain_text('Focus')
                assert latest_plan(root,day.isoformat(),zone)['blocks'][0]['start']==690
                # A committed save with a failed view refresh still reports success in the visible read view.
                page.locator('[data-edit-schedule]').click()
                editor.locator('#day-time-focus').fill('12:00');editor.locator('#day-time-focus').press('Tab')
                page.route('**/report/**',lambda route:route.fulfill(status=503,body='Synthetic view failure'))
                editor.locator('.plan-submit-button').click()
                editor.get_by_role('button',name='Submit plan',exact=True).click()
                expect(read).to_be_visible(timeout=12000)
                expect(today.locator('.day-read-status')).to_contain_text('Plan saved locally. Reload')
                expect(page.locator('[data-edit-schedule]')).to_be_focused()
                page.unroute('**/report/**')
                page.reload();expect(read).to_be_visible();expect(editor).to_be_hidden()
                expect(today.locator('[data-plan-source=local]')).to_contain_text('Focus')
                # Existing event actions remain clickable after the lanes overlap.
                page.locator('[data-edit-schedule]').click()
                fixed.locator('[data-calendar-toggle]').click()
                expect(fixed.locator('[data-calendar-toggle]')).to_have_text('Undo done')
                editor.locator('.day-cancel').click()
                today.screenshot(path='/tmp/coffee-loop3-calendar-read.png')
                page.locator('#todos').screenshot(path='/tmp/coffee-loop3-todos.png')
                page.locator('[data-edit-schedule]').click()
                today.screenshot(path='/tmp/coffee-loop3-calendar-edit.png')
                page.set_viewport_size({'width':390,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert page.locator('#reviews-waiting').bounding_box()['y'] < page.locator('#rfcs-to-review').bounding_box()['y']
                assert not errors,errors
                print('Combined read/edit, day headers, one-column drag, draft refresh, submit/reload, event actions and mobile passed.')
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    main()
