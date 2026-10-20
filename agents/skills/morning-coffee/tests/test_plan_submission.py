"""Local plan records and registered frontend/HTTP submission workflows. No provider calls."""
from copy import deepcopy
from datetime import datetime
import http.client
from http.server import HTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from plan_submission import PlanError, latest_plan, render_submission, save_plan
from local_plan_server import handler_for, session_snapshot


def snapshot():
    return {'report': {'date': '2026-10-19', 'timezone': 'America/Toronto'}, 'collected_at': '2026-10-19T08:00:00-04:00',
            'availability': {'status': 'complete', 'checked_at': '2026-10-19T08:00:00-04:00', 'coverage': 'Primary calendar only',
                             'window_start': '09:00', 'window_end': '17:00', 'coverage_start': '2026-10-19T00:00:00-04:00',
                             'coverage_end': '2026-10-20T00:00:00-04:00', 'busy': []}, 'agenda': {'events': []}}


def selected(*blocks):
    return {'date': '2026-10-19', 'timezone': 'America/Toronto', 'blocks': list(blocks) or
            [{'kind': 'focus', 'start': 540, 'minutes': 120}, {'kind': 'exercise', 'start': 720, 'minutes': 60},
             {'kind': 'lunch', 'start': 780, 'minutes': 30}, {'kind': 'dog_walk', 'start': 1200, 'minutes': 30}]}


