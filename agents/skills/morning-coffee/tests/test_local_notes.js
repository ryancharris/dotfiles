const assert=require('node:assert/strict');
const {mount}=require('../assets/local-notes.js');
global.window={addEventListener(){}};
function element(value=''){return {value,hidden:true,listeners:{},addEventListener(name,fn){this.listeners[name]=fn;}};}
function fixture(){
 const input=element(''),status=element(),retry=element(),timers=new Map();let id=0;
 const section={querySelector(selector){return selector==='textarea'?input:selector==='[role=status]'?status:retry;}};
 const config={notes:{text:'',revision:0},endpoint:'http://127.0.0.1:1234/notes',token:'private',timezone:'America/Toronto'};
 const timer={set(fn,ms){assert.equal(ms,500);timers.set(++id,fn);return id;},clear(key){timers.delete(key);}};
 const tick=()=>{const tasks=[...timers.values()];timers.clear();tasks.forEach(fn=>fn());};
 return {input,status,retry,section,config,timer,tick,timers};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const f=fixture(),calls=[];let respond;
 const ui=mount(f.section,f.config,(_,options)=>{calls.push(options);return new Promise(resolve=>respond=resolve);},f.timer);
 f.input.value='first';f.input.listeners.input();f.input.value='second';f.input.listeners.input();
 assert.equal(calls.length,0);assert.equal(f.timers.size,1);f.tick();
 assert.equal(calls.length,1);assert.deepEqual(JSON.parse(calls[0].body),{text:'second',revision:0});assert.equal(calls[0].headers['X-Brief-Token'],'private');
 f.input.value='typed while saving';f.input.listeners.input();f.tick();assert.equal(calls.length,1);
 respond({ok:true,status:200,json:async()=>({ok:true,notes:{text:'second',revision:1,updated_at:'2026-10-20T18:05:00+00:00'}})});await settle();
 assert.equal(f.input.value,'typed while saving');assert.equal(f.timers.size,1);f.tick();assert.equal(calls.length,2);
 assert.deepEqual(JSON.parse(calls[1].body),{text:'typed while saving',revision:1});
 respond({ok:false,status:500,json:async()=>({error:'Disk unavailable'})});await settle();
 assert.equal(f.input.value,'typed while saving');assert.match(f.status.textContent,/Disk unavailable/);assert.equal(f.retry.hidden,false);assert.equal(f.timers.size,0);
 const retry=f.retry.listeners.click();assert.equal(calls.length,3);
 respond({ok:true,status:200,json:async()=>({ok:true,notes:{text:'wrong draft',revision:2,updated_at:'2026-10-20T18:05:00+00:00'}})});await retry;
 assert.match(f.status.textContent,/did not confirm/);assert.equal(f.input.value,'typed while saving');
 const saved=ui.persist();respond({ok:true,status:200,json:async()=>({ok:true,notes:{text:'typed while saving',revision:2,updated_at:'2026-10-20T18:05:00+00:00'}})});await saved;
 assert.match(f.status.textContent,/14:05/);assert.doesNotMatch(f.status.textContent,/AM|PM/);
 f.input.value='';f.input.listeners.input();const clearing=ui.persist();
 assert.deepEqual(JSON.parse(calls.at(-1).body),{text:'',revision:2});
 respond({ok:false,status:409,json:async()=>({error:'Notes changed in another page. Copy your draft before reloading.'})});await clearing;
 assert.equal(f.input.value,'');assert.match(f.status.textContent,/another page/);assert.equal(f.retry.hidden,true);
 const count=calls.length;f.input.value='keep conflict draft';f.input.listeners.input();f.tick();await ui.persist();assert.equal(calls.length,count);assert.equal(f.input.value,'keep conflict draft');
 const archived=fixture();mount(archived.section,{notes:archived.config.notes},()=>{throw Error('Archived notes must not save');},archived.timer);assert.equal(archived.input.readOnly,true);
})().catch(error=>{console.error(error);process.exit(1);});
