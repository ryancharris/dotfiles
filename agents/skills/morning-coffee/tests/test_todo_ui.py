"""Widget shows local work honestly and confirms mutations before changing state."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from todo_state import render_todos
from test_report_history import ReportSurface

SKILL = Path(__file__).resolve().parents[1]


class TodoUiTests(unittest.TestCase):
    def fixture(self, live=False):
        todos = [{'id': str(index) * 32, 'title': title, 'status': status, 'due_date': due, 'important': False}
                 for index, title, status, due in [(1, 'Old task', 'pending', '2026-10-19'),
                      (2, 'Current <task>', 'pending', '2026-10-20'),
                      (3, 'Next task', 'pending', '2026-10-21'),
                      (4, 'Completed task', 'completed', '2026-10-19'),
                      (5, 'Cancelled task', 'cancelled', '2026-10-20')]]
        data = {'report': {'date': '2026-10-20'}, 'todos': todos}
        if live:
            data['todo_interaction'] = {'endpoint': 'http://127.0.0.1:1234/todo', 'token': 'safe</script>token'}
        return data

    def test_archive_lists_every_status_and_future_item_with_disabled_mutations(self):
        data = self.fixture()
        before = deepcopy(data)
        page = render_todos(data)
        surface = ReportSurface(page)
        rows = [node for node in surface.elements() if 'data-todo-id' in node['attrs']]
        self.assertEqual(len(rows), 5)
        self.assertEqual({node['attrs']['data-todo-group'] for node in rows}, {'overdue', 'today', 'upcoming', 'completed', 'cancelled'})
        buttons = [node for node in surface.elements() if node['tag'] == 'button']
        self.assertTrue(buttons)
        self.assertTrue(all('disabled' in node['attrs'] for node in buttons))
        self.assertIn('1 overdue · 1 due today · 1 upcoming', surface.visible_text())
        self.assertIn('Current &lt;task&gt;', page)
        self.assertEqual(data, before)

    def test_live_configuration_is_safe_json_and_all_actions_are_accessible(self):
        data = self.fixture(live=True)
        page = render_todos(data)
        surface = ReportSurface(page)
        config = json.loads(surface.by_id['todo-config']['children'][0])
        self.assertEqual({item['id']: item for item in config['todos']}, {item['id']: item for item in data['todos']})
        self.assertEqual(config['today'], '2026-10-20')
        self.assertEqual(config['token'], data['todo_interaction']['token'])
        self.assertNotIn('safe</script>token', page)
        buttons = [node for node in surface.elements() if node['tag'] == 'button']
        self.assertTrue(all('disabled' not in node['attrs'] for node in buttons))
        actions = {node['attrs']['data-todo-action'] for node in buttons if 'data-todo-action' in node['attrs']}
        self.assertEqual(actions, {'complete', 'cancel', 'reopen', 'remove', 'subtask', 'set_importance'})
        self.assertTrue(any('data-todo-reschedule' in node['attrs'] for node in surface.elements()))

    def test_nested_items_render_inside_parent_lists_with_independent_labels(self):
        data = self.fixture()
        data['todos'][0]['parent_id'] = data['todos'][2]['id']
        data['todos'][1]['parent_id'] = data['todos'][0]['id']
        page = render_todos(data)
        surface = ReportSurface(page)
        by_id = {node['attrs']['data-todo-id']: node for node in surface.elements() if 'data-todo-id' in node['attrs']}
        nested_parent = by_id[data['todos'][2]['id']]
        nested_ids = {node['attrs']['data-todo-id'] for node in surface.elements(nested_parent) if 'data-todo-id' in node['attrs']}
        self.assertTrue({data['todos'][0]['id'], data['todos'][1]['id']}.issubset(nested_ids))

    def test_static_starred_descendant_promotes_parent_group_and_accessible_controls(self):
        data = self.fixture(live=True)
        data['todos'][1]['parent_id'] = data['todos'][2]['id']
        data['todos'][1]['important'] = True
        surface = ReportSurface(render_todos(data))
        rows = [node for node in surface.elements() if 'data-todo-id' in node['attrs']]
        self.assertEqual([node['attrs']['data-todo-id'] for node in rows[:2]], [data['todos'][2]['id'], data['todos'][1]['id']])
        self.assertEqual(rows[0]['attrs']['data-todo-important'], 'false')
        self.assertEqual(rows[1]['attrs']['data-todo-important'], 'true')
        starred = next(node for node in surface.elements(rows[1]) if node['attrs'].get('class') == 'todo-star')
        self.assertEqual(starred['attrs']['aria-pressed'], 'true')
        self.assertEqual(starred['attrs']['aria-label'], 'Remove high importance')
        self.assertEqual(starred['attrs']['title'], 'Remove high importance')

    @unittest.skipUnless(shutil.which('node'), 'Node needed for task interactions')
    def test_pending_failed_acknowledged_actions_and_filters(self):
        script = r'''
const assert=require('node:assert/strict');
const {mount,confirmed,summarize,orderedTodos}=require(process.argv[1]+'/assets/local-todo.js');
class Element {
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.listeners={};this.dataset={};this.value='';this.textContent='';this.disabled=false;this.hidden=false;this.className='';}
 append(...children){for(const child of children){child.parent=this;this.children.push(child);}}
 replaceChildren(...children){this.children=[];this.append(...children);}
 addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
 setAttribute(name,value){this[name]=value;}
 fire(type,event={}){return Promise.all((this.listeners[type]||[]).map(fn=>fn({preventDefault(){},target:this,...event})));}
 matches(selector){
  if(selector.includes(','))return selector.split(',').some(s=>this.matches(s));
  if(selector.includes(' ')){const [parent,child]=selector.split(' ');return this.matches(child)&&Boolean(this.parent?.closest(parent));}
  if(selector.startsWith('.'))return this.className.split(' ').includes(selector.slice(1));
  if(selector.startsWith('#'))return this.id===selector.slice(1);
  if(selector.startsWith('[')){const match=selector.match(/^\[([^=\]]+)(?:=([^\]]+))?\]$/);const key=match[1].replace(/^data-/, '').replace(/-([a-z])/g,(_,c)=>c.toUpperCase());const value=match[1].startsWith('data-')?this.dataset[key]:this[match[1]];return match[2]!==undefined?value===match[2].replace(/^"|"$/g,''):value!==undefined;}
  return this.tagName===selector.toUpperCase();
 }
 querySelectorAll(selector){return this.children.flatMap(child=>[...(child.matches(selector)?[child]:[]),...child.querySelectorAll(selector)]);}
 querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
 closest(selector){return this.matches(selector)?this:this.parent?.closest(selector);}
 contains(node){return node===this || this.children.some(child=>child.contains(node));}
 focus(){this.focused=true;}
 dispatchEvent(event){this.lastEvent=event;}
}
global.CustomEvent=class {constructor(type,options){this.type=type;Object.assign(this,options);}};
function fixture(live=true){
 const section=new Element('section');section.id='todos';
 const doc=new Element();doc.createElement=tag=>new Element(tag);doc.createTextNode=text=>{const e=new Element('#text');e.textContent=text;return e;};doc.append(section);
 const context=new Element('p');context.className='todo-add-context';context.hidden=true;const contextText=new Element('span'),rootButton=new Element('button');rootButton.dataset.todoRoot='';context.append(contextText,rootButton);section.append(context);
 const config=new Element('script');config.id='todo-config';
 const initial={id:'1'.repeat(32),title:'Today task',status:'pending',due_date:'2026-10-20'};
 config.textContent=JSON.stringify({today:'2026-10-20',todos:[initial],...(live?{endpoint:'http://127.0.0.1:1234/todo',token:'token'}:{})});
 const nodes={};for(const name of ['todo-status','todo-list','todo-empty','todo-counts']){nodes[name]=new Element(name==='todo-list'?'ul':'p');nodes[name].className=name;section.append(nodes[name]);}
 const filter=new Element('select');filter.id='todo-filter';filter.value='all';section.append(filter);
 const add=new Element('form');add.className='todo-add';const title=new Element('input');title.name='title';const due=new Element('input');due.name='due_date';due.value='2026-10-20';const button=new Element('button');add.append(title,due,button);section.append(add,config);
 return {doc,section,nodes,filter,add,title,due,initial,config,context};
}
(async()=>{
 const f=fixture();let resolve,calls=[];
 mount(f.doc,(endpoint,options)=>{calls.push({endpoint,options});return new Promise(r=>{resolve=r;});});
 const row=()=>f.nodes['todo-list'].children[0];
 assert.equal(f.filter.value,'due');assert.equal(row().hidden,false);assert.match(f.nodes['todo-counts'].textContent,/1 due today/);
 const old=row(),complete=old.querySelector('[data-todo-action=complete]');
 const pending=f.nodes['todo-list'].fire('click',{target:complete});
 assert.equal(row(),old);assert.equal(row().dataset.todoGroup,'today');assert.equal(complete.disabled,true);
 assert.deepEqual(JSON.parse(calls[0].options.body),{action:'complete',id:f.initial.id});assert.equal(calls[0].options.headers['X-Brief-Token'],'token');
 resolve({ok:false,json:async()=>({ok:false,error:'Disk write failed'})});await pending;
 assert.equal(row().dataset.todoGroup,'today');assert.match(f.nodes['todo-status'].textContent,/Disk write failed/);
 const success=f.nodes['todo-list'].fire('click',{target:row().querySelector('[data-todo-action=complete]')});
 const completed={...f.initial,status:'completed'};resolve({ok:true,json:async()=>({ok:true,item:completed,todos:[completed]})});await success;
 assert.equal(row().dataset.todoGroup,'completed');assert.equal(row().hidden,true);assert.match(f.nodes['todo-counts'].textContent,/0 due today/);
 f.filter.value='completed';await f.filter.fire('change');assert.equal(row().hidden,false);
 const reopen=f.nodes['todo-list'].fire('click',{target:row().querySelector('[data-todo-action=reopen]')});
 resolve({ok:true,json:async()=>({ok:true,item:{...f.initial,id:'2'.repeat(32)},todos:[f.initial]})});await reopen;
 assert.equal(row().dataset.todoGroup,'completed');assert.match(f.nodes['todo-status'].textContent,/did not confirm/);
 const cancelled={...f.initial,status:'cancelled'};assert.equal(confirmed({action:'cancel',id:f.initial.id},{ok:true,item:cancelled,todos:[cancelled]}),true);
 assert.equal(confirmed({action:'remove',id:f.initial.id},{ok:true,item:{...f.initial,status:'removed'},todos:[]}),true);
 assert.equal(confirmed({action:'remove',id:f.initial.id},{ok:true,item:{...f.initial,status:'removed'},todos:[f.initial]}),false);
 assert.equal(confirmed({action:'reschedule',id:f.initial.id,due_date:'2026-10-23'},{ok:true,item:{...f.initial,due_date:'2026-10-23'},todos:[{...f.initial,due_date:'2026-10-23'}]}),true);
 assert.deepEqual(summarize([f.initial,{...f.initial,id:'2'.repeat(32),due_date:'2026-10-19'},{...f.initial,id:'3'.repeat(32),due_date:'2026-10-21'},completed,cancelled],'2026-10-20'),{today:1,overdue:1,upcoming:1});
 f.title.value='Added task';const added={...f.initial,id:'4'.repeat(32),title:'Added task'};
 const adding=f.add.fire('submit');assert.equal(f.nodes['todo-list'].children.length,1);
 resolve({ok:true,json:async()=>({ok:true,item:added,todos:[completed,added]})});await adding;
 assert.equal(f.nodes['todo-list'].children.length,2);assert.equal(f.title.value,'');assert.equal(f.title.focused,true);
 const archive=fixture(false);let archiveCalls=0;mount(archive.doc,()=>{archiveCalls++;});
 assert.equal(archive.title.disabled,true);await archive.add.fire('submit');assert.equal(archiveCalls,0);
 const nested=fixture();const parent={...nested.initial,title:'Future parent',due_date:'2026-10-25'},child={...nested.initial,id:'2'.repeat(32),title:'Due child',parent_id:parent.id},grandchild={...nested.initial,id:'3'.repeat(32),title:'Nested child',parent_id:child.id};
 nested.config.textContent=JSON.stringify({today:'2026-10-20',todos:[parent,child,grandchild],endpoint:'http://127.0.0.1:1234/todo',token:'token'});
 let nestedResolve,nestedPayload;mount(nested.doc,(_,options)=>{nestedPayload=JSON.parse(options.body);return new Promise(r=>{nestedResolve=r;});});
 const nestedRows=()=>nested.nodes['todo-list'].querySelectorAll('[data-todo-id]');
 assert.equal(nestedRows().length,3);assert.equal(nestedRows()[0].hidden,false);assert.equal(nestedRows()[1].hidden,false);assert.equal(nestedRows()[2].hidden,false);
 assert.equal(nestedRows()[0].querySelector('.todo-context-note').textContent,'Parent task context');
 await nested.nodes['todo-list'].fire('click',{target:nestedRows()[1].querySelector('[data-todo-action=subtask]')});
 assert.equal(nested.context.hidden,false);assert.match(nested.context.querySelector('span').textContent,/Due child/);
 nested.title.value='Another child';const newChild={...child,id:'4'.repeat(32),title:'Another child'};const nestedAdding=nested.add.fire('submit');
 assert.equal(nestedPayload.parent_id,child.id);newChild.parent_id=child.id;
 nestedResolve({ok:true,json:async()=>({ok:true,item:newChild,todos:[parent,child,grandchild,newChild]})});await nestedAdding;
 assert.equal(nestedRows().length,4);assert.equal(nested.context.hidden,true);
 const stars=fixture(),other={...stars.initial,id:'2'.repeat(32),title:'Second task',important:false};
 stars.config.textContent=JSON.stringify({today:'2026-10-20',todos:[stars.initial,other],endpoint:'http://127.0.0.1:1234/todo',token:'token'});
 let starResolve,starPayload;mount(stars.doc,(_,options)=>{starPayload=JSON.parse(options.body);return new Promise(r=>{starResolve=r;});});
 const starRows=()=>stars.nodes['todo-list'].children,secondStar=()=>starRows().find(row=>row.dataset.todoId===other.id).querySelector('[data-todo-action=set_importance]');
 assert.deepEqual(starRows().map(row=>row.dataset.todoId),[stars.initial.id,other.id]);
 assert.equal(secondStar()['aria-pressed'],'false');assert.equal(secondStar()['aria-label'],'Mark high importance');
 let starring=stars.nodes['todo-list'].fire('click',{target:secondStar()});
 assert.deepEqual(starPayload,{action:'set_importance',id:other.id,important:true});assert.equal(secondStar().disabled,true);assert.equal(secondStar()['aria-pressed'],'false');
 starResolve({ok:false,json:async()=>({ok:false,error:'Star write failed'})});await starring;
 assert.equal(secondStar()['aria-pressed'],'false');assert.deepEqual(starRows().map(row=>row.dataset.todoId),[stars.initial.id,other.id]);assert.match(stars.nodes['todo-status'].textContent,/Star write failed/);
 starring=stars.nodes['todo-list'].fire('click',{target:secondStar()});
 starResolve({ok:true,json:async()=>({ok:true,item:other,todos:[stars.initial,other]})});await starring;
 assert.equal(secondStar()['aria-pressed'],'false');assert.match(stars.nodes['todo-status'].textContent,/did not confirm/);
 const starred={...other,important:true};starring=stars.nodes['todo-list'].fire('click',{target:secondStar()});
 starResolve({ok:true,json:async()=>({ok:true,item:starred,todos:[stars.initial,starred]})});await starring;
 assert.equal(secondStar()['aria-pressed'],'true');assert.equal(secondStar()['aria-label'],'Remove high importance');assert.equal(secondStar().focused,true);
 assert.deepEqual(starRows().map(row=>row.dataset.todoId),[other.id,stars.initial.id]);
 const unstarring=stars.nodes['todo-list'].fire('click',{target:secondStar()});assert.equal(starPayload.important,false);assert.equal(secondStar()['aria-pressed'],'true');
 starResolve({ok:true,json:async()=>({ok:true,item:other,todos:[stars.initial,other]})});await unstarring;
 assert.equal(secondStar()['aria-pressed'],'false');assert.deepEqual(starRows().map(row=>row.dataset.todoId),[stars.initial.id,other.id]);
 const starParent={...stars.initial,id:'3'.repeat(32),due_date:'2026-10-25',important:false},earlySibling={...other,id:'4'.repeat(32),parent_id:starParent.id,due_date:'2026-10-19'},lateSibling={...other,id:'5'.repeat(32),parent_id:starParent.id,due_date:'2026-10-21'},starNested={...other,id:'6'.repeat(32),parent_id:lateSibling.id,important:true};
 const nestedQueue=[stars.initial,starParent,earlySibling,lateSibling,starNested];
 assert.deepEqual(orderedTodos(nestedQueue).map(item=>item.id),[starParent.id,lateSibling.id,starNested.id,earlySibling.id,stars.initial.id]);
 assert.equal(starParent.important,false);assert.equal(lateSibling.important,false);
 assert.deepEqual(orderedTodos(nestedQueue,new Set([stars.initial.id,earlySibling.id])).map(item=>item.id),[stars.initial.id,starParent.id,earlySibling.id,lateSibling.id,starNested.id]);
 assert.equal(confirmed({action:'set_importance',id:other.id,important:true},{ok:true,item:starred,todos:[other]}),false);
 assert.equal(confirmed({action:'set_importance',id:other.id,important:true},{ok:true,item:{...starred,important:1},todos:[starred]}),false);
 assert.equal(confirmed({action:'set_importance',id:other.id,important:true},{ok:true,item:{...starred,status:'removed'},todos:[]}),false);
 console.log('Task save pending/failure/mismatched acknowledgement/success, add, filters, lifecycle confirmation and archived read-only checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', script, str(SKILL)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
