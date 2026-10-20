"""Tea can remove confirmed local choices without mutating provider events or history."""
from copy import deepcopy
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
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from day_calendar import plan_revision, render_calendar
from local_plan_server import handler_for, session_snapshot
from plan_submission import latest_plan, save_plan
from report_history import publish
from test_calendar_optin import snapshot
from test_report_history import ReportSurface


class PlanRemovalTests(unittest.TestCase):
    def test_live_tea_removes_exact_saved_blocks_and_reloads_today_including_empty_plan(self):
        with tempfile.TemporaryDirectory() as root:
            data = snapshot()
            blocks = [{'kind': 'exercise', 'start': 720, 'minutes': 60},
                      {'kind': 'dog_walk', 'start': 1200, 'minutes': 30}]
            saved = save_plan(root, data, dict(date=data['report']['date'], timezone=data['report']['timezone'], blocks=blocks))
            archived = Path(saved['path']).read_bytes()
            data['history'] = {'kind': 'tea-time'}
            data['report']['title'] = 'Tea Time'
            # A new conflict and unavailable availability must not prevent removing an old choice.
            data['availability']['status'] = 'partial'
            data['agenda']['events'].append({'title': 'New conflict', 'time': '12:00–13:00',
                'start': '2026-10-19T12:00:00-04:00', 'end': '2026-10-19T13:00:00-04:00'})
            original = deepcopy(data)
            token = 'private-test-capability-' + 'x' * 32
            server = HTTPServer(('127.0.0.1', 0), handler_for(data, root, token))
            origin = 'http://127.0.0.1:' + str(server.server_port)
            data['plan_removal'] = {'endpoint': origin + '/plan/remove', 'token': token}
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def call(path='/plan/remove', request=None, method='POST', **updates):
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    headers = {'Origin': origin, 'Content-Type': 'application/json', 'X-Brief-Token': token}
                    headers.update(updates)
                    connection.request(method, path, json.dumps(request) if request is not None else None, headers)
                    response = connection.getresponse()
                    result = response.status, response.read().decode()
                    connection.close()
                    return result

                def page():
                    status, markup = call('/report/' + token, method='GET')
                    self.assertEqual(status, 200)
                    return ReportSurface(markup)

                def local_count(surface):
                    return sum(node['attrs'].get('data-plan-source') == 'local'
                               for node in surface.elements(surface.by_id['today']))

                initial = page()
                self.assertEqual(local_count(initial), 2)
                buttons = [node for node in initial.elements() if node['attrs'].get('class') == 'day-remove-submitted']
                self.assertEqual(len(buttons), 2)
                self.assertTrue(all('Remove ' in node['attrs']['aria-label'] for node in buttons))
                calendar = initial.by_id['focus-exercise']
                self.assertFalse(any(node['tag'] == 'input' for node in initial.elements(calendar)))
                self.assertFalse(any('day-block' in node['attrs'].get('class', '').split() for node in initial.elements(calendar)))
                request = dict(date=data['report']['date'], timezone=data['report']['timezone'],
                               revision=plan_revision(saved), block=blocks[0])
                failures = [(request, {'Origin': 'https://evil.example'}, 403),
                            (request, {'Origin': 'null'}, 403),
                            (request, {'Host': 'evil.example'}, 403),
                            (request, {'X-Brief-Token': 'wrong'}, 403),
                            (dict(request, revision='stale'), {}, 409),
                            (dict(request, block={'id': data['agenda']['events'][0]['id']}), {}, 400),
                            (dict(request, block=dict(blocks[0], start=735)), {}, 400),
                            (dict(request, date='2026-10-20'), {}, 400)]
                for payload, headers, expected in failures:
                    with self.subTest(payload=payload, headers=headers):
                        self.assertEqual(call(request=payload, **headers)[0], expected)
                        self.assertEqual(latest_plan(root, request['date'], request['timezone'])['path'], saved['path'])
                        self.assertEqual(local_count(page()), 2)
                with patch('plan_submission._append_plan', side_effect=OSError('disk full')):
                    self.assertEqual(call(request=request)[0], 500)
                self.assertEqual(latest_plan(root, request['date'], request['timezone'])['path'], saved['path'])
                self.assertEqual(local_count(page()), 2)
                self.assertEqual(call('/submit', request={'blocks': []})[0], 403)
                status, body = call(request=request)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)['blocks'], [blocks[1]])
                self.assertEqual(latest_plan(root, request['date'], request['timezone'])['blocks'], [blocks[1]])
                refreshed = page()
                self.assertEqual(local_count(refreshed), 1)
                self.assertNotIn('👟 Exercise', refreshed.visible_text(refreshed.by_id['today']))
                self.assertIn('Fixture stand-up', refreshed.visible_text(refreshed.by_id['today']))
                self.assertIn('1 local plan block', refreshed.visible_text(refreshed.by_id['day-overview']))
                self.assertEqual(call(request=request)[0], 409, 'An old tab cannot remove another saved version')
                request.update(revision=plan_revision(latest_plan(root, request['date'], request['timezone'])), block=blocks[1])
                self.assertEqual(call(request=request)[0], 200)
                self.assertEqual(latest_plan(root, request['date'], request['timezone'])['blocks'], [])
                empty = page()
                self.assertEqual(local_count(empty), 0)
                self.assertIn('Empty plan submitted', empty.visible_text(empty.by_id['focus-exercise']))
                self.assertIn('0 local plan blocks', empty.visible_text(empty.by_id['day-overview']))
                self.assertEqual(len(list(Path(saved['path']).parent.glob('*.json'))), 3)
                self.assertEqual(Path(saved['path']).read_bytes(), archived)
                data.pop('plan_removal')
                self.assertEqual(data, original)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_new_coffee_submission_invalidates_old_tea_identity_and_archives_strip_capability(self):
        with tempfile.TemporaryDirectory() as root:
            data = snapshot()
            blocks = [{'kind': 'exercise', 'start': 720, 'minutes': 60}]
            first = save_plan(root, data, dict(date=data['report']['date'], timezone=data['report']['timezone'], blocks=blocks))
            # Even resubmitting the identical choices creates a distinct saved version.
            second = save_plan(root, data, dict(date=data['report']['date'], timezone=data['report']['timezone'], blocks=blocks))
            from plan_submission import StalePlanError, remove_plan_block
            with self.assertRaises(StalePlanError):
                remove_plan_block(root, data, dict(date=data['report']['date'], timezone=data['report']['timezone'],
                    revision=plan_revision(first), block=blocks[0]))
            self.assertEqual(latest_plan(root, data['report']['date'], data['report']['timezone'])['path'], second['path'])
            data['plan_removal'] = {'endpoint': 'http://127.0.0.1:1234/plan/remove', 'token': 'private-capability-' + 'x' * 32}
            self.assertNotIn('plan_removal', session_snapshot(data, root))
            report = publish(root, data, 'morning-coffee')
            self.assertNotIn('plan_removal', json.loads(Path(report['snapshot']).read_text()))
            self.assertNotIn(data['plan_removal']['token'], Path(report['html']).read_text())
            data['submitted_plan'] = second
            data['plan_removal']['endpoint'] = 'https://evil.example/plan/remove'
            self.assertNotIn('day-plan-removal-data', render_calendar(data, read_only=True))

    @unittest.skipUnless(shutil.which('node'), 'Node required for client save acknowledgement test')
    def test_client_keeps_blocks_on_failure_and_refreshes_only_after_saved_acknowledgement(self):
        script = r"""
const assert=require('assert'),{mountRemoval}=require(process.argv[1]);
const config={endpoint:'http://127.0.0.1:1234/plan/remove',token:'private',date:'2026-10-19',timezone:'America/Toronto',revision:'v1'};
const blockFor=kind=>({kind,start:kind==='exercise'?720:1200,minutes:kind==='exercise'?60:30});
const timeouts=[],timeout=AbortSignal.timeout.bind(AbortSignal);
AbortSignal.timeout=milliseconds=>{timeouts.push(milliseconds);return timeout(milliseconds);};
class Element {
 constructor(){this.listeners={};this.children=[];this.disabled=false;this.value='';this.textContent='';}
 addEventListener(name,handler){this.listeners[name]=handler;}
 append(child){this.children.push(child);}
 focus(options){this.focusOptions=options;}
}
const todo={draftTitle:'Unsubmitted task',draftTag:'Transport',draftSubtask:'Check logs',filter:'active'};
let replacements=[],reloads=0,requests=[],resolvePost,resolveGet,nextPage;
function page(blocks){
 const doc={nodes:{},activeElement:todo,createElement:()=>new Element(),importNode:node=>node,
   querySelector(selector){return this.nodes[selector]||null;}};
 const status=new Element(),scroll={scrollTop:400};
 const buttons=blocks.map(kind=>Object.assign(new Element(),{dataset:{kind,start:kind==='exercise'?'720':'1200',minutes:kind==='exercise'?'60':'30'}}));
 const root={dataset:{},ownerDocument:doc,contains:element=>buttons.includes(element),
  querySelector:selector=>selector==='.day-plan-removal-data'?{textContent:JSON.stringify({...config,blocks:blocks.map(blockFor)})}:selector==='.day-scroll'?scroll:selector==='.day-remove-status'?status:null,
  querySelectorAll:()=>buttons};
 const agenda=new Element(),link={closest:()=>doc.nodes.agenda};
 doc.nodes={'#focus-exercise':root,'#today':new Element(),'.day-scroll':scroll,'#day-overview a[href="#today"]':link,agenda,'#local-todos':todo};
 for(const key of ['#focus-exercise','#today','agenda'])doc.nodes[key].replaceWith=function(node){
   doc.nodes[key]=node;node.ownerDocument=doc;replacements.push(key);
   node.replaceWith=this.replaceWith;
 };
 doc.defaultView={location:{href:'http://127.0.0.1:1234/report/private',reload(){reloads++;}},scrollX:0,scrollY:850,
  scrollTo(x,y){this.restoredScroll=[x,y];},DOMParser:class{parseFromString(html,type){assert.equal(type,'text/html');return nextPage;}}};
 return {doc,root,status,scroll,buttons};
}
const initial=page(['exercise','dog_walk']);
// The parser returns a Document, as in a browser.
global.fetch=(url,options)=>{
 requests.push({url,options,body:options.body?JSON.parse(options.body):null});
 return new Promise(resolve=>{if(options.method==='POST')resolvePost=resolve;else resolveGet=resolve;});
};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 mountRemoval(initial.root);assert.equal(requests.length,0);
 let save=initial.buttons[0].listeners.click();assert.equal(initial.buttons[0].disabled,true);assert.equal(initial.buttons[1].disabled,true);
 await initial.buttons[1].listeners.click();assert.equal(requests.length,1);
 resolvePost({ok:false,json:async()=>({error:'disk full'})});await save;
 assert.equal(initial.buttons[0].disabled,false);assert.match(initial.status.textContent,/not confirmed saved: disk full/);
 assert.equal(replacements.length,0);assert.strictEqual(initial.doc.nodes['#local-todos'],todo);
 save=initial.buttons[0].listeners.click();resolvePost({ok:true,json:async()=>({ok:false,blocks:[]})});await save;
 save=initial.buttons[0].listeners.click();resolvePost({ok:true,json:async()=>({ok:true})});await save;
 save=initial.buttons[0].listeners.click();resolvePost({ok:true,json:async()=>({ok:true,blocks:['exercise','dog_walk'].map(blockFor)})});await save;
 assert.match(initial.status.textContent,/not confirmed saved.*expected remaining blocks/,'unchanged plan is not an acknowledgement');
 save=initial.buttons[0].listeners.click();resolvePost({ok:true,json:async()=>({ok:true,blocks:[]})});await save;
 assert.match(initial.status.textContent,/not confirmed saved.*expected remaining blocks/,'losing another block is not an acknowledgement');
 save=initial.buttons[0].listeners.click();resolvePost({ok:true,json:async()=>({ok:true,blocks:[blockFor('exercise')]})});await save;
 assert.match(initial.status.textContent,/not confirmed saved.*expected remaining blocks/,'removing a different block is not an acknowledgement');
 assert.equal(requests.filter(r=>!r.body).length,0,'failed acknowledgements never refresh or mutate the view');
 save=initial.buttons[0].listeners.click();resolvePost({ok:true,json:async()=>({ok:true,blocks:[{kind:'dog_walk',start:1200,minutes:30}]})});await tick();
 assert.equal(replacements.length,0,'keep the confirmed DOM until complete HTML is available');
 const fresh=page(['dog_walk']);nextPage=fresh.doc;
 resolveGet({ok:true,text:async()=>'<html>current report</html>'});await save;
 assert.deepEqual(replacements,['#focus-exercise','#today','agenda']);
 assert.strictEqual(initial.doc.nodes['#focus-exercise'],fresh.root);
 assert.strictEqual(initial.doc.nodes['#local-todos'],todo);
 assert.deepEqual(todo,{draftTitle:'Unsubmitted task',draftTag:'Transport',draftSubtask:'Check logs',filter:'active'});
 assert.strictEqual(initial.doc.activeElement,todo,'refresh leaves a task editor focused');
 assert.equal(fresh.scroll.scrollTop,400);assert.deepEqual(initial.doc.defaultView.restoredScroll,[0,850]);
 assert.equal(typeof fresh.buttons[0].listeners.click,'function','replacement calendar is mounted');
 assert.equal(fresh.status.textContent,'Block removed locally.');assert.equal(reloads,0);
 const posted=requests.filter(r=>r.body).at(-1);
 assert.deepEqual(posted.body,{date:config.date,timezone:config.timezone,revision:'v1',block:{kind:'exercise',start:720,minutes:60}});
 assert.equal(posted.options.headers['X-Brief-Token'],'private');
 // The next durable removal succeeds, but refreshing HTML fails. Keep saved-vs-display status distinct.
 save=fresh.buttons[0].listeners.click();resolvePost({ok:true,json:async()=>({ok:true,blocks:[]})});await tick();
 resolveGet({ok:false});await save;
 assert.match(fresh.status.textContent,/Block removed locally.*updated view could not load/);
 assert.doesNotMatch(fresh.status.textContent,/not confirmed saved/);
 assert.equal(fresh.buttons[0].disabled,true,'stale removal controls stay locked');
 assert.equal(replacements.length,3);assert.strictEqual(initial.doc.nodes['#local-todos'],todo);
 const retry=fresh.status.children.at(-1);assert.equal(retry.textContent,'Refresh saved plan');
 const postCount=requests.filter(r=>r.body).length;
 const retrying=retry.listeners.click();await tick();
 const empty=page([]);nextPage=empty.doc;resolveGet({ok:true,text:async()=>'<html>empty plan</html>'});await retrying;
 assert.equal(requests.filter(r=>r.body).length,postCount,'refresh retry must never repeat a removal');
 assert.deepEqual(replacements,['#focus-exercise','#today','agenda','#focus-exercise','#today','agenda']);
 assert.strictEqual(initial.doc.nodes['#focus-exercise'],empty.root);assert.strictEqual(initial.doc.nodes['#local-todos'],todo);
 assert.equal(empty.buttons.length,0);assert.equal(reloads,0);
 assert.equal(timeouts.length,requests.length);assert.ok(timeouts.every(value=>value===10000));
 assert.ok(requests.every(request=>request.options.signal instanceof AbortSignal),'both POST and GET have abort signals');
})().catch(error=>{console.error(error);process.exit(1);});
"""
        result = subprocess.run(['node', '-e', script, str(SKILL / 'assets/day-calendar.js')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
