/* Tree movement and durable acknowledgement contracts; no browser or live task writes. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {moveOrder,moveConfirmed,confirmed,orderedTodos,topology}=require('../assets/local-todo.js');
const id=n=>String(n).repeat(32);
function fixture(){
  return [1,2,3,4,5,6].map(n=>({id:id(n),title:['Alpha','Bravo child','Charlie grandchild','Delta','Echo child','Foxtrot'][n-1],
    parent_id:n===2?id(1):n===3?id(2):n===5?id(4):null,status:'pending',important:false,project_tags:[],created_at:'2026-10-22T09:0'+n+':00Z',updated_at:'2026-10-22T09:0'+n+':00Z'}));
}
const request=(items,n,target,placement)=>({action:'move',id:id(n),target_id:target===null?null:id(target),placement,base_order:topology(items)});
function ack(items,move){
  const expected=moveOrder(items,move),todos=expected.rows.map((row,index)=>expected.changed?{...row,position:index}:row);
  return {ok:true,todos,archive:[],item:{...todos.find(row=>row.id===move.id)},move:{target_id:move.target_id,placement:move.placement,previous_parent_id:expected.previousParent,parent_id:expected.parent}};
}
const ids=rows=>rows.map(row=>Number(row.id[0]));

test('moving a parent after another parent carries its whole subtree',()=>{
  const items=fixture(),before=structuredClone(items),move=request(items,1,4,'after'),result=moveOrder(items,move);
  assert.deepEqual(ids(result.rows),[4,5,1,2,3,6]);assert.equal(result.parent,null);assert.deepEqual(result.movedIds,[id(1),id(2),id(3)]);
  assert.equal(result.rows.find(row=>row.id===id(2)).parent_id,id(1));assert.deepEqual(items,before);
  assert.equal(confirmed(move,ack(items,move),[],items),true);
});

test('inside appends the subtree as last child and after skips the target subtree',()=>{
  const items=fixture();
  const nested=moveOrder(items,request(items,6,1,'inside'));assert.deepEqual(ids(nested.rows),[1,2,3,6,4,5]);assert.equal(nested.parent,id(1));
  const after=moveOrder(items,request(items,6,2,'after'));assert.deepEqual(ids(after.rows),[1,2,3,6,4,5]);assert.equal(after.parent,id(1));
  const deep=moveOrder(items,request(items,1,5,'inside'));assert.deepEqual(ids(deep.rows),[4,5,1,2,3,6]);assert.equal(deep.parent,id(5));
});

test('before/after adopt target parent, root-end unnests without losing descendants',()=>{
  const items=fixture();
  const before=moveOrder(items,request(items,6,2,'before'));assert.deepEqual(ids(before.rows),[1,6,2,3,4,5]);assert.equal(before.parent,id(1));
  const unnested=moveOrder(items,request(items,2,4,'before'));assert.deepEqual(ids(unnested.rows),[1,2,3,4,5,6]);assert.equal(unnested.parent,null);assert.equal(unnested.changed,true);
  const root=moveOrder(items,request(items,2,null,'root-end'));assert.deepEqual(ids(root.rows),[1,4,5,6,2,3]);assert.equal(root.parent,null);assert.equal(root.rows.at(-1).parent_id,id(2));
});

test('self/descendant destinations and malformed root-end targets are rejected',()=>{
  const items=fixture();
  for(const placement of ['before','after','inside']){
    for(const target of [1,2,3])assert.equal(moveOrder(items,request(items,1,target,placement)),null);
  }
  assert.equal(moveOrder(items,request(items,2,3,'inside')),null);
  assert.equal(moveOrder(items,request(items,2,4,'root-end')),null);
  assert.equal(moveOrder(items,request(items,2,null,'before')),null);
  assert.equal(moveOrder(items,request(items,9,4,'before')),null);
});

test('legacy importance promotes groups until manual positions define sibling order',()=>{
  const items=fixture();items[4].important=true;
  assert.deepEqual(ids(orderedTodos(items)),[4,5,1,2,3,6]);
  const manual=[1,2,3,4,5,6].map((n,index)=>({...items.find(row=>row.id===id(n)),position:index}));
  assert.deepEqual(ids(orderedTodos(manual)),[1,2,3,4,5,6]);
  manual[5].important=true;assert.deepEqual(ids(orderedTodos(manual,new Set([id(6)]))),[1,2,3,4,5,6]);
});

test('no-op moves retain the existing legacy or manual positions unchanged',()=>{
  const items=fixture(),move=request(items,6,null,'root-end'),result=moveOrder(items,move);
  assert.equal(result.changed,false);assert.equal(confirmed(move,ack(items,move),[],items),true);
  const migrated=ack(items,move);migrated.todos=migrated.todos.map((row,index)=>({...row,position:index}));migrated.item=migrated.todos.at(-1);
  assert.equal(confirmed(move,migrated,[],items),false,'a no-op cannot silently switch the ordering model');
  const manual=items.map((row,index)=>({...row,position:index})),manualMove=request(manual,2,1,'inside');
  assert.equal(moveOrder(manual,manualMove).changed,false);assert.equal(confirmed(manualMove,ack(manual,manualMove),[],manual),true);
});

test('filtered views still submit every active task in the base topology',()=>{
  const items=fixture();items[3].status='completed';items[5].project_tags=['Other project'];
  const move=request(items,2,null,'root-end');assert.equal(move.base_order.length,6);assert.ok(move.base_order.some(row=>row[0]===id(4)));
  const partial={...move,base_order:move.base_order.filter(row=>row[0]!==id(4))};
  assert.equal(confirmed(partial,ack(items,move),[],items),false);
  assert.equal(confirmed(move,ack(items,move),[],items),true);
});

test('acknowledgement rejects arbitrary topology, missing/extra tasks, wrong ranks and echoes',()=>{
  const items=fixture(),move=request(items,2,null,'root-end');
  const mutate=[
    result=>{result.todos=result.todos.slice(1);},
    result=>{result.todos.push({...items[0],id:id(9),position:6});},
    result=>{result.todos.find(row=>row.id===id(3)).parent_id=null;},
    result=>{result.todos.find(row=>row.id===id(4)).position=50;},
    result=>{result.todos.find(row=>row.id===id(4)).position=0;},
    result=>{result.move.parent_id=id(1);},
    result=>{result.move.placement='before';},
    result=>{result.move.previous_parent_id=null;},
    result=>{result.item={...result.item,title:'Wrong echoed item'};},
    result=>{result.todos.find(row=>row.id===id(4)).status='unknown';},
    result=>{result.todos[0].position=1.5;}
  ];
  for(const change of mutate){const result=ack(items,move);change(result);assert.equal(confirmed(move,result,[],items),false,change.toString());}
  assert.equal(confirmed(move,{ok:true,todos:items,item:items[1]},[],items),false);
});

test('concurrent unrelated field edits are authoritative after the exact move is confirmed',()=>{
  const items=fixture(),move=request(items,2,null,'root-end'),result=ack(items,move);
  Object.assign(result.todos.find(row=>row.id===id(4)),{title:'Renamed in another tab',status:'completed',important:true,project_tags:['New project'],updated_at:'2026-10-22T10:00:00Z'});
  Object.assign(result.todos.find(row=>row.id===id(2)),{title:'Mover renamed elsewhere',updated_at:'2026-10-22T10:01:00Z'});
  const saved=result.todos.find(row=>row.id===id(2));
  result.item=Object.fromEntries(Object.entries(saved).reverse());
  assert.equal(moveConfirmed(move,result,items),true);assert.equal(confirmed(move,result,[],items),true,'JSON key ordering does not affect acknowledgement');
  const changedParent={...move,base_order:move.base_order.map(row=>row[0]===id(2)?[id(2),null]:row)};
  assert.equal(confirmed(changedParent,result,[],items),false);
});
