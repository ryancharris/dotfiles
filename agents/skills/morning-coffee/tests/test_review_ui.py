"""Local PR/RFC completion stays distinct from source approvals and queue totals."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from test_report_history import ReportSurface, snapshot
from render_brief import render
from review_state import review_key, canonical_url

SKILL = Path(__file__).resolve().parents[1]


class ReviewUiTests(unittest.TestCase):
    def with_marks(self):
        data = snapshot()
        data['review_state'] = {}
        for kind, section in [('pr', 'reviews'), ('rfc', 'rfcs')]:
            url = data[section]['items'][0]['url']
            data['review_state'][review_key(kind, url)] = {
                'version': 1, 'kind': kind, 'url': canonical_url(url),
                'done': True, 'updated_at': '2026-10-20T12:00:00Z',
            }
        return data

    def test_static_marks_leave_source_approvals_and_eligible_totals_unchanged(self):
        data = self.with_marks()
        original = deepcopy(data)
        surface = ReportSurface(render(data))
        rows = [n for n in surface.elements() if 'data-local-review' in n['attrs']]
        self.assertEqual(len(rows), 2)
        self.assertEqual({n['attrs']['data-review-kind'] for n in rows}, {'pr', 'rfc'})
        self.assertTrue(all(n['attrs']['data-review-done'] == 'true' for n in rows))
        self.assertTrue(all('hidden' not in n['attrs'] for n in rows))
        buttons = [n for n in surface.elements() if 'data-review-toggle' in n['attrs']]
        self.assertTrue(all('disabled' in n['attrs'] for n in buttons))
        visible = surface.visible_text()
        self.assertIn('Done locally', visible)
        self.assertIn('Open the live Morning Coffee workspace to save.', visible)
        self.assertNotIn('No verified approval from you', visible)
        archive = next(n for n in surface.elements() if 'data-rfc-completed' in n['attrs'])
        archive['attrs']['open'] = ''
        self.assertIn('No verified approval from you', surface.visible_text(archive))
        self.assertIn('REVIEW_REQUIRED', visible)
        self.assertIn('1 retained requests', visible)
        self.assertEqual(data, original)

    def test_coffee_and_tea_embed_review_session_without_editing_tea_calendar(self):
        for kind in ['morning-coffee', 'tea-time']:
            with self.subTest(kind=kind):
                data = self.with_marks()
                data['history'] = {'kind': kind}
                data['review_interaction'] = {'endpoint': 'http://127.0.0.1:8765/review', 'token': 'test</script>token'}
                page = render(data)
                surface = ReportSurface(page)
                configs = [n for n in surface.elements() if n['attrs'].get('class') == 'review-interaction-data']
                self.assertEqual(len(configs), 1)
                self.assertEqual(json.loads(configs[0]['children'][0]), data['review_interaction'])
                self.assertNotIn('test</script>token', page)
                self.assertIn('data-filter="progress"', page)
                self.assertIn('<option value="todo" selected>To review</option>', page)
                if kind == 'tea-time':
                    calendar = surface.by_id['focus-exercise']
                    self.assertFalse(any(n['tag'] in ('input', 'button') for n in surface.elements(calendar)))

    def test_provider_approval_can_coexist_with_a_separate_local_done_mark(self):
        data = self.with_marks()
        data['rfcs']['items'][0]['user_approved'] = True
        surface = ReportSurface(render(data))
        rfc = surface.by_id['rfcs-to-review']
        self.assertNotIn('Approved by you', surface.visible_text(rfc))
        archive = next(n for n in surface.elements(rfc) if 'data-rfc-completed' in n['attrs'])
        archive['attrs']['open'] = ''
        self.assertIn('Approved by you', surface.visible_text(rfc))
        self.assertIn('Done locally', surface.visible_text(rfc))

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for local interaction tests')
    def test_success_failure_undo_filters_and_keyboard_control_contract(self):
        script = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {mount}=require(process.argv[1]+'/assets/local-review-state.js');
class Element {
  constructor(){this.listeners={};this.dataset={};this.textContent='';this.value='';this.hidden=false;this.attributes={};}
  addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
  fire(type,event={}){return Promise.all((this.listeners[type]||[]).map(fn=>fn({...event,type,target:this})));}
  setAttribute(name,value){this.attributes[name]=value;}
  dispatchEvent(event){this.fire(event.type,event);if(event.bubbles&&this.parent)this.parent.dispatchEvent(event);}
  focus(){this.focused=true;}
  scrollIntoView(){}
  closest(){return this.parent;}
}
class LocalEvent {constructor(type,options={}){this.type=type;Object.assign(this,options);}}
global.CustomEvent=LocalEvent;
function fixture(){
  const inputs={};for(const name of ['text','status','effort','team','authors','request-type','progress']){inputs[name]=new Element();inputs[name].tagName=name==='text'?'INPUT':'SELECT';}
  inputs.authors.value='transport';inputs.authors.dataset.defaultValue='transport';inputs.progress.value='todo';
  const pageSize=new Element();pageSize.value='10';const reset=new Element();
  const controls=new Element();controls.querySelectorAll=()=>Object.values(inputs);
  controls.querySelector=q=>q==='[data-page-size]'?pageSize:q==='[data-action="clear"]'?reset:inputs[q.match(/data-filter="([^"]+)"/)[1]];
  const count=new Element(),filterBadge=new Element(),empty=new Element(),previous=new Element(),next=new Element(),pageLabel=new Element(),pagination=new Element();
  pagination.querySelector=q=>q==='[data-action="previous"]'?previous:q==='[data-action="next"]'?next:pageLabel;
  const queue=new Element();queue.querySelector=q=>({'.pr-controls':controls,'.pr-count':count,'.pr-filter-badge':filterBadge,'.pr-empty':empty,'.pr-pagination':pagination}[q]);
  const row=(id,done,transport,kind='pr')=>{
    const r=new Element();r.dataset={reviewKind:kind,reviewUrl:'https://example.com/'+id,reviewDone:String(done),authorOnTransport:String(transport),status:'READY',effort:'S',teams:'',requestType:'direct'};r.textContent=id;
    r.button=new Element();r.label=new Element();r.message=new Element();r.providerApproval='REVIEW_REQUIRED';r.parent=queue;
    r.querySelector=q=>q==='[data-review-toggle]'?r.button:q==='.local-review-label'?r.label:r.message;
    return r;
  };
  const rows=[row('one',false,true),row('two',true,true),row('three',false,false)],rfc=row('rfc',false,true,'rfc');rfc.parent=null;
  queue.querySelectorAll=()=>rows;
  const notice=new Element(),config={endpoint:'http://127.0.0.1:8765/review',token:'test-token'};
  const doc={getElementById:()=>null,querySelector:q=>q==='.review-interaction-data'?{textContent:JSON.stringify(config)}:notice,querySelectorAll:q=>q==='.pr-queue'?[queue]:q==='[data-local-review]'?[...rows,rfc]:[]};
  vm.runInNewContext(fs.readFileSync(process.argv[1]+'/assets/brief.js','utf8'),{document:doc,window:{location:{hash:''},addEventListener(){}}});
  return {doc,rows,rfc,inputs,pageSize,reset,count,filterBadge,notice,config};
}
(async()=>{
  const f=fixture();let pending,calls=[];
  mount(f.doc,(endpoint,options)=>{calls.push({endpoint,options});return new Promise(resolve=>{pending=resolve;});});
  assert.deepEqual(f.rows.map(r=>r.hidden),[false,true,true]);assert.match(f.count.textContent,/1 matching · 3 retained requests/);
  assert.equal(f.filterBadge.hidden,true);
  f.inputs.status.value='BLOCKED';await f.inputs.status.fire('change');assert.equal(f.filterBadge.textContent,'1 active');assert.equal(f.filterBadge.hidden,false);assert.deepEqual(f.rows.map(r=>r.hidden),[true,true,true]);
  f.inputs.effort.value='S';await f.inputs.effort.fire('change');assert.equal(f.filterBadge.textContent,'2 active');
  await f.reset.fire('click');assert.equal(f.inputs.status.value,'');assert.equal(f.inputs.effort.value,'');assert.equal(f.filterBadge.hidden,true);assert.deepEqual(f.rows.map(r=>r.hidden),[false,true,true]);
  f.inputs.progress.value='';await f.inputs.progress.fire('change');assert.deepEqual(f.rows.map(r=>r.hidden),[false,false,true]);
  f.inputs.authors.value='all';await f.inputs.authors.fire('change');assert.deepEqual(f.rows.map(r=>r.hidden),[false,false,false]);
  f.inputs.progress.value='done';await f.inputs.progress.fire('change');assert.deepEqual(f.rows.map(r=>r.hidden),[true,false,true]);
  f.pageSize.value='25';await f.reset.fire('click');assert.equal(f.inputs.authors.value,'transport');assert.equal(f.inputs.progress.value,'todo');assert.equal(f.pageSize.value,'25');
  const first=f.rows[0],saving=first.button.fire('click');
  assert.equal(first.dataset.reviewDone,'false');assert.equal(first.hidden,false);assert.equal(first.button.disabled,true);assert.match(f.notice.textContent,/Saving/);
  assert.deepEqual(JSON.parse(calls[0].options.body),{kind:'pr',url:first.dataset.reviewUrl,done:true});assert.equal(calls[0].options.headers['X-Brief-Token'],'test-token');
  first.textContent='one Done locally'; // Simulate the browser's changed row text after saving.
  pending({ok:true,json:async()=>({ok:true,record:{kind:'pr',url:first.dataset.reviewUrl,done:true}})});await saving;
  assert.equal(first.dataset.reviewDone,'true');assert.equal(first.button.textContent,'Undo local done');assert.equal(first.hidden,true);assert.match(f.count.textContent,/0 matching · 3 retained requests/);assert.match(f.notice.textContent,/Saved: Done locally/);assert.equal(f.count.focused,true);
  assert.equal(first.providerApproval,'REVIEW_REQUIRED'); // Provider evidence is never changed.
  f.inputs.progress.value='done';await f.inputs.progress.fire('change');assert.equal(first.hidden,false);assert.match(f.count.textContent,/2 matching · 3 retained/);
  f.inputs.text.value='done locally';await f.inputs.text.fire('input');assert.equal(first.hidden,false);assert.match(f.count.textContent,/1 matching · 3 retained/);
  f.inputs.text.value='';await f.inputs.text.fire('input');
  const failedUndo=first.button.fire('click');pending({ok:false,json:async()=>({ok:false,error:'Undo write failed'})});await failedUndo;
  assert.equal(first.dataset.reviewDone,'true');assert.equal(first.button.textContent,'Undo local done');assert.equal(first.hidden,false);assert.match(f.notice.textContent,/Undo write failed/);
  const undo=first.button.fire('click');assert.equal(first.dataset.reviewDone,'true');
  pending({ok:true,json:async()=>({ok:true,record:{kind:'pr',url:first.dataset.reviewUrl,done:false}})});await undo;
  assert.equal(first.dataset.reviewDone,'false');assert.equal(first.button.attributes['aria-pressed'],'false');assert.equal(first.hidden,true);
  f.inputs.progress.value='todo';await f.inputs.progress.fire('change');const failed=first.button.fire('click');
  pending({ok:false,json:async()=>({ok:false,error:'Write failed'})});await failed;
  assert.equal(first.dataset.reviewDone,'false');assert.equal(first.hidden,false);assert.equal(first.button.disabled,false);assert.match(f.notice.textContent,/Save not confirmed: Write failed/);
  const unconfirmed=first.button.fire('click');pending({ok:true,json:async()=>({ok:true})});await unconfirmed;assert.equal(first.dataset.reviewDone,'false');assert.match(f.notice.textContent,/did not confirm/);
  const rfcSave=f.rfc.button.fire('click');pending({ok:true,json:async()=>({ok:true,record:{kind:'rfc',url:f.rfc.dataset.reviewUrl,done:true}})});await rfcSave;
  assert.equal(f.rfc.dataset.reviewDone,'true');assert.equal(f.rfc.hidden,false);assert.equal(f.rfc.providerApproval,'REVIEW_REQUIRED');
  const archived=fixture();archived.doc.querySelector=q=>q==='.review-interaction-data'?null:archived.notice;let staticCalls=0;
  mount(archived.doc,()=>{staticCalls++;});assert.equal(archived.rows[0].button.disabled,true);await archived.rows[0].button.fire('click');assert.equal(staticCalls,0);
  console.log('Pending/success/failure/undo, PR filters and retained counts, RFC marks, source approval isolation and static read-only checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', script, str(SKILL)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
