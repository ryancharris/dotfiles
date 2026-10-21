"""Live end-time styling for actual and saved calendar items."""
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from day_calendar import calendar_data, render_calendar


def snapshot():
    stamp = '2026-10-19T08:00:00-04:00'
    return {
        'report': {'date': '2026-10-19', 'timezone': 'America/Toronto'},
        'collected_at': stamp,
        'availability': {'status': 'complete', 'checked_at': stamp, 'coverage': 'Primary calendar only',
                         'window_start': '00:00', 'window_end': '23:59', 'busy': []},
        'agenda': {'events': []},
    }


class CalendarPastMarkupTests(unittest.TestCase):
    def test_fixed_event_uses_absolute_end_including_all_day_exclusive_end(self):
        data = snapshot()
        data['agenda']['events'] = [
            {'start': '2026-10-19T09:00:00-04:00', 'end': '2026-10-19T13:30:00Z', 'title': 'Planning'},
            {'start': '2026-10-19', 'end': '2026-10-20', 'title': 'All day'},
        ]
        model = calendar_data(data, read_only=True)
        self.assertEqual(model['fixed'][0]['end_at'], '2026-10-20T00:00:00-04:00')
        self.assertEqual(model['fixed'][1]['end_at'], '2026-10-19T09:30:00-04:00')
        rendered = render_calendar(data, read_only=True)
        self.assertIn('data-calendar-end="2026-10-19T09:30:00-04:00"', rendered)
        self.assertIn('data-calendar-end="2026-10-20T00:00:00-04:00"', rendered)

    def test_invalid_events_are_skipped_and_submitted_blocks_have_local_end(self):
        data = snapshot()
        data['agenda']['events'] = [
            {'start': '2026-10-19T09:00:00-04:00', 'end': 'bad', 'title': 'Broken'},
        ]
        # The invalid event is excluded by interval validation.
        data['submitted_plan'] = {'date': '2026-10-19', 'timezone': 'America/Toronto',
                                  'submitted_at': '2026-10-19T08:30:00-04:00',
                                  'blocks': [{'kind': 'lunch', 'start': 720, 'minutes': 30}]}
        model = calendar_data(data, read_only=True)
        self.assertEqual(model['fixed'], [])
        self.assertEqual(model['submitted_blocks'][0]['end_at'], '2026-10-19T12:30:00-04:00')
        markup = render_calendar(data, read_only=True)
        self.assertIn('data-local-plan-end="2026-10-19T12:30:00-04:00"', markup)
        self.assertNotIn('data-calendar-end="bad"', markup)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the live clock helper test')
    def test_browser_helper_boundaries_offsets_refresh_and_action_preservation(self):
        script = SKILL / 'assets' / 'calendar-past.js'
        program = r"""
const assert=require('assert');
const api=require(process.argv[1]);
function item(attrs){
  const values=attrs;
  const classes=new Set(['unrelated']);
  return {getAttribute:key=>Object.prototype.hasOwnProperty.call(values,key)?values[key]:null,
    classList:{toggle:(name,on)=>on?classes.add(name):classes.delete(name),contains:name=>classes.has(name)},
    classes};
}
const before=item({'data-calendar-end':'2026-10-19T13:30:00Z'});
const exact=item({'data-local-plan-end':'2026-10-19T09:30:00-04:00'});
const after=item({'data-calendar-end':'2026-10-19T09:30:01-04:00'});
const invalid=item({'data-calendar-end':'2026-10-19T09:30:00'});
const action=item({'data-calendar-end':'2026-10-19T09:00:00-04:00'});
const elements=[before,exact,after,invalid,action];
const root={querySelectorAll:()=>elements};
const now=Date.parse('2026-10-19T13:30:00Z');
assert.strictEqual(api.updateCalendarPast(root,now),5);
assert.strictEqual(before.classList.contains('calendar-past'),true);
assert.strictEqual(exact.classList.contains('calendar-past'),true);
assert.strictEqual(after.classList.contains('calendar-past'),false);
assert.strictEqual(invalid.classList.contains('calendar-past'),false);
assert.strictEqual(action.classList.contains('unrelated'),true);
const early=item({'data-calendar-end':'2026-10-19T20:00:00Z','data-calendar-done':'true'});
const reopened=item({'data-calendar-end':'2026-10-19T09:00:00Z','data-calendar-done':'false'});
const noEnd=item({'data-calendar-done':'true'});
api.updateCalendarPast({querySelectorAll:()=>[early,reopened,noEnd]},now);
assert.strictEqual(early.classList.contains('calendar-past'),false);
assert.strictEqual(early.classList.contains('calendar-done'),true);
assert.strictEqual(reopened.classList.contains('calendar-past'),true);
assert.strictEqual(reopened.classList.contains('calendar-done'),false);
assert.strictEqual(noEnd.classList.contains('calendar-done'),true);

api.updateCalendarPast(root,now+60000);
assert.strictEqual(after.classList.contains('calendar-past'),true);
// A newly patched row can be refreshed without reconstructing the widget.
const refreshed=item({'data-calendar-end':'2026-10-19T15:00:00Z'});
root.querySelectorAll=()=>[refreshed];
api.updateCalendarPast(root,now+60000);
assert.strictEqual(refreshed.classList.contains('calendar-past'),false);
// Mount performs an immediate update, schedules a minute tick, and responds
// to tab visibility changes; repeated mounts do not install duplicate timers.
const listeners={};let intervalCalls=0;
const doc={querySelectorAll:()=>[before],addEventListener:(name,fn)=>{listeners[name]=fn;}};
api.mountCalendarPast(doc,{document:doc,setInterval:(fn,ms)=>{intervalCalls++;assert.strictEqual(ms,60000);return 1;}});
api.mountCalendarPast(doc,{document:doc,setInterval:()=>{intervalCalls++;}});
assert.strictEqual(intervalCalls,1);
assert.strictEqual(typeof listeners.visibilitychange,'function');
assert.strictEqual(before.classList.contains('calendar-past'),Date.parse('2026-10-19T13:30:00Z')<=Date.now());
"""
        result = subprocess.run(['node', '-e', program, str(script)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
