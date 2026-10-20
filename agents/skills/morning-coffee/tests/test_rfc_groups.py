"""RFC completion groups preserve source approvals, evidence and transactional saves."""
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import unittest

from test_report_history import ReportSurface, snapshot
from render_brief import render
from review_state import review_key

SKILL = Path(__file__).resolve().parents[1]


def attribute_node(page, attribute, root=None):
    return next(node for node in page.elements(root) if attribute in node['attrs'])


class RfcGroupTests(unittest.TestCase):
    def test_tea_overview_preserves_safe_rendering_for_invalid_source_links(self):
        data = snapshot()
        data['history'] = {'kind': 'tea-time'}
        data['rfcs']['items'][0]['url'] = 'javascript:alert(1)'
        page = render(data)
        self.assertIn('Fixture queue isolation', page)
        self.assertNotIn('href="javascript:', page)

    def test_source_approved_and_locally_done_are_collapsed_in_coffee_and_tea(self):
        for kind in ('morning-coffee', 'tea-time'):
            with self.subTest(kind=kind):
                data = snapshot()
                data['history'] = {'kind': kind}
                original = data['rfcs']['items'][0]
                data['rfcs']['items'] = []
                for index in range(4):
                    row = deepcopy(original)
                    row.update(id='RFC-' + str(index), title='Decision ' + str(index),
                               url='https://example.com/rfc/' + str(index), user_approved=index in (1, 3))
                    data['rfcs']['items'].append(row)
                data['review_state'] = {review_key('rfc', row['url']): {'done': True}
                                        for row in data['rfcs']['items'][2:]}
                before = deepcopy(data)
                page = ReportSurface(render(data))
                section = page.by_id['rfcs-to-review']
                pending = attribute_node(page, 'data-rfc-pending', section)
                archive = attribute_node(page, 'data-rfc-completed', section)
                archived_rows = attribute_node(page, 'data-rfc-completed-list', archive)
                self.assertNotIn('open', archive['attrs'])
                self.assertNotIn('hidden', archive['attrs'])
                self.assertIn('Decision 0', page.visible_text(pending))
                for index in (1, 2, 3):
                    self.assertNotIn('Decision ' + str(index), page.visible_text(section))
                self.assertEqual(len([n for n in page.elements(archived_rows) if 'data-local-review' in n['attrs']]), 3)
                self.assertEqual(page.visible_text(attribute_node(page, 'data-rfc-pending-count', section)), '1')
                self.assertEqual(page.visible_text(attribute_node(page, 'data-rfc-completed-count', section)), '3')
                self.assertIn('4 eligible', page.visible_text(section))
                archive['attrs']['open'] = ''
                for index in (1, 2, 3):
                    self.assertIn('Decision ' + str(index), page.visible_text(section))
                self.assertIn('Approved by you', page.visible_text(archive))
                self.assertIn('Done locally', page.visible_text(archive))
                if kind == 'tea-time':
                    overview = page.by_id['day-overview']
                    self.assertIn('4 RFCs', page.visible_text(overview))
                    self.assertIn('Decision 0', page.visible_text(overview))
                    for index in (1, 2, 3):
                        self.assertNotIn('Decision ' + str(index), page.visible_text(overview))
                self.assertEqual(data, before)

    def test_empty_pending_and_empty_archive_are_honest(self):
        for approved in (False, True):
            data = snapshot()
            data['rfcs']['items'][0]['user_approved'] = approved
            page = ReportSurface(render(data))
            empty = attribute_node(page, 'data-rfc-empty')
            archive = attribute_node(page, 'data-rfc-completed')
            self.assertEqual('hidden' not in empty['attrs'], approved)
            self.assertEqual('hidden' not in archive['attrs'], approved)

    @unittest.skipUnless(shutil.which('node'), 'Node verifies live save and undo behavior')
    def test_live_completion_ack_failure_undo_source_approval_focus_and_order(self):
        script = r'''
const assert=require('node:assert/strict');
const {mount}=require(process.argv[1]+'/assets/local-review-state.js');
class Element {
  constructor(){this.dataset={};this.children=[];this.listeners={};this.textContent='';this.hidden=false;this.attributes={};}
  addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
  fire(){return Promise.all((this.listeners.click||[]).map(fn=>fn()));}
  setAttribute(key,value){this.attributes[key]=value;}
  dispatchEvent(){}
  focus(){if(!this.disabled)this.focused=true;}
  insertBefore(row,next){if(row.parentElement){const old=row.parentElement.children;old.splice(old.indexOf(row),1);}const index=next?this.children.indexOf(next):this.children.length;this.children.splice(index,0,row);row.parentElement=this;}
}
global.CustomEvent=class{};
const pending=new Element(),completed=new Element(),archive=new Element(),summary=new Element(),empty=new Element(),pendingCount=new Element(),completedCount=new Element(),notice=new Element();
archive.hidden=true;archive.open=false;archive.querySelector=()=>summary;
const section=new Element();section.querySelector=q=>({'[data-rfc-pending]':pending,'[data-rfc-completed-list]':completed,'[data-rfc-completed]':archive,'[data-rfc-pending-count]':pendingCount,'[data-rfc-completed-count]':completedCount,'[data-rfc-empty]':empty,'[data-rfc-group-status]':notice}[q]);
function row(index,approved=false,done=false){const r=new Element();r.dataset={reviewKind:'rfc',reviewUrl:'https://example.com/'+index,reviewOrder:String(index),sourceApproved:String(approved),reviewDone:String(done)};r.button=new Element();r.label=new Element();r.message=new Element();r.closest=()=>section;r.querySelector=q=>q==='[data-review-toggle]'?r.button:q==='.local-review-label'?r.label:r.message;(approved||done?completed:pending).insertBefore(r,null);return r;}
const first=row(0),second=row(1),approved=row(2,true,true);
let resolveRequest;
const config={endpoint:'http://127.0.0.1:8765/review',token:'test'};
const overviewPending=new Element(),overviewCompleted=new Element(),overviewNote=new Element(),preview=new Element();preview.dataset.rfcOverviewUrl=first.dataset.reviewUrl;
const overview=new Element();overview.querySelector=q=>({'[data-rfc-overview-pending]':overviewPending,'[data-rfc-overview-completed]':overviewCompleted,'[data-rfc-overview-note]':overviewNote}[q]);overview.querySelectorAll=()=>[preview];
const doc={getElementById:()=>({querySelector:()=>overview}),querySelector:q=>q==='.review-interaction-data'?{textContent:JSON.stringify(config)}:null,querySelectorAll:()=>[first,second,approved]};
mount(doc,()=>new Promise(resolve=>{resolveRequest=resolve;}));
function ack(r,done){resolveRequest({ok:true,json:async()=>({ok:true,record:{kind:'rfc',url:r.dataset.reviewUrl,done}})});}
(async()=>{
  const before=first.button.fire();assert.deepEqual(pending.children,[first,second]);assert.equal(first.dataset.reviewDone,'false');
  resolveRequest({ok:false,json:async()=>({ok:false,error:'Disk write failed'})});await before;
  assert.deepEqual(pending.children,[first,second]);assert.equal(first.dataset.reviewDone,'false');assert.match(first.message.textContent,/Disk write failed/);
  const save=first.button.fire();ack(first,true);await save;
  assert.deepEqual(pending.children,[second]);assert.deepEqual(completed.children,[first,approved]);assert.equal(pendingCount.textContent,'1');assert.equal(completedCount.textContent,'2');assert.equal(summary.focused,true);assert.equal(archive.hidden,false);assert.match(notice.textContent,/Moved to Approved or done/);assert.equal(preview.hidden,true);assert.equal(overviewPending.textContent,'1');assert.equal(overviewCompleted.textContent,'2');
  archive.open=true;const undo=first.button.fire();assert.equal(first.button.disabled,true);assert.notEqual(first.button.focused,true);ack(first,false);await undo;
  assert.deepEqual(pending.children,[first,second]);assert.deepEqual(completed.children,[approved]);assert.equal(first.button.focused,true);assert.equal(pendingCount.textContent,'2');assert.match(notice.textContent,/Returned to RFCs to review/);assert.equal(preview.hidden,false);assert.equal(overviewPending.textContent,'2');
  const undoApproved=approved.button.fire();ack(approved,false);await undoApproved;
  assert.deepEqual(completed.children,[approved]);assert.equal(approved.dataset.sourceApproved,'true');assert.equal(approved.dataset.reviewDone,'false');assert.equal(completedCount.textContent,'1');
  for(const r of [first,second]){const saving=r.button.fire();ack(r,true);await saving;}
  assert.equal(pending.children.length,0);assert.equal(empty.hidden,false);assert.equal(pendingCount.textContent,'0');assert.equal(completedCount.textContent,'3');
  for(const r of [first,second]){const saving=r.button.fire();ack(r,false);await saving;}
  assert.equal(empty.hidden,true);assert.deepEqual(pending.children,[first,second]);
  // With no source-approved entries, undoing the final done mark removes the disclosure.
  approved.dataset.sourceApproved='false';approved.dataset.reviewDone='true';const finalUndo=approved.button.fire();ack(approved,false);await finalUndo;
  assert.equal(completed.children.length,0);assert.equal(archive.hidden,true);assert.equal(completedCount.textContent,'0');assert.deepEqual(pending.children,[first,second,approved]);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', script, str(SKILL)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
