"""Scheduling/privacy contracts and local planner interaction tests."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from day_calendar import calendar_data, render_calendar
from plan_day import suggest


def snapshot(at='09:00', busy=None, status='complete'):
    stamp = '2026-10-19T' + at + ':00-04:00'
    return {'report': {'date': '2026-10-19', 'timezone': 'America/Toronto'}, 'collected_at': stamp,
            'availability': {'status': status, 'checked_at': stamp, 'coverage': 'Primary calendar only',
                             'window_start': '09:00', 'window_end': '17:00', 'busy': busy or []},
            'agenda': {'events': []}}


def busy(start, end):
    return {'start': '2026-10-19T' + start + ':00-04:00', 'end': '2026-10-19T' + end + ':00-04:00'}


class PlannerTests(unittest.TestCase):
    def test_four_goals_and_preferences(self):
        plan = suggest(snapshot())
        self.assertEqual(plan['status'], 'suggested')
        slots = {row['kind']: row for row in plan['suggestions']}
        self.assertEqual({key: row['minutes'] for key, row in slots.items()}, {'focus': 120, 'exercise': 60, 'dog_walk': 30, 'lunch': 30})
        self.assertIn('T09:00:', slots['focus']['start'])
        self.assertIn('T12:00:', slots['exercise']['start'])
        self.assertIn('T11:00:', slots['dog_walk']['start'])
        self.assertIn('T11:30:', slots['lunch']['start'])

    def test_global_search_preserves_all_four(self):
        data = snapshot(busy=[busy('11:00', '12:00'), busy('13:00', '14:00'), busy('15:00', '17:00')])
        plan = suggest(data)
        self.assertEqual(plan['status'], 'suggested')
        self.assertEqual([row['start'][11:16] for row in plan['suggestions']], ['09:00', '12:00', '14:00', '14:30'])

    def test_feasible_subsets_and_remaining_day(self):
        plan = suggest(snapshot('15:30'))
        self.assertEqual({row['kind'] for row in plan['suggestions']}, {'exercise', 'lunch'})
        self.assertEqual(plan['unscheduled'], ['focus', 'dog_walk'])
        plan = suggest(snapshot('14:30'))
        self.assertEqual({row['kind'] for row in plan['suggestions']}, {'focus', 'lunch'})
        self.assertEqual(plan['unscheduled'], ['exercise', 'dog_walk'])
        plan = suggest(snapshot('16:15'))
        self.assertEqual([row['kind'] for row in plan['suggestions']], ['lunch'])

    def test_lunch_and_walk_do_not_displace_required_focus_or_exercise(self):
        data = snapshot(busy=[busy('11:00', '12:00'), busy('13:00', '17:00')])
        plan = suggest(data)
        self.assertEqual({row['kind'] for row in plan['suggestions']}, {'focus', 'exercise'})
        self.assertEqual(plan['unscheduled'], ['dog_walk', 'lunch'])

    def test_anytime_walk_uses_only_explicit_full_day_coverage(self):
        data = snapshot('18:00', busy=[busy('18:00', '19:00')])
        self.assertEqual(suggest(data)['suggestions'], [])
        data['availability'].update(coverage_start='2026-10-19T00:00:00-04:00', coverage_end='2026-10-20T00:00:00-04:00')
        plan = suggest(data)
        self.assertEqual([(row['kind'], row['start'][11:16]) for row in plan['suggestions']], [('dog_walk', '19:00')])
        data = snapshot('06:00')
        data['availability'].update(coverage_start='2026-10-19T00:00:00-04:00', coverage_end='2026-10-20T00:00:00-04:00')
        self.assertEqual(next(row['start'][11:16] for row in suggest(data)['suggestions'] if row['kind'] == 'dog_walk'), '06:00')

    def test_later_verification_and_quarter_hour_snap(self):
        data = snapshot('09:00')
        data['availability']['checked_at'] = '2026-10-19T14:00:01-04:00'
        plan = suggest(data)
        self.assertTrue(all(row['start'] >= '2026-10-19T14:15:' for row in plan['suggestions']))
        self.assertTrue(all(datetime.fromisoformat(row['start']).minute % 15 == 0 for row in plan['suggestions']))

    def test_exact_busy_bounds_and_timezone_conversion(self):
        data = snapshot(busy=[{'start': '2026-10-19T13:00:00Z', 'end': '2026-10-19T14:07:00Z'}])
        plan = suggest(data)
        self.assertTrue(all(row['start'] >= '2026-10-19T10:15:' for row in plan['suggestions']))
        self.assertEqual(plan['status'], 'suggested')

    def test_all_day_exclusive_end(self):
        self.assertEqual(suggest(snapshot(busy=[{'start': '2026-10-19', 'end': '2026-10-20'}]))['suggestions'], [])
        self.assertEqual(suggest(snapshot(busy=[{'start': '2026-10-18', 'end': '2026-10-19'}]))['status'], 'suggested')

    def test_partial_and_invalid_never_invent_slots(self):
        self.assertEqual(suggest(snapshot(status='partial'))['suggestions'], [])
        data = snapshot()
        data['availability']['busy'] = [{'start': 'bad', 'end': 'bad'}]
        self.assertEqual(suggest(data)['status'], 'unverified')
        self.assertEqual(calendar_data(snapshot(status='partial'))['blocks'][0]['start'], None)

    def test_source_snapshot_unchanged(self):
        data = snapshot(busy=[busy('10:00', '11:00')])
        original = deepcopy(data)
        render_calendar(data)
        self.assertEqual(data, original)


class CalendarTests(unittest.TestCase):
    def test_anonymous_busy_and_hidden_titles(self):
        data = snapshot(busy=[busy('09:00', '09:30'), busy('10:00', '10:30')])
        data['agenda']['events'] = [dict(busy('09:00', '09:30'), title='  🏡 FAMILY TIME '),
                                    dict(busy('10:00', '10:30'), title='Stand-up')]
        model = calendar_data(data)
        self.assertEqual([row['label'] for row in model['fixed']], ['Busy', 'Stand-up'])
        self.assertNotIn('FAMILY TIME', render_calendar(data))
        self.assertTrue(all(row['start'] >= 570 for row in model['blocks'] if row['start'] is not None))

    def test_read_only_has_actual_events_and_no_planner_controls(self):
        data = snapshot()
        data['agenda']['events'] = [dict(busy('19:00', '20:00'), title='Evening event')]
        model = calendar_data(data, read_only=True)
        self.assertEqual(model['blocks'], [])
        self.assertEqual(model['fixed'][0]['start'], 1140)
        rendered = render_calendar(data, read_only=True)
        self.assertIn('Evening event', rendered)
        self.assertIn('read only', rendered)
        for marker in ('<button', '<input', 'day-plan-lane', 'coffee-confirmation', 'day-calendar-data', 'Shape your day'):
            self.assertNotIn(marker, rendered)

    def test_read_only_retains_submitted_past_choices_and_flags_new_conflicts(self):
        data = snapshot('15:00')
        data['agenda']['events'] = [dict(busy('09:30', '10:30'), title='New meeting')]
        data['submitted_plan'] = {'date': '2026-10-19', 'timezone': 'America/Toronto',
                                  'submitted_at': '2026-10-19T08:50:00-04:00', 'blocks': [
                                      {'kind': 'focus', 'start': 540, 'minutes': 120},
                                      {'kind': 'dog_walk', 'start': 1260, 'minutes': 30}]}
        original = deepcopy(data)
        model = calendar_data(data, read_only=True)
        self.assertEqual([(row['kind'], row['start'], row['conflict']) for row in model['submitted_blocks']],
                         [('focus', 540, True), ('dog_walk', 1260, False)])
        rendered = render_calendar(data, read_only=True)
        self.assertIn('Your submitted plan', rendered)
        self.assertIn('Submitted 08:50 EDT', rendered)
        self.assertIn('09:00–11:00', rendered)
        self.assertIn('21:00–21:30', rendered)
        self.assertIn('Overlaps current calendar: 🔎 Focus.', rendered)
        for marker in ('<button', '<input', 'day-calendar-data', 'coffee-confirmation'):
            self.assertNotIn(marker, rendered)
        self.assertEqual(data, original)

    def test_no_submitted_plan_and_wrong_day_are_explicit(self):
        self.assertIn('No plan submitted yet.', render_calendar(snapshot(), read_only=True))
        data = snapshot()
        data['submitted_plan'] = {'date': '2026-10-18', 'timezone': 'America/Toronto',
                                  'submitted_at': '2026-10-18T08:50:00-04:00',
                                  'blocks': [{'kind': 'focus', 'start': 540, 'minutes': 120}]}
        model = calendar_data(data, read_only=True)
        self.assertEqual(model['submitted_blocks'], [])
        self.assertIn('Saved plan unavailable', render_calendar(data, read_only=True))
        self.assertNotIn('Your submitted plan', render_calendar(data, read_only=True))

    def test_coffee_prefills_saved_choices_and_unplaces_new_conflicts(self):
        data = snapshot('15:00')
        data['agenda']['events'] = [dict(busy('09:30', '10:30'), title='New meeting')]
        data['submitted_plan'] = {'date': '2026-10-19', 'timezone': 'America/Toronto',
                                  'submitted_at': '2026-10-19T08:50:00-04:00', 'blocks': [
                                      {'kind': 'focus', 'start': 540, 'minutes': 120},
                                      {'kind': 'lunch', 'start': 720, 'minutes': 30}]}
        model = calendar_data(data)
        blocks = {row['kind']: row for row in model['blocks']}
        self.assertEqual(blocks['lunch']['start'], 720)  # Past choices remain visible.
        self.assertIsNone(blocks['focus']['start'])
        self.assertIsNone(blocks['exercise']['start'])  # Omitted choices stay omitted.
        self.assertIsNone(blocks['dog_walk']['start'])
        self.assertIn('Needs a new time: 🔎 Focus.', model['note'])
        rendered = render_calendar(data)
        self.assertIn('submit below to save', rendered)
        self.assertNotIn('confirm below to book', rendered)

    def test_calendar_domains_and_hidden_detailed_events(self):
        data = snapshot()
        data['availability'].update(coverage_start='2026-10-19T00:00:00-04:00', coverage_end='2026-10-20T00:00:00-04:00')
        data['agenda']['events'] = [dict(busy('21:00', '21:30'), title='Family time')]
        model = calendar_data(data)
        self.assertEqual((model['start'], model['end']), (0, 1440))
        self.assertEqual(model['fixed'][0]['label'], 'Busy')
        blocks = {row['kind']: row for row in model['blocks']}
        self.assertEqual((blocks['dog_walk']['min_start'], blocks['dog_walk']['max_end']), (0, 1440))
        self.assertEqual((blocks['lunch']['min_start'], blocks['lunch']['max_end']), (540, 1020))

    def test_unstructured_display_time_is_not_scheduling_evidence(self):
        data = snapshot()
        data['agenda']['events'] = [{'time': '10:00–11:00', 'title': 'Not hydrated'}]
        self.assertEqual(calendar_data(data)['fixed'], [])

    def test_free_events_also_block_suggestions_without_duplicate_busy(self):
        data = snapshot(busy=[busy('10:00', '11:00')])
        data['agenda']['events'] = [dict(busy('10:00', '11:00'), title='Optional', free=True)]
        fixed = calendar_data(data)['fixed']
        self.assertEqual(len(fixed), 1)
        self.assertTrue(all(not (row['start'] < '2026-10-19T11:00:00-04:00' and row['end'] > '2026-10-19T10:00:00-04:00') for row in suggest(data)['suggestions']))

    def test_escaping_and_accessible_controls(self):
        data = snapshot()
        data['agenda']['events'] = [dict(busy('10:00', '11:00'), title='</script><img src=x onerror=bad()>')]
        rendered = render_calendar(data)
        self.assertNotIn('<img src=x', rendered)
        self.assertEqual(rendered.count('</script>'), 1)
        self.assertIn('\\u003c/script', rendered)
        self.assertIn('placeholder="HH:MM"', rendered)
        self.assertIn('type="text"', rendered)
        self.assertNotIn('type="time"', rendered)
        self.assertIn('aria-live="polite"', rendered)
        self.assertIn('day-time-dog_walk', rendered)

    def test_fixed_overlap_uses_columns(self):
        data = snapshot()
        data['agenda']['events'] = [dict(busy('10:00', '11:00'), title='A'), dict(busy('10:30', '11:30'), title='B')]
        rendered = render_calendar(data)
        self.assertIn('left:50.0%;width:50.0%', rendered)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for local interaction checks')
    def test_javascript_handlers_and_constraints(self):
        script = r'''
const assert=require('node:assert/strict');
const api=require(process.argv[1]);
const data={start:540,end:1020,now:540,verified:true,fixed:[{start:660,end:690,free:false}],blocks:[
  {kind:'focus',label:'Focus',minutes:120,start:540},{kind:'exercise',label:'Exercise',minutes:60,start:720},{kind:'dog_walk',label:'Dog walk',minutes:30,start:900}]};
class Element {
  constructor(){this.listeners={};this.style={};this.hidden=false;this.dataset={};this.value='';this.textContent='';this.attributes={};this.classes=new Set();this.classList={toggle:(k,v)=>v?this.classes.add(k):this.classes.delete(k),add:k=>this.classes.add(k),remove:k=>this.classes.delete(k)};}
  addEventListener(type,fn){const before=this.listeners[type];this.listeners[type]=before?event=>{before(event);fn(event);}:fn;}
  setAttribute(k,v){this.attributes[k]=v;}
  setPointerCapture(){}
  fire(type,props={}){this.listeners[type]({...props,type,target:this,preventDefault(){}});}
}
const buttons={},controls={};
data.blocks.forEach(block=>{
  const button=new Element();button.span=new Element();button.dataset.kind=block.kind;button.querySelector=()=>button.span;buttons[block.kind]=button;
  const control=new Element();control.dataset.kind=block.kind;control.input=new Element();control.place=new Element();control.remove=new Element();
  control.querySelector=q=>q==='input'?control.input:q==='[data-place]'?control.place:control.remove;controls[block.kind]=control;
});
const warning=new Element(),reset=new Element(),board=new Element(),lane=new Element();
board.getBoundingClientRect=()=>({height:480});lane.querySelector=q=>buttons[q.match(/data-kind="(.*?)"/)[1]];lane.querySelectorAll=()=>Object.values(buttons);
const root={querySelector:q=>({'.day-calendar-data':{textContent:JSON.stringify(data)},'.day-board':board,'.day-plan-lane':lane,'.day-warning':warning,'.day-reset':reset}[q]||(q==='.day-scroll'?null:controls[q.match(/data-kind="(.*?)"/)[1]])),querySelectorAll:()=>Object.values(controls)};
api.mount(root);
assert.equal(root.getDayPlan().blocks[0].start,540);
const exposed=root.getDayPlan();exposed.blocks[0].start=0;assert.equal(root.getDayPlan().blocks[0].start,540);
assert.equal(controls.focus.input.value,'09:00');
buttons.focus.fire('keydown',{key:'ArrowDown'});
assert.equal(controls.focus.input.value,'09:00');assert.match(warning.textContent,/overlaps/);
controls.exercise.input.value='09:00';controls.exercise.input.fire('change');
assert.match(warning.textContent,/overlaps/);assert.equal(controls.exercise.input.value,'12:00');
controls.dog_walk.remove.fire('click');assert.equal(buttons.dog_walk.hidden,true);assert.match(warning.textContent,/Unplaced/);
controls.dog_walk.place.fire('click');assert.equal(controls.dog_walk.input.value,'11:30');assert.equal(buttons.dog_walk.hidden,false);
controls.dog_walk.input.value='14:99';controls.dog_walk.input.fire('change');
assert.equal(controls.dog_walk.input.value,'11:30');assert.match(warning.textContent,/24-hour/);
controls.exercise.input.value='18:00';controls.exercise.input.fire('change');
assert.equal(controls.exercise.input.value,'16:00');assert.match(warning.textContent,/Moved to 16:00.*window 09:00–17:00/);
root.dayPlanner.setLocked(true);
const lockedPlan=root.getDayPlan();
for(const control of Object.values(controls))for(const item of [control.input,control.place,control.remove])assert.equal(item.disabled,true);
assert.equal(reset.disabled,true);assert.equal(buttons.focus.disabled,true);
controls.exercise.input.value='';controls.exercise.input.fire('change');
assert.equal(controls.exercise.input.value,'16:00');
controls.dog_walk.remove.fire('click');controls.dog_walk.place.fire('click');
buttons.dog_walk.fire('keydown',{key:'ArrowDown'});reset.fire('click');
assert.deepEqual(root.getDayPlan(),lockedPlan);
root.dayPlanner.setLocked(false);
assert.equal(reset.disabled,false);assert.equal(controls.exercise.input.disabled,false);
buttons.dog_walk.fire('keydown',{key:'ArrowDown'});
assert.equal(controls.dog_walk.input.value,'11:45');
reset.fire('click');
assert.ok(root.getDayPlan().blocks.every(block=>block.start===null));
assert.equal(controls.focus.input.value,'');assert.equal(controls.exercise.input.value,'');
controls.focus.place.fire('click');assert.equal(controls.focus.input.value,'09:00');
controls.exercise.place.fire('click');assert.equal(controls.exercise.input.value,'11:30');
reset.fire('click');
assert.equal(api.placement(2000,120,data),900);assert.equal(api.placement(0,120,data),540);
assert.equal(api.placement(600,600,data),null);assert.equal(api.placement(NaN,30,data),null);
assert.deepEqual(api.warnings({...data,verified:false},[{kind:'dog_walk',label:'Dog walk',minutes:30,start:null}]),['Availability unverified','Unplaced: Dog walk']);
const overlap=api.lanes([{start:540,end:600},{start:570,end:630},{start:660,end:690}]);
assert.deepEqual(overlap.map(r=>r.columns),[2,2,1]);
assert.equal(api.canPlace(1260,{...data.blocks[2],min_start:0,max_end:1440},{...data,start:0,end:1440},data.blocks),true);
assert.equal(api.canPlace(1260,{...data.blocks[1],min_start:540,max_end:1020},{...data,start:0,end:1440},data.blocks),false);
assert.equal(api.canPlace(660,data.blocks[2],data,data.blocks),false);
assert.equal(api.canPlace(690,data.blocks[2],data,data.blocks),true);
assert.equal(api.canPlace(720,data.blocks[2],data,data.blocks),false);
assert.equal(api.canPlace(840,data.blocks[2],{...data,fixed:[{start:840,end:870,free:true}]},data.blocks),false);
assert.equal(api.firstFree(data.blocks[2],{...data,fixed:[{start:540,end:1020}]},data.blocks),null);
assert.equal(data.blocks[0].start,540); // Rendered interactions never change source input.
console.log('Keyboard, HH:MM input, reset, locking and helper constraints passed.');
'''
        result = subprocess.run(['node', '-e', script, str(SKILL / 'assets/day-calendar.js')], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
