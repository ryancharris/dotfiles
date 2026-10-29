"""Opt-in choices and saved-plan agenda behavior; no calendar provider calls."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from day_calendar import calendar_data, render_calendar
from local_plan_server import session_snapshot
from plan_submission import save_plan
from render_brief import render, today_rows
from test_report_history import ReportSurface, snapshot as report_snapshot


def snapshot():
    data = report_snapshot()
    data['availability'] = {'status': 'complete', 'checked_at': data['collected_at'],
                            'coverage': 'Synthetic primary calendar', 'window_start': '09:00',
                            'window_end': '17:00', 'coverage_start': '2026-10-19T00:00:00-04:00',
                            'coverage_end': '2026-10-20T00:00:00-04:00', 'busy': []}
    return data


class OptInCalendarTests(unittest.TestCase):
    def test_new_plan_is_unplaced_and_explicit_24_hour_inputs(self):
        data = snapshot()
        original = deepcopy(data)
        self.assertTrue(all(row['start'] is None for row in calendar_data(data)['blocks']))
        self.assertFalse(any(row['_local_plan'] for row in today_rows(data)))
        markup = render_calendar(data)
        self.assertNotIn('type="time"', markup)
        self.assertEqual(markup.count('placeholder="HH:MM"'), 5)
        self.assertEqual(markup.count('placeholder="HH:MM" value=""'), 5)
        self.assertIn('data-focus-name type="text" maxlength="120" value="" placeholder="Focus"', markup)
        self.assertIn('class="day-cancel">Cancel editing</button>', markup)
        self.assertEqual(data, original)

    def test_successful_save_restores_only_chosen_blocks_and_today_on_reload(self):
        data = snapshot()
        request = {'date': data['report']['date'], 'timezone': data['report']['timezone'],
                   'blocks': [{'kind': 'exercise', 'start': 720, 'minutes': 60}]}
        with tempfile.TemporaryDirectory() as root:
            self.assertFalse(any(row['_local_plan'] for row in today_rows(session_snapshot(data, root))))
            saved = save_plan(root, data, request, datetime.fromisoformat('2026-10-19T09:05:00-04:00'))
            opened = session_snapshot(data, root)
            self.assertEqual(opened['submitted_plan']['blocks'], saved['blocks'])
            starts = {row['kind']: row['start'] for row in calendar_data(opened)['blocks']}
            self.assertEqual(starts, {'focus': None, 'exercise': 720, 'dog_walk': None, 'lunch': None, 'learning': None})
            original = deepcopy(opened)
            page = ReportSurface(render(opened))
            self.assertIn('hidden', page.by_id['focus-exercise']['attrs'])
            today = page.visible_text(page.by_id['today'])
            self.assertIn('12:00–13:00', today)
            self.assertNotIn('Local chosen plan', today)
            self.assertIn('Fixture stand-up', today)
            local_rows = [row for row in page.elements(page.by_id['today']) if row['attrs'].get('data-plan-source') == 'local']
            self.assertEqual(len(local_rows), 1)
            self.assertEqual(opened, original)
            opened['history'] = {'kind': 'tea-time'}
            tea = ReportSurface(render(opened))
            overview = tea.visible_text(tea.by_id['day-overview'])
            self.assertIn('1 event from calendar · 1 local plan block', overview)
            self.assertNotIn('Local chosen plan', overview)
            self.assertNotIn('Local chosen plan', tea.visible_text(tea.by_id['today']))
            request['blocks'] = []
            save_plan(root, data, request, datetime.fromisoformat('2026-10-19T09:10:00-04:00'))
            cleared = session_snapshot(data, root)
            self.assertFalse(any(row['_local_plan'] for row in today_rows(cleared)))
            self.assertTrue(all(row['start'] is None for row in calendar_data(cleared)['blocks']))
            self.assertIn('hidden', ReportSurface(render(cleared)).by_id['focus-exercise']['attrs'])

    def test_compact_calendar_bounds_do_not_discard_full_day_evidence_or_saved_choices(self):
        data = snapshot()
        data['agenda']['events'] = [
            {'title': 'Early appointment', 'start': '2026-10-19T07:00:00-04:00', 'end': '2026-10-19T08:00:00-04:00'},
            {'title': 'Crossing boundary', 'start': '2026-10-19T08:00:00-04:00', 'end': '2026-10-19T09:00:00-04:00'},
            {'title': 'Evening appointment', 'start': '2026-10-19T19:00:00-04:00', 'end': '2026-10-19T20:00:00-04:00'},
        ]
        model = calendar_data(data)
        self.assertEqual((model['view_start'], model['view_end']), (510, 1020))
        self.assertEqual((model['start'], model['end']), (0, 1440))
        self.assertEqual(len(model['fixed']), 3)
        page = ReportSurface(render_calendar(data))
        visible = page.visible_text()
        ticks = [page.visible_text(node).strip() for node in page.elements() if node['attrs'].get('class') == 'day-tick']
        self.assertEqual(ticks, ['08:30', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00'])
        self.assertNotIn('Early appointment', visible)
        self.assertNotIn('Evening appointment', visible)
        crossing = next(node for node in page.elements() if 'day-fixed' in node['attrs'].get('class', '').split())
        self.assertIn('top:0.0000%', crossing['attrs']['style'])
        self.assertIn('08:00–09:00', page.visible_text(crossing))
        data['submitted_plan'] = {'date': data['report']['date'], 'timezone': data['report']['timezone'],
                                  'submitted_at': '2026-10-19T09:05:00-04:00',
                                  'blocks': [{'kind': 'dog_walk', 'start': 1080, 'minutes': 30}]}
        self.assertEqual(next(block['start'] for block in calendar_data(data)['blocks'] if block['kind'] == 'dog_walk'), 1080)
        self.assertEqual(next(row['time'] for row in today_rows(data) if row['_local_plan']), '18:00–18:30')
        tea = calendar_data(data, read_only=True)
        self.assertEqual((tea['view_start'], tea['view_end']), (0, 1440))

    def test_wrong_day_or_invalid_saved_plan_does_not_create_today_rows(self):
        data = snapshot()
        data['submitted_plan'] = {'date': '2026-10-18', 'timezone': data['report']['timezone'],
                                  'submitted_at': '2026-10-19T09:05:00-04:00',
                                  'blocks': [{'kind': 'exercise', 'start': 720, 'minutes': 60}]}
        self.assertFalse(any(row['_local_plan'] for row in today_rows(data)))
        data['submitted_plan']['date'] = data['report']['date']
        data['submitted_plan']['blocks'][0]['minutes'] = 5
        self.assertFalse(any(row['_local_plan'] for row in today_rows(data)))

    @unittest.skipUnless(shutil.which('node'), 'Node required for frontend persistence test')
    def test_browser_today_updates_only_after_save_success_and_preserves_calendar_rows(self):
        script = r"""