class LocalPlanTests(unittest.TestCase):
    def test_private_immutable_versions_and_latest_day_scope(self):
        with tempfile.TemporaryDirectory() as root:
            first = save_plan(root, snapshot(), selected(), datetime.fromisoformat('2026-10-19T09:00:00-04:00'))
            second = save_plan(root, snapshot(), selected({'kind': 'dog_walk', 'start': 1380, 'minutes': 30}), datetime.fromisoformat('2026-10-19T10:00:00-04:00'))
            self.assertNotEqual(first['path'], second['path'])
            self.assertEqual(Path(first['path']).stat().st_mode & 0o777, 0o600)
            self.assertEqual(Path(first['path']).parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(len(json.loads(Path(first['path']).read_text())['blocks']), 4)
            result = latest_plan(root, '2026-10-19', 'America/Toronto')
            self.assertEqual(result['blocks'], second['blocks'])
            self.assertIsNone(latest_plan(root, '2026-10-20', 'America/Toronto'))
            self.assertIsNone(latest_plan(root, '2026-10-19', 'UTC'))
            self.assertNotIn('completed', result)

    def test_restarted_session_prefills_latest_local_choices_and_never_archived_ones(self):
        with tempfile.TemporaryDirectory() as root:
            data = snapshot()
            data['submitted_plan'] = {'blocks': [{'kind': 'dog_walk', 'start': 600, 'minutes': 30}]}
            self.assertNotIn('submitted_plan', session_snapshot(data, root))
            saved = save_plan(root, data, selected({'kind': 'dog_walk', 'start': 1200, 'minutes': 30}))
            opened = session_snapshot(data, root)
            self.assertEqual(opened['submitted_plan']['blocks'], saved['blocks'])
            self.assertEqual(data['submitted_plan']['blocks'][0]['start'], 600)
            opened['history'] = {'kind': 'tea-time'}
            with self.assertRaisesRegex(PlanError, 'read-only'):
                session_snapshot(opened, root)

    def test_empty_plan_clears_latest_choices(self):
        with tempfile.TemporaryDirectory() as root:
            request = selected()
            request['blocks'] = []
            save_plan(root, snapshot(), request)
            self.assertEqual(latest_plan(root, '2026-10-19', 'America/Toronto')['blocks'], [])

    def test_rejects_own_and_calendar_overlaps_including_free_events(self):
        with tempfile.TemporaryDirectory() as root:
            request = selected({'kind': 'focus', 'start': 540, 'minutes': 120}, {'kind': 'lunch', 'start': 600, 'minutes': 30})
            with self.assertRaisesRegex(PlanError, 'overlap'):
                save_plan(root, snapshot(), request)
            data = snapshot()
            data['agenda']['events'] = [{'title': 'Free event', 'free': True,
                'start': '2026-10-19T10:00:00-04:00', 'end': '2026-10-19T10:30:00-04:00'}]
            with self.assertRaisesRegex(PlanError, 'overlap'):
                save_plan(root, data, selected())
            self.assertEqual(list(Path(root).rglob('*.json')), [])

    def test_invalid_shapes_durations_domains_and_unknown_availability(self):
        cases = [selected({'kind': 'focus', 'start': 540, 'minutes': 60}), selected({'kind': 'lunch', 'start': 780, 'minutes': 60}),
                 selected({'kind': 'focus', 'start': 1200, 'minutes': 120}), selected({'kind': 'dog_walk', 'start': True, 'minutes': 30}),
                 selected({'kind': 'dog_walk', 'start': 1000, 'minutes': 30}), selected('bad')]
        with tempfile.TemporaryDirectory() as root:
            for request in cases:
                with self.subTest(request=request), self.assertRaises(PlanError):
                    save_plan(root, snapshot(), request)
            data = snapshot()
            data['availability']['status'] = 'partial'
            with self.assertRaisesRegex(PlanError, 'unverified'):
                save_plan(root, data, selected())
            request = selected()
            request['date'] = '2026-10-20'
            with self.assertRaisesRegex(PlanError, 'different day'):
                save_plan(root, snapshot(), request)

    def test_full_day_walk_and_touching_blocks_are_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            result = save_plan(root, snapshot(), selected({'kind': 'dog_walk', 'start': 1380, 'minutes': 30},
                {'kind': 'focus', 'start': 540, 'minutes': 180}, {'kind': 'lunch', 'start': 720, 'minutes': 30}))
            self.assertEqual(len(result['blocks']), 3)

    def test_corrupt_latest_skipped_with_warning_and_all_corrupt_is_disclosed(self):
        with tempfile.TemporaryDirectory() as root:
            saved = save_plan(root, snapshot(), selected())
            invalid = Path(saved['path']).with_name('9999999999.json')
            invalid.write_text('{')
            result = latest_plan(root, '2026-10-19', 'America/Toronto', with_warnings=True)
            self.assertEqual(result['plan']['blocks'], saved['blocks'])
            self.assertEqual(len(result['warnings']), 1)
            Path(saved['path']).unlink()
            with self.assertRaises(PlanError):
                latest_plan(root, '2026-10-19', 'America/Toronto')

    def test_loopback_authentication_and_explicit_post_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            server = HTTPServer(('127.0.0.1', 0), handler_for(snapshot(), root, 'private-test-capability'))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def call(method='POST', **updates):
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    headers = {'Origin': 'null', 'Host': '127.0.0.1:' + str(server.server_port), 'Content-Type': 'application/json', 'X-Brief-Token': 'private-test-capability'}
                    headers.update(updates)
                    connection.request(method, '/submit', json.dumps(selected()), headers)
                    response = connection.getresponse()
                    result = response.status, response.read(), response.getheader('Access-Control-Allow-Origin')
                    connection.close()
                    return result
                self.assertEqual(call('GET')[0], 404)
                self.assertEqual(call(**{'X-Brief-Token': ''})[0], 403)
                self.assertEqual(call(Origin='https://evil.example')[0], 403)
                self.assertEqual(call(Host='evil.example')[0], 403)
                self.assertEqual(list(Path(root).rglob('*.json')), [])
                status, body, cors = call()
                self.assertEqual(status, 200)
                self.assertTrue(json.loads(body)['ok'])
                self.assertEqual(cors, 'null')
                self.assertEqual(latest_plan(root, '2026-10-19', 'America/Toronto')['blocks'], selected()['blocks'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_normal_markup_has_actionable_setup_without_active_capability(self):
        html = render_submission(snapshot())
        self.assertIn('Enable local plan saving', html)
        self.assertNotIn('plan-submit-data', html)
        data = snapshot()
        data['plan_submission'] = {'endpoint': 'https://evil.example/submit', 'token': 'a' * 43}
        self.assertNotIn('plan-submit-data', render_submission(data))
        data['plan_submission']['endpoint'] = 'http://127.0.0.1:1234/submit'
        self.assertIn('plan-submit-data', render_submission(data))

    @unittest.skipUnless(shutil.which('node'), 'Node required for browser handler test')
    def test_registered_browser_handlers_only_save_final_review_and_allow_resubmission(self):
        script = r"""
const assert=require('assert'); const {mount}=require(process.argv[1]);
class Element {constructor(){this.children=[];this.listeners={};this.textContent='';}append(...items){this.children.push(...items);}replaceChildren(){this.children=[];}addEventListener(n,f){this.listeners[n]=f;}focus(){global.focused=this;}}
const opener=new Element(),review=new Element(),status=new Element(),calendar=new Element();
const state={date:'2026-10-19',timezone:'America/Toronto',blocks:[{kind:'dog_walk',start:1200,minutes:30}]};
calendar.getDayPlan=()=>JSON.parse(JSON.stringify(state));calendar.dayPlanner={setLocked(value){calendar.locked=value;}};
const config={textContent:JSON.stringify({endpoint:'http://127.0.0.1:123/submit',token:'private'})};
const root={querySelector(s){return {'.plan-submit-data':config,'.plan-submit-button':opener,'.plan-submit-review':review,'.plan-submit-status':status}[s];},closest(){return calendar;}};
global.document={createElement(){return new Element();}};let requests=[];
global.fetch=async(url,options)=>{requests.push(JSON.parse(options.body));return{ok:true,json:async()=>({ok:true,message:'Saved locally'})};};
(async()=>{
 mount(root);assert.equal(requests.length,0);opener.listeners.click();assert.equal(requests.length,0);
 let cancel=review.children.find(x=>x.textContent==='Cancel');cancel.listeners.click();assert.equal(requests.length,0);assert.equal(global.focused,opener);
 opener.listeners.click();let confirm=review.children.find(x=>x.textContent==='Submit plan');assert.equal(global.focused,confirm);assert.equal(review.children[1].children[0].textContent,'dog walk · 20:00–20:30');
 let submission=confirm.listeners.click();assert.equal(calendar.locked,true);await submission;
 assert.equal(requests.length,1);assert.equal(calendar.locked,false);assert.equal(opener.disabled,false);assert.equal(global.focused,status);
 await confirm.listeners.click();assert.equal(requests.length,1,'double click must not submit a second record');
 state.blocks[0].start=1215;opener.listeners.click();confirm=review.children.find(x=>x.textContent==='Submit plan');await confirm.listeners.click();assert.equal(requests.length,2);assert.equal(requests[1].blocks[0].start,1215);
 opener.listeners.click();confirm=review.children.find(x=>x.textContent==='Submit plan');state.blocks[0].start=1230;await confirm.listeners.click();assert.equal(requests.length,2);assert.match(status.textContent,/changed/);
 opener.listeners.click();confirm=review.children.find(x=>x.textContent==='Submit plan');global.fetch=async()=>{throw Error('offline');};await confirm.listeners.click();assert.equal(calendar.locked,false);assert.equal(opener.disabled,false);assert.match(status.textContent,/not confirmed saved/);
})().catch(e=>{console.error(e);process.exit(1);});
"""
        result = subprocess.run([shutil.which('node'), '-e', script, str(SKILL / 'assets/local-plan-submission.js')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
