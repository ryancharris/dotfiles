/* Local pointer interaction contract; no browser package or provider connection needed. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const api=require('../assets/day-calendar.js');

class Element {
  constructor(){
    this.listeners={};this.dataset={};this.style={};this.classes=new Set();this.children=[];
    this.attributes={};this.value='';this.textContent='';this.hidden=false;
    this.classList={add:(...names)=>names.forEach(n=>this.classes.add(n)),remove:(...names)=>names.forEach(n=>this.classes.delete(n)),toggle:(n,on)=>on?this.classes.add(n):this.classes.delete(n)};
  }
  addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
  fire(type,props={}){const event={type,target:this,preventDefault(){},...props};for(const listener of this.listeners[type]||[])listener(event);}
  setAttribute(name,value){this.attributes[name]=value;}
  setPointerCapture(id){this.capture=id;}
  hasPointerCapture(id){return this.capture===id;}
  releasePointerCapture(id){this.capture=null;this.fire('lostpointercapture',{pointerId:id});}
  appendChild(child){this.children.push(child);child.parent=this;return child;}
  querySelector(name){return this.children.find(c=>c.tagName===name);}
  remove(){this.parent.children.splice(this.parent.children.indexOf(this),1);}
}

function fixture({compact=false}={}){
  const data={start:0,end:1440,now:540,verified:true,fixed:[
    {start:660,end:690,free:true}, {start:720,end:750,anonymous:true}],blocks:[
    {kind:'focus',label:'Focus',minutes:120,start:null,min_start:540,max_end:1020},
    {kind:'dog_walk',label:'Dog walk',minutes:30,start:null,min_start:0,max_end:1440},
    {kind:'lunch',label:'Lunch',minutes:30,start:780,min_start:540,max_end:1020}]};
  if(compact){data.view_start=510;data.view_end=1020;}
  const lower=data.view_start??data.start,span=(data.view_end??data.end)-lower;
  const controls={},buttons={},warning=new Element(),reset=new Element(),lane=new Element(),scroll=new Element();
  let changes=0,frame=null;
  scroll.scrollTop=compact?0:400;
  scroll.getBoundingClientRect=()=>({left:0,right:400,top:100,bottom:500,width:400,height:400});
  lane.getBoundingClientRect=()=>({left:200,right:400,top:100-scroll.scrollTop,bottom:100+span-scroll.scrollTop,width:200,height:span});
  const doc={createElement:tag=>Object.assign(new Element(),{tagName:tag}),defaultView:{requestAnimationFrame:callback=>{frame=callback;return 1;},cancelAnimationFrame:()=>{frame=null;}}};
  data.blocks.forEach(block=>{
    const button=new Element();button.dataset.kind=block.kind;button.appendChild(doc.createElement('span'));buttons[block.kind]=button;
    const control=new Element();control.dataset.kind=block.kind;
    control.input=new Element();control.place=new Element();control.removeButton=new Element();
    control.duration=block.kind==='focus'?new Element():null;control.summary=new Element();
    control.name=block.kind==='focus'?new Element():null;control.label=new Element();
    control.querySelector=name=>name==='input'?control.input:name==='[data-place]'?control.place:name==='[data-remove]'?control.removeButton:name==='[data-duration]'?control.duration:name==='[data-duration-summary]'?control.summary:name==='[data-focus-name]'?control.name:name==='[data-block-label]'?control.label:null;
    controls[block.kind]=control;
  });
  lane.querySelector=selector=>buttons[selector.match(/data-kind="([^"]+)"/)[1]];
  lane.querySelectorAll=()=>Object.values(buttons);
  const root={dataset:{},ownerDocument:doc,dispatchEvent:()=>changes++,querySelectorAll:()=>Object.values(controls),querySelector:selector=>{
    const elements={'.day-calendar-data':{textContent:JSON.stringify(data)},'.day-plan-lane':lane,'.day-warning':warning,'.day-reset':reset,'.day-scroll':scroll};
    return elements[selector]||controls[selector.match(/data-kind="([^"]+)"/)?.[1]]||null;
  }};
  api.mount(root);
  const get=kind=>root.getDayPlan().blocks.find(b=>b.kind===kind).start;
  const point=(minute,x=300)=>({button:0,pointerId:1,clientX:x,clientY:100-scroll.scrollTop+minute-lower});
  const source=kind=>controls[kind].place;
  const start=(kind,minute=540)=>{source(kind).fire('pointerdown',point(minute,100));source(kind).fire('pointermove',point(minute));};
  const drop=(kind,minute,x=300)=>source(kind).fire('pointerup',point(minute,x));
  return {data,root,get,point,source,start,drop,controls,buttons,lane,scroll,warning,reset,changes:()=>changes,frame:timestamp=>frame?.(timestamp)};
}

test('unplaced source previews without selecting until a valid plan-lane drop',()=>{
  const f=fixture(),changes=f.changes();f.start('focus',540);
  assert.equal(f.get('focus'),null);assert.equal(f.controls.focus.input.value,'');assert.equal(f.changes(),changes);
  assert.equal(f.lane.children.length,1);assert.equal(f.lane.classes.has('day-drop-valid'),true);
  assert.match(f.warning.textContent,/Release to place Focus at 09:00/);
  f.drop('focus',540);assert.equal(f.get('focus'),540);assert.equal(f.lane.children.length,0);assert.equal(f.changes(),changes+1);
  f.source('focus').fire('click',{detail:1});assert.equal(f.get('focus'),540); // Browser's post-drag click cannot auto-place.
  assert.equal(f.data.blocks[0].start,null);
});

test('transparent events, anonymous intervals, other plans and block windows reject drops',()=>{
  for(const minute of [660,720,780,510,1020]){
    const f=fixture();f.scroll.scrollTop=minute-100;f.start('dog_walk',minute);
    if(minute===510 || minute===1020){f.source('dog_walk').fire('pointercancel',{pointerId:1});f.start('focus',minute);f.drop('focus',minute);assert.equal(f.get('focus'),null);}
    else {f.drop('dog_walk',minute);assert.equal(f.get('dog_walk'),null);}
    assert.match(f.warning.textContent,/Drop rejected/);
  }
});

test('moving a placed block uses grab offset and current scroll geometry',()=>{
  const f=fixture();f.start('dog_walk',540);f.drop('dog_walk',540);
  const button=f.buttons.dog_walk;
  button.fire('pointerdown',f.point(550));button.fire('pointermove',f.point(610));
  assert.equal(f.get('dog_walk'),540);
  f.scroll.scrollTop+=30; // Pointer stays still; the content moved under it.
  f.scroll.fire('scroll');button.fire('pointerup',f.point(640));
  assert.equal(f.get('dog_walk'),630);
});

test('outside lane, cancel, lost capture, Escape and locking all preserve the prior state',()=>{
  for(const end of ['outside','pointercancel','lostpointercapture','Escape','lock']){
    const f=fixture();f.start('dog_walk',540);f.drop('dog_walk',540);
    const button=f.buttons.dog_walk;
    button.fire('pointerdown',f.point(540));button.fire('pointermove',f.point(600));
    if(end==='outside')button.fire('pointerup',f.point(600,150));
    else if(end==='Escape')button.fire('keydown',{key:'Escape'});
    else if(end==='lock')f.root.dayPlanner.setLocked(true);
    else button.fire(end,{pointerId:1});
    assert.equal(f.get('dog_walk'),540,end);assert.equal(f.lane.children.length,0,end);
    assert.equal(f.lane.classes.has('day-drop-active'),false,end);
  }
});

test('edge dragging scrolls the full-day viewport and keeps preview time in sync',()=>{
  const f=fixture();f.start('dog_walk',780);const previous=f.scroll.scrollTop;
  f.frame(16);assert.ok(f.scroll.scrollTop>previous);
  assert.equal(f.get('dog_walk'),null); // Autoscroll cannot submit a choice.
  f.source('dog_walk').fire('pointercancel',{pointerId:1});const stopped=f.scroll.scrollTop;
  f.frame(32);assert.equal(f.scroll.scrollTop,stopped);
});

test('keyboard Place, arrow movement, strict HH:MM edits and reset remain available',()=>{
  const f=fixture();f.source('dog_walk').fire('click',{detail:0});assert.equal(f.get('dog_walk'),540);
  f.buttons.dog_walk.fire('keydown',{key:'ArrowDown'});assert.equal(f.get('dog_walk'),555);
  const input=f.controls.dog_walk.input;
  for(const invalid of ['9:30','09:90','24:00','12:99','12:00 PM']){input.value=invalid;input.fire('change');assert.equal(f.get('dog_walk'),555);assert.match(f.warning.textContent,/HH:MM/);}
  input.value='00:00';input.fire('change');assert.equal(f.get('dog_walk'),0);
  input.value='23:30';input.fire('change');assert.equal(f.get('dog_walk'),1410);
  input.value='';input.fire('change');assert.equal(f.get('dog_walk'),null);
  f.reset.fire('click');assert.equal(f.get('lunch'),null);assert.match(f.warning.textContent,/All blocks unplaced/);
});

test('a drag cancellation does not eat the next keyboard Place action',()=>{
  const f=fixture();f.start('dog_walk',540);f.source('dog_walk').fire('pointercancel',{pointerId:1});
  f.source('dog_walk').fire('click',{detail:0});assert.equal(f.get('dog_walk'),540);
});

test('compact 08:30–17:00 lane maps drag geometry without changing full-day saved bounds',()=>{
  const f=fixture({compact:true});f.start('focus',540);f.drop('focus',540);
  assert.equal(f.get('focus'),540);assert.equal(f.buttons.focus.style.top,(30/510*100)+'%');
  const input=f.controls.dog_walk.input;input.value='19:00';input.fire('change');
  assert.equal(f.get('dog_walk'),1140,'manual time preserves valid full-day choice');assert.equal(f.buttons.dog_walk.hidden,true);
  input.value='';input.fire('change');f.scroll.scrollTop=100;f.start('dog_walk',1005);f.drop('dog_walk',1005);
  assert.equal(f.get('dog_walk'),null,'drag cannot extend beyond the visible 17:00 boundary');
  f.start('dog_walk',990);f.drop('dog_walk',990);assert.equal(f.get('dog_walk'),990);
});

test('restoring an edit baseline discards movement and drag previews without mutating the baseline',()=>{
  const f=fixture(),baseline=f.root.dayPlanner.getState();
  f.source('dog_walk').fire('click',{detail:0});assert.equal(f.get('dog_walk'),540);
  f.root.dayPlanner.setLocked(true);assert.equal(f.root.dayPlanner.restoreState(baseline),false);
  assert.equal(f.get('dog_walk'),540);f.root.dayPlanner.setLocked(false);
  f.buttons.dog_walk.fire('pointerdown',f.point(540));f.buttons.dog_walk.fire('pointermove',f.point(600));
  assert.equal(f.lane.children.length,1);
  assert.equal(f.root.dayPlanner.restoreState(baseline),true);
  assert.equal(f.lane.children.length,0);assert.equal(f.get('dog_walk'),null);assert.equal(f.get('lunch'),780);
  assert.deepEqual(f.root.getDayPlan().blocks,baseline.blocks);assert.match(f.warning.textContent,/Draft changes discarded/);
  f.controls.lunch.input.value='14:00';f.controls.lunch.input.fire('change');
  assert.equal(baseline.blocks.find(block=>block.kind==='lunch').start,780,'restoration copies the saved baseline');
});

function resize(f,minutes){f.controls.focus.duration.value=String(minutes);f.controls.focus.duration.fire('change');}
const focus=f=>f.root.getDayPlan().blocks.find(b=>b.kind==='focus');

test('focus duration edits affect placement, drag, labels and edit cancellation',()=>{
  const f=fixture(),baseline=f.root.getDayPlan();
  assert.equal(f.controls.focus.duration.value,'120');
  resize(f,45);assert.equal(focus(f).minutes,45);assert.equal(focus(f).start,null);
  assert.equal(f.controls.focus.summary.textContent,'45m');
  f.start('focus',600);f.drop('focus',600);assert.equal(focus(f).start,600);
  assert.equal(f.buttons.focus.children[0].textContent,'10:00–10:45');
  resize(f,60);assert.equal(focus(f).minutes,60,'touching free event allowed');
  resize(f,75);assert.equal(focus(f).minutes,60,'extension into transparent event rejected');
  assert.equal(f.controls.focus.duration.value,'60');assert.match(f.warning.textContent,/overlaps/);
  f.root.dayPlanner.restoreState(baseline);assert.equal(focus(f).minutes,120);assert.equal(focus(f).start,null);
  assert.equal(f.controls.focus.duration.value,'120');assert.equal(f.controls.focus.summary.textContent,'120m');
});

test('focus duration rejects invalid lengths, own-plan conflicts and planning boundaries',()=>{
  const f=fixture();
  for(const value of ['',0,-15,16,22.5,NaN,Infinity,495]){resize(f,value);assert.equal(focus(f).minutes,120);assert.equal(f.controls.focus.duration.value,'120');}
  resize(f,15);f.controls.focus.input.value='12:45';f.controls.focus.input.fire('change');
  assert.equal(focus(f).start,765);resize(f,30);assert.equal(focus(f).minutes,15,'lunch starts at 13:00');
  f.controls.focus.input.value='16:45';f.controls.focus.input.fire('change');resize(f,30);
  assert.equal(focus(f).minutes,15,'cannot extend past window');
  f.root.dayPlanner.setLocked(true);assert.equal(f.controls.focus.duration.disabled,true);
  resize(f,45);assert.equal(focus(f).minutes,15);assert.equal(f.controls.focus.duration.value,'15');
  f.root.dayPlanner.setLocked(false);assert.equal(f.controls.focus.duration.disabled,false);
  f.reset.fire('click');assert.equal(focus(f).minutes,120);
  resize(f,480);assert.equal(focus(f).minutes,480,'unplaced length can span the checked window');
  f.controls.focus.place.fire('click');assert.equal(focus(f).start,null,'full window still cannot overlap events');
});

function rename(f,name){f.controls.focus.name.value=name;f.controls.focus.name.fire('change');}

test('optional focus names survive dragging, placement, cancellation, and clearing',()=>{
  const f=fixture();
  rename(f,'  Review <SQL> & "migration"  ');
  assert.equal(focus(f).name,'Review <SQL> & "migration"');
  assert.equal(f.controls.focus.label.textContent,'🔎 Review <SQL> & "migration"');
  assert.match(f.controls.focus.place.attributes['aria-label'],/Review <SQL>/);
  resize(f,45);f.start('focus',600);f.drop('focus',600);
  assert.equal(focus(f).start,600);assert.equal(focus(f).name,'Review <SQL> & "migration"');
  assert.equal(f.buttons.focus.attributes['aria-label'],'🔎 Review <SQL> & "migration", 10:00 to 10:45. Arrow keys move 15 minutes.');
  const baseline=f.root.getDayPlan();
  rename(f,'Another project');f.root.dayPlanner.restoreState(baseline);
  assert.equal(focus(f).name,'Review <SQL> & "migration"');
  assert.equal(f.controls.focus.name.value,'Review <SQL> & "migration"');
  f.controls.focus.removeButton.fire('click');assert.equal(focus(f).name,'Review <SQL> & "migration"');
  rename(f,'   ');assert.equal('name' in focus(f),false);assert.equal(focus(f).label,'🔎 Focus');
  f.root.dayPlanner.restoreState(baseline);assert.equal(focus(f).name,'Review <SQL> & "migration"');
  f.reset.fire('click');assert.equal('name' in focus(f),false);assert.equal(f.controls.focus.name.value,'');
});

test('focus names reject oversized/control text, stay locked during saves, and restore a blank baseline',()=>{
  const f=fixture(),baseline=f.root.getDayPlan();
  rename(f,'Project');
  for(const invalid of ['x'.repeat(121),'two\nlines','bad\u0000','\ud800']){
    rename(f,invalid);assert.equal(focus(f).name,'Project');assert.equal(f.controls.focus.name.value,'Project');
  }
  assert.equal(api.focusName('🔎'.repeat(120)),'🔎'.repeat(120));
  assert.throws(()=>api.focusName(null),/plain-text/);
  f.root.dayPlanner.setLocked(true);assert.equal(f.controls.focus.name.disabled,true);
  rename(f,'Should not save');assert.equal(focus(f).name,'Project');assert.equal(f.controls.focus.name.value,'Project');
  f.root.dayPlanner.setLocked(false);assert.equal(f.controls.focus.name.disabled,false);
  f.root.dayPlanner.restoreState(baseline);assert.equal('name' in focus(f),false);assert.equal(f.controls.focus.name.value,'');
});
