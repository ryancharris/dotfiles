const assert = require('node:assert/strict');
const {test} = require('node:test');
const {captureDisclosures,restoreDisclosures} = require('../assets/workspace.js');

function details(id,open,label='Evidence & context',section='daily-priorities') {
  return {id,open,closest:()=>({id:section}),querySelector:()=>({textContent:label})};
}
const documentFor=nodes=>({querySelectorAll:selector=>{assert.equal(selector,'details');return nodes;}});

test('stable disclosure identities preserve open and closed choices across source reorder and label changes',()=>{
  const previous=[details('priority-evidence-first',true),details('priority-evidence-second',false),details('yesterday-coverage',false,'Activity coverage')];
  const next=[details('priority-evidence-second',true),details('priority-evidence-new',false),details('priority-evidence-first',false,'Fresh evidence'),details('yesterday-coverage',true,'Updated activity coverage')];
  restoreDisclosures(documentFor(next),captureDisclosures(documentFor(previous)));
  assert.deepEqual(next.map(node=>node.open),[false,false,true,false]);
});

test('ambiguous legacy labels never expand unrelated disclosures',()=>{
  const previous=[details('',true),details('',false)];
  const next=[details('',false),details('',false)];
  restoreDisclosures(documentFor(next),captureDisclosures(documentFor(previous)));
  assert.deepEqual(next.map(node=>node.open),[false,false]);
});

test('legacy fallback preserves unique disclosure choices only when unique in both views',()=>{
  const previous=[details('',true,'Activity coverage','yesterday'),details('',false,'Queue coverage','reviews')];
  const next=[details('',false,'Activity coverage','yesterday'),details('',true,'Queue coverage','reviews')];
  restoreDisclosures(documentFor(next),captureDisclosures(documentFor(previous)));
  assert.deepEqual(next.map(node=>node.open),[true,false]);
  const duplicateNext=[details('',false,'Activity coverage','yesterday'),details('',false,'Activity coverage','yesterday')];
  restoreDisclosures(documentFor(duplicateNext),captureDisclosures(documentFor(previous)));
  assert.deepEqual(duplicateNext.map(node=>node.open),[false,false]);
});
