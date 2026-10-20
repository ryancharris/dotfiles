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
        self.assertEqual(markup.count('placeholder="HH:MM"'), 4)
        self.assertEqual(markup.count('value=""'), 4)
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
            self.assertEqual(starts, {'focus': None, 'exercise': 720, 'dog_walk': None, 'lunch': None})
            original = deepcopy(opened)
            page = ReportSurface(render(opened))
            today = page.visible_text(page.by_id['today'])
            self.assertIn('12:00–13:00', today)
            self.assertIn('Local chosen plan', today)
            self.assertIn('Fixture stand-up', today)
            local_rows = [row for row in page.elements(page.by_id['today']) if row['attrs'].get('data-plan-source') == 'local']
            self.assertEqual(len(local_rows), 1)
            self.assertEqual(opened, original)
            opened['history'] = {'kind': 'tea-time'}
            tea = ReportSurface(render(opened))
            overview = tea.visible_text(tea.by_id['day-overview'])
            self.assertIn('1 event from calendar · 1 local plan block', overview)
            self.assertIn('Local chosen plan', overview)
            self.assertIn('Local chosen plan', tea.visible_text(tea.by_id['today']))
            request['blocks'] = []
            save_plan(root, data, request, datetime.fromisoformat('2026-10-19T09:10:00-04:00'))
            cleared = session_snapshot(data, root)
            self.assertFalse(any(row['_local_plan'] for row in today_rows(cleared)))
            self.assertTrue(all(row['start'] is None for row in calendar_data(cleared)['blocks']))

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
  constructor(){this.children=[];this.listeners={};this.dataset={};this.textContent='';}
  append(...items){items.forEach(item=>{item.parent=this;this.children.push(item);});}
  insertBefore(item,before){item.parent=this;const index=this.children.indexOf(before);if(index<0)this.children.push(item);else this.children.splice(index,0,item);}
  replaceChildren(){this.children=[];}
  remove(){this.parent.children.splice(this.parent.children.indexOf(this),1);}
  addEventListener(name,handler){this.listeners[name]=handler;}
  querySelectorAll(){return this.children.filter(row=>row.dataset.planSource==='local');}
  focus(){}
}
const agenda=new Element(), actual=new Element();
actual.dataset={planSource:'calendar',start:'600'};actual.sourceURL='https://example.com/event';agenda.append(actual);
const empty=new Element(), overview=new Element(), count=new Element(), note=new Element();
overview.dataset={calendarEventCount:'1',agendaTimezone:'America/Toronto'};
overview.querySelector=s=>s==='.status-value'?count:note;
const today={querySelector:s=>s==='.agenda'?agenda:empty};
global.document={createElement:()=>new Element(),querySelector:s=>s==='#today'?today:overview};
const state={date:'2026-10-19',timezone:'America/Toronto',blocks:[{kind:'exercise',start:720,minutes:60}]};
const calendar=new Element();calendar.getDayPlan=()=>structuredClone(state);calendar.dayPlanner={setLocked(){}};
const opener=new Element(), review=new Element(), status=new Element();
const config={textContent:JSON.stringify({endpoint:'http://127.0.0.1:123/submit',token:'private'})};
const root={querySelector:s=>({'.plan-submit-data':config,'.plan-submit-button':opener,'.plan-submit-review':review,'.plan-submit-status':status}[s]),closest:()=>calendar};
let pendingResponse;
global.fetch=()=>new Promise(resolve=>{pendingResponse=resolve;});
const local=()=>agenda.children.filter(row=>row.dataset.planSource==='local');
const confirm=()=>{opener.listeners.click();return review.children.find(row=>row.textContent==='Submit plan').listeners.click();};
(async()=>{
  mount(root);assert.equal(local().length,0);
  opener.listeners.click();assert.equal(local().length,0,'review is only a preview');
  review.children.find(row=>row.textContent==='Cancel').listeners.click();assert.equal(local().length,0);
  let save=confirm();assert.equal(local().length,0,'request in flight is not saved');
  pendingResponse({ok:false,json:async()=>({ok:false,error:'disk full'})});await save;
  assert.equal(local().length,0);assert.match(status.textContent,/not confirmed saved/);
  save=confirm();pendingResponse({ok:true,json:async()=>({ok:false,error:'not retained'})});await save;
  assert.equal(local().length,0,'HTTP success without saved acknowledgement must not add rows');
  save=confirm();pendingResponse({ok:true,json:async()=>({ok:true,message:'Saved',blocks:structuredClone(state.blocks)})});await save;
  assert.equal(local().length,1);assert.equal(local()[0].children[0].textContent,'12:00–13:00');
  assert.equal(count.textContent,'2');assert.match(note.textContent,/1 event from calendar · 1 local plan block/);
  state.blocks[0].start=780;calendar.listeners['day-plan-change']();
  assert.equal(local()[0].children[0].textContent,'12:00–13:00','unsaved edits keep saved Today rows');
  save=confirm();pendingResponse({ok:false,json:async()=>({ok:false,error:'offline'})});await save;
  assert.equal(local()[0].children[0].textContent,'12:00–13:00','failed resubmit keeps previous saved rows');
  save=confirm();pendingResponse({ok:true,json:async()=>({ok:true,message:'Saved',blocks:structuredClone(state.blocks)})});await save;
  assert.equal(local().length,1);assert.equal(local()[0].children[0].textContent,'13:00–14:00');
  state.blocks=[];save=confirm();pendingResponse({ok:true,json:async()=>({ok:true,message:'Saved',blocks:[]})});await save;
  assert.equal(local().length,0);assert.equal(count.textContent,'1');assert.equal(empty.hidden,true);
  assert.strictEqual(agenda.children[0],actual);assert.equal(actual.sourceURL,'https://example.com/event');
})().catch(error=>{console.error(error);process.exit(1);});
"""
        result = subprocess.run([shutil.which('node'), '-e', script, str(SKILL / 'assets/local-plan-submission.js')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