const assert = require('assert');
const {mount} = require(process.argv[1]);
class Element {
  constructor(){this.children=[];this.listeners={};this.dataset={};this.textContent='';this.hidden=false;this.attributes={};}
  setAttribute(name,value){this.attributes[name]=value;}
  append(...items){items.forEach(item=>{item.parent=this;this.children.push(item);});}
  insertBefore(item,before){item.parent=this;const index=this.children.indexOf(before);if(index<0)this.children.push(item);else this.children.splice(index,0,item);}
  replaceChildren(){this.children=[];}
  remove(){this.parent.children.splice(this.parent.children.indexOf(this),1);}
  addEventListener(name,handler){this.listeners[name]=handler;}
  querySelectorAll(){return this.children.filter(row=>row.dataset.planSource==='local');}
  focus(){this.focused=true;}
}
const agenda=new Element(), actual=new Element();
actual.dataset={planSource:'calendar',start:'600'};actual.sourceURL='https://example.com/event';agenda.append(actual);
const empty=new Element(), overview=new Element(), count=new Element(), note=new Element();
overview.dataset={calendarEventCount:'1',agendaTimezone:'America/Toronto'};
overview.querySelector=s=>s==='.status-value'?count:note;
const today={querySelector:s=>s==='.agenda'?agenda:empty};
const edit=new Element(),heading=new Element(),cancelEditing=new Element();edit.hidden=true;
global.document={createElement:()=>new Element(),querySelector:s=>s==='#today'?today:s==='[data-calendar-event-count]'?overview:s==='[data-edit-schedule]'?edit:null};
const state={date:'2026-10-19',timezone:'America/Toronto',blocks:[{kind:'exercise',start:720,minutes:60}]};
const calendar=new Element();calendar.querySelector=s=>s==='#day-calendar-title'?heading:s==='.day-cancel'?cancelEditing:null;calendar.getDayPlan=()=>structuredClone(state);calendar.dayPlanner={setLocked(){},getState:()=>structuredClone(state),restoreState:baseline=>{state.blocks=structuredClone(baseline.blocks);calendar.listeners['day-plan-change']();return true;}};
const opener=new Element(), review=new Element(), status=new Element();
const config={textContent:JSON.stringify({endpoint:'http://127.0.0.1:123/submit',token:'private'})};
const root={querySelector:s=>({'.plan-submit-data':config,'.plan-submit-button':opener,'.plan-submit-review':review,'.plan-submit-status':status}[s]),closest:()=>calendar};
let pendingResponse,requests=0;
global.fetch=()=>{requests++;return new Promise(resolve=>{pendingResponse=resolve;});};
const local=()=>agenda.children.filter(row=>row.dataset.planSource==='local');
const confirm=()=>{opener.listeners.click();return review.children.find(row=>row.textContent==='Submit plan').listeners.click();};
(async()=>{
  mount(root);assert.equal(local().length,0);assert.equal(calendar.hidden,false);assert.equal(edit.hidden,true);
  opener.listeners.click();assert.equal(local().length,0,'review is only a preview');
  review.children.find(row=>row.textContent==='Cancel').listeners.click();assert.equal(local().length,0);
  let save=confirm();assert.equal(local().length,0,'request in flight is not saved');assert.equal(calendar.hidden,false);
  pendingResponse({ok:false,json:async()=>({ok:false,error:'disk full'})});await save;
  assert.equal(local().length,0);assert.match(status.textContent,/not confirmed saved/);assert.equal(calendar.hidden,false);assert.equal(edit.hidden,true);
  save=confirm();pendingResponse({ok:true,json:async()=>({ok:false,error:'not retained'})});await save;
  assert.equal(local().length,0,'HTTP success without saved acknowledgement must not add rows');
  save=confirm();pendingResponse({ok:true,json:async()=>({ok:true,message:'Saved',blocks:structuredClone(state.blocks)})});await save;
  assert.equal(local().length,1);assert.equal(local()[0].children[0].textContent,'12:00–13:00');
  assert.equal(calendar.hidden,true);assert.equal(edit.hidden,false);assert.equal(edit.attributes['aria-expanded'],'false');assert.equal(edit.focused,true);
  edit.listeners.click();assert.equal(calendar.hidden,false);assert.equal(edit.hidden,true);assert.equal(edit.attributes['aria-expanded'],'true');assert.equal(heading.focused,true);
  assert.equal(count.textContent,'2');assert.match(note.textContent,/1 event from calendar · 1 local plan block/);
  state.blocks[0].start=780;calendar.listeners['day-plan-change']();
  opener.listeners.click();const beforeCancel=requests;
  cancelEditing.listeners.click();
  assert.equal(requests,beforeCancel,'Cancel editing writes no local state');assert.equal(state.blocks[0].start,720);
  assert.equal(calendar.hidden,true);assert.equal(edit.hidden,false);assert.equal(edit.focused,true);
  assert.equal(review.hidden,true);assert.equal(review.children.length,0);assert.equal(status.textContent,'');
  edit.listeners.click();assert.equal(state.blocks[0].start,720,'reopening restores the last successful schedule');
  state.blocks[0].start=780;calendar.listeners['day-plan-change']();
  assert.equal(local()[0].children[0].textContent,'12:00–13:00','unsaved edits keep saved Today rows');
  save=confirm();assert.equal(cancelEditing.disabled,true);
  cancelEditing.listeners.click();assert.equal(calendar.hidden,false);assert.equal(state.blocks[0].start,780,'pending POST cannot be cancelled');
  pendingResponse({ok:false,json:async()=>({ok:false,error:'offline'})});await save;
  assert.equal(cancelEditing.disabled,false);
  assert.equal(local()[0].children[0].textContent,'12:00–13:00','failed resubmit keeps previous saved rows');
  const afterFailure=requests;cancelEditing.listeners.click();assert.equal(requests,afterFailure);
  assert.equal(state.blocks[0].start,720,'failed save does not replace cancellation baseline');assert.equal(status.textContent,'');
  edit.listeners.click();state.blocks[0].start=780;calendar.listeners['day-plan-change']();
  save=confirm();pendingResponse({ok:true,json:async()=>({ok:true,message:'Saved',blocks:structuredClone(state.blocks)})});await save;
  assert.equal(local().length,1);assert.equal(local()[0].children[0].textContent,'13:00–14:00');
  edit.listeners.click();state.blocks=[];save=confirm();pendingResponse({ok:true,json:async()=>({ok:true,message:'Saved',blocks:[]})});await save;
  assert.equal(local().length,0);assert.equal(count.textContent,'1');assert.equal(empty.hidden,true);assert.equal(calendar.hidden,true);assert.equal(edit.hidden,false);
  edit.listeners.click();state.blocks=[{kind:'exercise',start:840,minutes:60}];calendar.listeners['day-plan-change']();
  cancelEditing.listeners.click();assert.deepEqual(state.blocks,[],'cancel restores a successfully submitted empty plan');assert.equal(local().length,0);
  assert.strictEqual(agenda.children[0],actual);assert.equal(actual.sourceURL,'https://example.com/event');
  const restored=new Element();restored.hidden=true;restored.querySelector=s=>s==='#day-calendar-title'?heading:null;
  mount({closest:()=>restored,querySelector:()=>null});
  assert.equal(restored.hidden,true);assert.equal(edit.hidden,false,'restored schedule exposes Edit even without active save config');
  edit.listeners.click();assert.equal(restored.hidden,false);assert.equal(edit.hidden,true);

})().catch(error=>{console.error(error);process.exit(1);});
"""
        result = subprocess.run([shutil.which('node'), '-e', script, str(SKILL / 'assets/local-plan-submission.js')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
