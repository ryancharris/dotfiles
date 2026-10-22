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
from plan_submission import PlanError, StalePlanError, latest_plan, remove_plan_block, render_submission, save_plan
from day_calendar import calendar_data, render_calendar, plan_revision, removal_config
from calendar_state import calendar_key, save_calendar_state, load_calendar_state
from local_plan_server import handler_for, interactive_snapshot, session_snapshot


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
    def test_plan_compare_and_swap_prevents_stale_edits_and_removed_block_resurrection(self):
        with tempfile.TemporaryDirectory() as root:
            source = snapshot()
            request = dict(selected({'kind': 'dog_walk', 'start': 780, 'minutes': 30}), base_revision=None)
            first = save_plan(root, source, request, require_revision=True)
            stale = dict(request, base_revision=plan_revision(first))
            removed = remove_plan_block(root, source, {'date': request['date'], 'timezone': request['timezone'],
                'revision': stale['base_revision'], 'block': request['blocks'][0]})
            before = list(Path(root).rglob('*.json'))
            with self.assertRaises(StalePlanError):
                save_plan(root, source, stale, require_revision=True)
            with self.assertRaises(StalePlanError):
                save_plan(root, source, selected(), require_revision=True)
            self.assertEqual(list(Path(root).rglob('*.json')), before)
            self.assertEqual(latest_plan(root, request['date'], request['timezone'])['blocks'], [])
            saved = save_plan(root, source, dict(stale, base_revision=plan_revision(removed)), require_revision=True)
            self.assertEqual(saved['blocks'], request['blocks'])
            view = interactive_snapshot(source, root, 'http://127.0.0.1:1234', 'x' * 40)
            self.assertEqual(view['plan_submission']['base_revision'], plan_revision(saved))
            self.assertIn(plan_revision(saved), render_submission(view))

    def test_named_focus_roundtrip_edit_clear_removal_and_completion(self):
        with tempfile.TemporaryDirectory() as root:
            source = snapshot()
            named = {'kind': 'focus', 'start': 540, 'minutes': 45, 'name': '  Review <migration> & "SQL"  '}
            first = save_plan(root, source, selected(named, {'kind': 'lunch', 'start': 780, 'minutes': 30}))
            self.assertEqual(first['blocks'][0]['name'], 'Review <migration> & "SQL"')
            reopened = session_snapshot(source, root)
            block = calendar_data(reopened)['blocks'][0]
            self.assertEqual((block['name'], block['label']), ('Review <migration> & "SQL"', '🔎 Review <migration> & "SQL"'))
            self.assertEqual(calendar_data(reopened, read_only=True)['submitted_blocks'][0]['name'], block['name'])
            markup = render_calendar(reopened)
            self.assertIn('data-focus-name type="text" maxlength="120" value="Review &lt;migration&gt; &amp; &quot;SQL&quot;"', markup)
            self.assertNotIn('<migration>', markup)
            self.assertIn('Review &lt;migration&gt;', render_calendar(reopened, read_only=True))
            key = calendar_key(reopened, first['blocks'][0], local=True)
            save_calendar_state(root, reopened, {'key': key, 'done': True})
            renamed = save_plan(root, source, dict(selected(dict(named, name='Ship migration')), base_revision=plan_revision(first)), require_revision=True)
            self.assertNotEqual(plan_revision(first), plan_revision(renamed))
            reopened = session_snapshot(source, root)
            self.assertEqual(calendar_key(reopened, renamed['blocks'][0], local=True), key)
            self.assertEqual(load_calendar_state(root, reopened), {key: True})
            with self.assertRaises(StalePlanError):
                remove_plan_block(root, source, {'date': source['report']['date'], 'timezone': source['report']['timezone'],
                    'revision': plan_revision(first), 'block': {'kind': 'focus', 'start': 540, 'minutes': 45}})
            # The removal request identity intentionally excludes the editable name.
            removed = remove_plan_block(root, source, {'date': source['report']['date'], 'timezone': source['report']['timezone'],
                'revision': plan_revision(renamed), 'block': {'kind': 'focus', 'start': 540, 'minutes': 45}})
            self.assertEqual(removed['blocks'], [])
            self.assertEqual(removed['removed_block']['name'], 'Ship migration')
            cleared = save_plan(root, source, selected(dict(named, name='   ')))
            self.assertNotIn('name', cleared['blocks'][0])
            self.assertEqual(calendar_data(session_snapshot(source, root))['blocks'][0]['label'], '🔎 Focus')
            self.assertEqual(json.loads(Path(first['path']).read_text())['blocks'][0]['name'], 'Review <migration> & "SQL"')

    def test_name_validation_and_removal_preserves_remaining_name(self):
        with tempfile.TemporaryDirectory() as root:
            source = snapshot()
            base = {'kind': 'focus', 'start': 540, 'minutes': 45}
            for name in (None, 1, [], {}, 'x' * 121, 'two\nlines', '\x00bad', '\ud800'):
                with self.subTest(name=repr(name)), self.assertRaises(PlanError):
                    save_plan(root, source, selected(dict(base, name=name)))
            self.assertEqual(list(Path(root).rglob('*.json')), [])
            with self.assertRaises(PlanError):
                save_plan(root, source, selected({'kind': 'lunch', 'start': 780, 'minutes': 30, 'name': 'No'}))
            named = dict(base, name='🔎' * 120)
            lunch = {'kind': 'lunch', 'start': 780, 'minutes': 30}
            first = save_plan(root, source, selected(named, lunch))
            opened = interactive_snapshot(source, root, 'http://127.0.0.1:1234', 'x' * 40)
            opened['plan_removal'] = {'endpoint': 'http://127.0.0.1:1234/plan/remove', 'token': 'x' * 40}
            self.assertEqual(removal_config(opened)['blocks'][0]['name'], named['name'])
            result = remove_plan_block(root, source, {'date': source['report']['date'], 'timezone': source['report']['timezone'],
                'revision': plan_revision(first), 'block': lunch})
            self.assertEqual(result['blocks'], [named])
            self.assertEqual(latest_plan(root, source['report']['date'], source['report']['timezone'])['blocks'], [named])

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

    def test_custom_focus_save_restore_conflict_edit_and_remove(self):
        with tempfile.TemporaryDirectory() as root:
            source = snapshot()
            short = save_plan(root, source, selected({'kind': 'focus', 'start': 540, 'minutes': 45}))
            opened = session_snapshot(source, root)
            focus = next(row for row in calendar_data(opened)['blocks'] if row['kind'] == 'focus')
            self.assertEqual((focus['start'], focus['minutes']), (540, 45))
            markup = render_calendar(opened)
            self.assertIn('data-duration type="number" min="15" max="480" step="15" value="45"', markup)
            self.assertIn('data-duration-summary>45m', markup)
            self.assertEqual(calendar_data(opened, read_only=True)['submitted_blocks'][0]['minutes'], 45)
            source['availability']['busy'] = [{'start': '2026-10-19T09:30:00-04:00', 'end': '2026-10-19T10:00:00-04:00'}]
            opened = session_snapshot(source, root)
            data = calendar_data(opened)
            focus = next(row for row in data['blocks'] if row['kind'] == 'focus')
            self.assertEqual((focus['start'], focus['minutes']), (None, 45), 'retain custom length when new calendar facts unplace it')
            self.assertTrue(data['submitted_blocks'][0]['conflict'])
            with self.assertRaisesRegex(PlanError, 'overlap'):
                save_plan(root, source, selected({'kind': 'focus', 'start': 540, 'minutes': 45}))
            edited = save_plan(root, source, dict(selected({'kind': 'focus', 'start': 600, 'minutes': 150}), base_revision=plan_revision(short)), require_revision=True)
            self.assertEqual(latest_plan(root, '2026-10-19', 'America/Toronto')['blocks'], edited['blocks'])
            removed = remove_plan_block(root, source, {'date': '2026-10-19', 'timezone': 'America/Toronto', 'revision': plan_revision(edited), 'block': edited['blocks'][0]})
            self.assertEqual(removed['blocks'], [])
            self.assertEqual(json.loads(Path(short['path']).read_text())['blocks'][0]['minutes'], 45)

    def test_legacy_long_focus_duration_remains_editable_and_removable(self):
        with tempfile.TemporaryDirectory() as root:
            saved = save_plan(root, snapshot(), selected({'kind': 'focus', 'start': 540, 'minutes': 121}))
            reopened = session_snapshot(snapshot(), root)
            self.assertEqual(calendar_data(reopened)['blocks'][0]['minutes'], 121)
            removed = remove_plan_block(root, snapshot(), {'date': '2026-10-19', 'timezone': 'America/Toronto',
                'revision': plan_revision(saved), 'block': saved['blocks'][0]})
            self.assertEqual(removed['blocks'], [])

    def test_custom_focus_http_roundtrip_and_rejected_extension(self):
        with tempfile.TemporaryDirectory() as root:
            source = snapshot()
            source['availability']['busy'] = [{'start': '2026-10-19T10:00:00-04:00', 'end': '2026-10-19T10:30:00-04:00'}]
            server = HTTPServer(('127.0.0.1', 0), handler_for(source, root, 'private-test-capability'))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def submit(minutes, name='Migration review'):
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    connection.request('POST', '/submit', json.dumps(selected({'kind': 'focus', 'start': 540, 'minutes': minutes, 'name': name})),
                        {'Origin': 'null', 'Content-Type': 'application/json', 'X-Brief-Token': 'private-test-capability'})
                    response = connection.getresponse()
                    result = response.status, json.loads(response.read())
                    connection.close()
                    return result
                status, result = submit(45)
                self.assertEqual(status, 200)
                self.assertEqual(result['blocks'][0]['minutes'], 45)
                self.assertEqual(result['blocks'][0]['name'], 'Migration review')
                self.assertEqual(submit(75)[0], 400)
                self.assertEqual(submit(16)[0], 400)
                reopened = session_snapshot(source, root)
                self.assertEqual(reopened['submitted_plan']['blocks'][0]['minutes'], 45)
                self.assertEqual(reopened['submitted_plan']['blocks'][0]['name'], 'Migration review')
                self.assertEqual(submit(45, 'x' * 121)[0], 400)
                self.assertEqual(submit(45, '')[0], 200)
                self.assertNotIn('name', session_snapshot(source, root)['submitted_plan']['blocks'][0])
                self.assertEqual(next(row for row in calendar_data(reopened)['blocks'] if row['kind'] == 'focus')['minutes'], 45)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

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
        cases = [selected({'kind': 'focus', 'start': 540, 'minutes': 16}), selected({'kind': 'lunch', 'start': 780, 'minutes': 60}),
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
const config={textContent:JSON.stringify({endpoint:'http://127.0.0.1:123/submit',token:'private',base_revision:null})};
const root={querySelector(s){return {'.plan-submit-data':config,'.plan-submit-button':opener,'.plan-submit-review':review,'.plan-submit-status':status}[s];},closest(){return calendar;}};
global.document={createElement(){return new Element();}};let requests=[];
global.fetch=async(url,options)=>{requests.push(JSON.parse(options.body));return{ok:true,json:async()=>({ok:true,message:'Saved locally',blocks:requests.at(-1).blocks,revision:'saved-'+requests.length})};};
(async()=>{
 mount(root);assert.equal(requests.length,0);opener.listeners.click();assert.equal(requests.length,0);
 let cancel=review.children.find(x=>x.textContent==='Cancel');cancel.listeners.click();assert.equal(requests.length,0);assert.equal(global.focused,opener);
 opener.listeners.click();let confirm=review.children.find(x=>x.textContent==='Submit plan');assert.equal(global.focused,confirm);assert.equal(review.children[1].children[0].textContent,'dog walk · 20:00–20:30');
 let submission=confirm.listeners.click();assert.equal(calendar.locked,true);await submission;
 assert.equal(requests.length,1);assert.equal(requests[0].base_revision,null);assert.equal(calendar.planSubmission.getBaseRevision(),'saved-1');assert.equal(calendar.locked,false);assert.equal(opener.disabled,false);assert.equal(global.focused,status);
 await confirm.listeners.click();assert.equal(requests.length,1,'double click must not submit a second record');
 state.blocks[0].start=1215;opener.listeners.click();confirm=review.children.find(x=>x.textContent==='Submit plan');await confirm.listeners.click();assert.equal(requests.length,2);assert.equal(requests[1].blocks[0].start,1215);assert.equal(requests[1].base_revision,'saved-1');
 opener.listeners.click();confirm=review.children.find(x=>x.textContent==='Submit plan');state.blocks[0].start=1230;await confirm.listeners.click();assert.equal(requests.length,2);assert.match(status.textContent,/changed/);
 opener.listeners.click();confirm=review.children.find(x=>x.textContent==='Submit plan');global.fetch=async()=>({ok:false,status:409,json:async()=>({error:'Your saved plan changed.'})});await confirm.listeners.click();assert.equal(state.blocks[0].start,1230);assert.equal(calendar.planSubmission.getBaseRevision(),'saved-2');assert.equal(calendar.locked,false);assert.match(status.textContent,/saved plan changed/);
 opener.listeners.click();confirm=review.children.find(x=>x.textContent==='Submit plan');global.fetch=async()=>{throw Error('offline');};await confirm.listeners.click();assert.equal(calendar.locked,false);assert.equal(opener.disabled,false);assert.match(status.textContent,/not confirmed saved/);
 state.blocks=[{kind:'focus',start:540,minutes:45,name:'Review <SQL> & "migration"'}];
 opener.listeners.click();confirm=review.children.find(x=>x.textContent==='Submit plan');
 assert.equal(review.children[1].children[0].textContent,'Review <SQL> & "migration" · 09:00–09:45');
 let captured;
 global.fetch=async(url,options)=>{captured=JSON.parse(options.body);assert.ok(options.signal instanceof AbortSignal);return {ok:true,json:async()=>({ok:true,revision:'unverified',blocks:[{kind:'focus',start:540,minutes:45}]})};};
 await confirm.listeners.click();assert.equal(captured.blocks[0].name,'Review <SQL> & "migration"');
 assert.match(status.textContent,/not confirmed saved.*blocks and names/);assert.equal(calendar.planSubmission.getBaseRevision(),'saved-2');
 opener.listeners.click();confirm=review.children.find(x=>x.textContent==='Submit plan');
 state.blocks[0].name='Changed after review';captured=null;await confirm.listeners.click();assert.equal(captured,null);assert.match(status.textContent,/changed/);
 opener.listeners.click();confirm=review.children.find(x=>x.textContent==='Submit plan');
 global.fetch=async(url,options)=>{captured=JSON.parse(options.body);return {ok:true,json:async()=>({ok:true,message:'Saved',revision:'named',blocks:captured.blocks})};};
 await confirm.listeners.click();assert.equal(calendar.planSubmission.getBaseRevision(),'named');assert.equal(captured.blocks[0].name,'Changed after review');
 state.blocks[0].name='';opener.listeners.click();confirm=review.children.find(x=>x.textContent==='Submit plan');await confirm.listeners.click();assert.equal('name' in captured.blocks[0],false);

})().catch(e=>{console.error(e);process.exit(1);});
"""
        result = subprocess.run([shutil.which('node'), '-e', script, str(SKILL / 'assets/local-plan-submission.js')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
