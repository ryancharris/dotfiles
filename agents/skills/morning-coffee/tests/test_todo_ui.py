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

    def test_archive_lists_every_status_without_dates_and_disables_mutations(self):
        data = self.fixture()
        before = deepcopy(data)
        page = render_todos(data)
        surface = ReportSurface(page)
        rows = [node for node in surface.elements() if 'data-todo-id' in node['attrs']]
        self.assertEqual(len(rows), 5)
        self.assertEqual({node['attrs']['data-todo-group'] for node in rows}, {'pending', 'completed', 'cancelled'})
        buttons = [node for node in surface.elements() if node['tag'] == 'button']
        self.assertTrue(buttons)
        self.assertTrue(all('disabled' in node['attrs'] for node in buttons if node['attrs'].get('role') != 'tab'))
        tabs = [node for node in buttons if node['attrs'].get('role') == 'tab']
        self.assertEqual([node['attrs']['data-todo-filter'] for node in tabs], ['pending', 'completed', 'cancelled', 'all', 'archive'])
        self.assertEqual([node['attrs']['aria-selected'] for node in tabs], ['true', 'false', 'false', 'false', 'false'])
        self.assertNotIn('todo-filter', surface.by_id)
        self.assertEqual(surface.by_id['todo-panel']['attrs']['role'], 'tabpanel')
        self.assertIn('3 open · 1 completed · 1 cancelled', surface.visible_text())
        self.assertIn('Current &lt;task&gt;', page)
        self.assertEqual(data, before)

    def test_live_configuration_is_safe_json_and_all_actions_are_accessible(self):
        data = self.fixture(live=True)
        page = render_todos(data)
        surface = ReportSurface(page)
        config = json.loads(surface.by_id['todo-config']['children'][0])
        expected_todos = {item['id']: dict(item, important=item.get('important', False)) for item in data['todos']}
        self.assertEqual({item['id']: item for item in config['todos']}, expected_todos)
        self.assertNotIn('today', config)
        self.assertEqual(config['token'], data['todo_interaction']['token'])
        self.assertNotIn('safe</script>token', page)
        buttons = [node for node in surface.elements() if node['tag'] == 'button']
        self.assertTrue(all('disabled' not in node['attrs'] for node in buttons))
        actions = {node['attrs']['data-todo-action'] for node in buttons if 'data-todo-action' in node['attrs']}
        self.assertEqual(actions, {'complete', 'cancel', 'reopen', 'remove', 'subtask', 'projects', 'set_importance'})
        self.assertFalse(any('data-todo-reschedule' in node['attrs'] or node['attrs'].get('name') == 'due_date' for node in surface.elements()))
        self.assertNotIn('Reschedule', surface.visible_text())
        self.assertNotIn('Due date', surface.visible_text())

    def test_cancel_is_a_direct_row_action_and_cancelled_rows_keep_the_column(self):
        surface = ReportSurface(render_todos(self.fixture(live=True)))
        rows = [node for node in surface.elements() if 'data-todo-id' in node['attrs']]
        for row in rows:
            actions = next(node for node in surface.elements(row) if node['attrs'].get('class') == 'todo-actions')
            children = [node for node in actions['children'] if isinstance(node, dict)]
            self.assertEqual([node['attrs'].get('data-todo-action', node['attrs'].get('class'))
                              for node in children], ['set_importance',
                              'complete' if row['attrs']['data-todo-group'] == 'pending' else 'reopen',
                              'todo-cancel-slot', 'todo-more'])
            slot = children[2]
            cancel_buttons = [node for node in surface.elements(slot) if node['tag'] == 'button']
            if row['attrs']['data-todo-group'] == 'cancelled':
                self.assertFalse(cancel_buttons)
                self.assertEqual(slot['attrs']['aria-hidden'], 'true')
            else:
                self.assertEqual(len(cancel_buttons), 1)
                self.assertEqual(cancel_buttons[0]['attrs']['data-todo-action'], 'cancel')
                self.assertIn('Cancel', ''.join(cancel_buttons[0]['children']))
            menu = children[3]
            self.assertEqual(menu['tag'], 'details')
            self.assertEqual([node['attrs']['data-todo-action'] for node in surface.elements(menu)
                              if 'data-todo-action' in node['attrs']], ['subtask', 'projects', 'remove'])
            self.assertFalse(any(node['attrs'].get('data-todo-action') == 'cancel' for node in surface.elements(menu)))

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
const {mount,confirmed,summarize,orderedTodos,parseTags,matchesProject}=require(process.argv[1]+'/assets/local-todo.js');
class Element {
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.listeners={};this.dataset={};this.value='';this.textContent='';this.disabled=false;this.hidden=false;this.className='';}
 append(...children){for(const child of children){child.parent=this;this.children.push(child);}}
 replaceChildren(...children){this.children=[];this.append(...children);}
 addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
 setAttribute(name,value){this[name]=value;}
 fire(type,event={}){return Promise.all((this.listeners[type]||[]).map(fn=>fn({preventDefault(){},target:this,...event})));}
 matches(selector){
  if(selector.includes(','))return selector.split(',').some(s=>this.matches(s));
  if(selector.includes(' > ')){const [parent,child]=selector.split(' > ');return this.matches(child)&&Boolean(this.parent?.matches(parent));}
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
function fixture(live=true,projectTools=false){
 const section=new Element('section');section.id='todos';
 const doc=new Element();doc.defaultView={confirm:()=>true};doc.createElement=tag=>new Element(tag);doc.createTextNode=text=>{const e=new Element('#text');e.textContent=text;return e;};doc.append(section);
 const context=new Element('p');context.className='todo-add-context';context.hidden=true;const contextText=new Element('span'),rootButton=new Element('button');rootButton.dataset.todoRoot='';context.append(contextText,rootButton);section.append(context);
 const config=new Element('script');config.id='todo-config';
 const initial={id:'1'.repeat(32),title:'Open task',status:'pending'};
 config.textContent=JSON.stringify({today:'2026-10-20',todos:[initial],...(live?{endpoint:'http://127.0.0.1:1234/todo',token:'token'}:{})});
 const nodes={};for(const name of ['todo-status','todo-list','todo-empty','todo-counts']){nodes[name]=new Element(name==='todo-list'?'ul':'p');nodes[name].className=name;section.append(nodes[name]);}
 const tabs=['pending','completed','cancelled','all','archive'].map(status=>{const tab=new Element('button');tab.id='todo-tab-'+status;tab.dataset.todoFilter=status;tab.setAttribute('role','tab');section.append(tab);return tab;});
 const panel=new Element('div');panel.id='todo-panel';section.append(panel);const clearView=new Element('button');clearView.dataset.todoClearView='';section.append(clearView);
 const undoNotice=new Element('p');undoNotice.className='todo-undo';const undo=new Element('button');undo.dataset.todoUndo='';undoNotice.append(new Element('span'),undo);section.append(undoNotice);
 const add=new Element('form');add.className='todo-add';const title=new Element('input');title.name='title';const button=new Element('button');add.append(title,button);
 let projectTags=null,projectOptions=null,projectFilter=null;
 if(projectTools){projectTags=new Element('input');projectTags.name='project_tags';add.append(projectTags);projectOptions=new Element('datalist');projectOptions.id='todo-project-options';projectFilter=new Element('select');projectFilter.dataset.todoProjectFilter='';section.append(projectOptions,projectFilter);}
 section.append(add,config);
 return {doc,section,nodes,tabs,panel,clearView,add,title,projectTags,projectOptions,projectFilter,initial,config,context,undo,undoNotice};
}
const batch='b'.repeat(32),stamp='2026-10-20T15:00:00Z';
const archived=(...items)=>items.map(item=>({...item,batch_id:batch,cleared_at:stamp}));
(async()=>{
 const f=fixture();let resolve,calls=[];
 mount(f.doc,(endpoint,options)=>{calls.push({endpoint,options});return new Promise(r=>{resolve=r;});});
 const row=()=>f.nodes['todo-list'].children[0];
 assert.equal(f.tabs[0]['aria-selected'],'true');assert.equal(row().hidden,false);assert.match(f.nodes['todo-counts'].textContent,/1 open/);
 const old=row(),complete=old.querySelector('[data-todo-action=complete]');
 const pending=f.nodes['todo-list'].fire('click',{target:complete});
 assert.equal(row(),old);assert.equal(row().dataset.todoGroup,'pending');assert.equal(complete.disabled,true);
 assert.deepEqual(JSON.parse(calls[0].options.body),{action:'complete',id:f.initial.id});assert.equal(calls[0].options.headers['X-Brief-Token'],'token');
 resolve({ok:false,json:async()=>({ok:false,error:'Disk write failed'})});await pending;
 assert.equal(row().dataset.todoGroup,'pending');assert.match(f.nodes['todo-status'].textContent,/Disk write failed/);
 const success=f.nodes['todo-list'].fire('click',{target:row().querySelector('[data-todo-action=complete]')});
 const completed={...f.initial,status:'completed'};resolve({ok:true,json:async()=>({ok:true,item:completed,todos:[completed]})});await success;
 assert.equal(row().dataset.todoGroup,'completed');assert.equal(row().hidden,true);assert.match(f.nodes['todo-counts'].textContent,/0 open/);
 await f.tabs[1].fire('click');assert.equal(row().hidden,false);assert.equal(f.panel['aria-labelledby'],'todo-tab-completed');
 const reopen=f.nodes['todo-list'].fire('click',{target:row().querySelector('[data-todo-action=reopen]')});
 resolve({ok:true,json:async()=>({ok:true,item:{...f.initial,id:'2'.repeat(32)},todos:[f.initial]})});await reopen;
 assert.equal(row().dataset.todoGroup,'completed');assert.match(f.nodes['todo-status'].textContent,/did not confirm/);
 const cancelled={...f.initial,status:'cancelled'};assert.equal(confirmed({action:'cancel',id:f.initial.id},{ok:true,item:cancelled,todos:[cancelled]}),true);
 assert.equal(confirmed({action:'remove',id:f.initial.id},{ok:true,item:{...f.initial,status:'removed'},todos:[],batch_id:batch,archive:archived(f.initial)}),true);
 assert.equal(confirmed({action:'remove',id:f.initial.id},{ok:true,item:{...f.initial,status:'removed'},todos:[f.initial]}),false);
 assert.equal(confirmed({action:'reschedule',id:f.initial.id,due_date:'2026-10-23'},{ok:true,item:f.initial,todos:[f.initial]}),false);
 assert.equal(f.nodes['todo-list'].querySelector('[name=due_date]'),null);
 assert.deepEqual(summarize([f.initial,{...f.initial,id:'2'.repeat(32),due_date:'2026-10-19'},{...f.initial,id:'3'.repeat(32),due_date:'2026-10-21'},completed,cancelled],'2026-10-20'),{pending:3,completed:1,cancelled:1});
 f.title.value='Added task';const added={...f.initial,id:'4'.repeat(32),title:'Added task'};
 const adding=f.add.fire('submit');assert.equal(f.nodes['todo-list'].children.length,1);assert.deepEqual(JSON.parse(calls.at(-1).options.body),{action:'add',title:'Added task'});
 resolve({ok:true,json:async()=>({ok:true,item:added,todos:[completed,added]})});await adding;
 assert.equal(f.nodes['todo-list'].children.length,2);assert.equal(f.title.value,'');assert.equal(f.title.focused,true);
 const archive=fixture(false);let archiveCalls=0;mount(archive.doc,()=>{archiveCalls++;});
 assert.equal(archive.title.disabled,true);await archive.add.fire('submit');assert.equal(archiveCalls,0);
 const nested=fixture();const parent={...nested.initial,title:'Completed parent',status:'completed'},child={...nested.initial,id:'2'.repeat(32),title:'Open child',parent_id:parent.id},grandchild={...nested.initial,id:'3'.repeat(32),title:'Nested child',parent_id:child.id};
 nested.config.textContent=JSON.stringify({today:'2026-10-20',todos:[parent,child,grandchild],endpoint:'http://127.0.0.1:1234/todo',token:'token'});
 let nestedResolve,nestedPayload,nestedCalls=0;mount(nested.doc,(_,options)=>{nestedCalls++;nestedPayload=JSON.parse(options.body);return new Promise(r=>{nestedResolve=r;});});
 const nestedRows=()=>nested.nodes['todo-list'].querySelectorAll('[data-todo-id]');
 assert.equal(nestedRows().length,3);assert.equal(nestedRows()[0].hidden,false);assert.equal(nestedRows()[1].hidden,false);assert.equal(nestedRows()[2].hidden,false);
 assert.equal(nestedRows()[0].querySelector('.todo-context-note').textContent,'Parent task context');
 const nestedList=nested.nodes['todo-list'];
 const childRow=()=>nestedRows().find(row=>row.dataset.todoId===child.id);
 const composer=()=>nestedList.querySelector('.todo-subtask-form');
 const draft=()=>composer().querySelector('[name=title]');
 const openComposer=async row=>nestedList.fire('click',{target:row.querySelector('[data-todo-action=subtask]')});
 nested.title.value='Unrelated root draft';
 await openComposer(childRow());
 assert.equal(composer().dataset.todoSubtask,child.id);assert.equal(composer().parent,childRow());
 assert.equal(childRow().children[1],composer());assert.equal(childRow().children[2].className,'todo-children');
 assert.equal(draft().focused,true);assert.equal(composer().querySelector('label')['for'],draft().id);
 assert.equal(composer().querySelector('label').textContent,'Subtask of Open child');
 assert.equal(nested.title.value,'Unrelated root draft');assert.equal(nestedCalls,0);
 draft().value='Another child';
 let nestedAdding=composer().fire('submit');
 assert.deepEqual(nestedPayload,{action:'add',title:'Another child',parent_id:child.id});
 assert.equal(draft().disabled,true);
 // Escape while a save is pending cannot dismiss the submitted draft.
 await nestedList.fire('keydown',{target:draft(),key:'Escape'});assert.notEqual(composer(),null);
 nestedResolve({ok:false,json:async()=>({ok:false,error:'Subtask write failed'})});await nestedAdding;
 assert.equal(draft().value,'Another child');assert.equal(draft().focused,true);
 assert.equal(nested.title.value,'Unrelated root draft');assert.equal(nestedRows().length,3);
 // Switching tabs or parents must retain each unfinished composer draft.
 await nested.tabs[1].fire('click');await nested.tabs[0].fire('click');assert.equal(draft().value,'Another child');
 await openComposer(nestedRows()[0]);draft().value='Different parent draft';
 await openComposer(childRow());assert.equal(draft().value,'Another child');
 await openComposer(nestedRows()[0]);assert.equal(draft().value,'Different parent draft');
 const beforeEscape=nestedCalls;
 await nestedList.fire('keydown',{target:draft(),key:'Escape'});
 assert.equal(composer(),null);assert.equal(nestedCalls,beforeEscape);
 assert.equal(nestedRows()[0].querySelector('.todo-more > summary').focused,true);
 await openComposer(nestedRows()[0]);assert.equal(draft().value,'');
 await nestedList.fire('click',{target:composer().querySelector('[data-todo-dismiss-subtask]')});
 assert.equal(composer(),null);assert.equal(nestedCalls,beforeEscape);
 // Reopening a different parent preserves its draft; acknowledged saves keep the composer ready for another child.
 await openComposer(childRow());assert.equal(draft().value,'Another child');
 const newChild={...child,id:'4'.repeat(32),title:'Another child',parent_id:child.id};
 nestedAdding=composer().fire('submit');
 nestedResolve({ok:true,json:async()=>({ok:true,item:newChild,todos:[parent,child,grandchild,newChild]})});await nestedAdding;
 assert.equal(nestedRows().length,4);assert.equal(composer().dataset.todoSubtask,child.id);
 assert.equal(draft().value,'');assert.equal(draft().focused,true);assert.equal(nested.title.value,'Unrelated root draft');
 // Creating from Completed moves to Open and keeps the completed parent visible as context.
 await nested.tabs[1].fire('click');await openComposer(nestedRows()[0]);draft().value='Child of completed parent';
 const completedChild={...child,id:'5'.repeat(32),title:'Child of completed parent',parent_id:parent.id};
 const completedAdding=composer().fire('submit');assert.equal(nestedPayload.parent_id,parent.id);
 nestedResolve({ok:true,json:async()=>({ok:true,item:completedChild,todos:[parent,child,grandchild,newChild,completedChild]})});await completedAdding;
 assert.equal(nested.tabs[0]['aria-selected'],'true');assert.equal(nestedRows()[0].hidden,false);
 assert.equal(nestedRows().find(row=>row.dataset.todoId===completedChild.id).hidden,false);
 assert.equal(nestedRows()[0].querySelector('.todo-context-note').textContent,'Parent task context');
 assert.equal(draft().value,'');assert.equal(draft().focused,true);
 // Inline cancellation is distinct from cancelling the task and never writes to the store.
 const beforeDismiss=nestedCalls;draft().value='Discard this';
 await nestedList.fire('click',{target:composer().querySelector('[data-todo-dismiss-subtask]')});
 assert.equal(composer(),null);assert.equal(nestedCalls,beforeDismiss);assert.equal(nested.title.value,'Unrelated root draft');
 const directActions=childRow().querySelector('.todo-actions');
 assert.ok(directActions.querySelector('.todo-more'));
 assert.equal(directActions.querySelector('.todo-more').querySelector('[data-todo-action=cancel]'),null);
 assert.equal(directActions.querySelector('[data-todo-action=cancel]').parent.className,'todo-cancel-slot');
 const cancelFixture=fixture(),doneTask={...cancelFixture.initial,status:'completed'};
 cancelFixture.config.textContent=JSON.stringify({todos:[doneTask],endpoint:'http://127.0.0.1:1234/todo',token:'token'});
 let cancelResolve,cancelPayload;mount(cancelFixture.doc,(_,options)=>{cancelPayload=JSON.parse(options.body);return new Promise(r=>{cancelResolve=r;});});
 await cancelFixture.tabs[1].fire('click');
 const cancelling=cancelFixture.nodes['todo-list'].fire('click',{target:cancelFixture.nodes['todo-list'].querySelector('[data-todo-action=cancel]')});
 assert.deepEqual(cancelPayload,{action:'cancel',id:doneTask.id});
 const cancelledDone={...doneTask,status:'cancelled'};cancelResolve({ok:true,json:async()=>({ok:true,item:cancelledDone,todos:[cancelledDone]})});await cancelling;
 await cancelFixture.tabs[2].fire('click');
 const cancelSlot=cancelFixture.nodes['todo-list'].querySelector('.todo-cancel-slot');
 assert.equal(cancelSlot.children.length,0);assert.equal(cancelSlot['aria-hidden'],'true');
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
 // Clear only the selected tab, after a matching acknowledgement; never include ancestor context.
 assert.equal(f.clearView.disabled,false);
 let confirmMessage;f.doc.defaultView.confirm=message=>{confirmMessage=message;return false;};
 const callsBefore=calls.length;await f.clearView.fire('click');assert.equal(calls.length,callsBefore);assert.match(confirmMessage,/1 task.*Completed/);assert.match(confirmMessage,/Archived/);
 f.doc.defaultView.confirm=()=>true;
 let clearing=f.clearView.fire('click');
 assert.deepEqual(JSON.parse(calls.at(-1).options.body),{action:'clear',ids:[completed.id],status:'completed'});
 assert.equal(f.nodes['todo-list'].children.length,2);
 resolve({ok:false,json:async()=>({ok:false,error:'Clear write failed'})});await clearing;
 assert.equal(f.nodes['todo-list'].children.length,2);assert.match(f.nodes['todo-status'].textContent,/Clear write failed/);
 clearing=f.clearView.fire('click');
 resolve({ok:true,json:async()=>({ok:true,status:'completed',removed_ids:[added.id],todos:[added]})});await clearing;
 assert.equal(f.nodes['todo-list'].children.length,2);assert.match(f.nodes['todo-status'].textContent,/did not confirm/);
 clearing=f.clearView.fire('click');
 resolve({ok:true,json:async()=>({ok:true,status:'completed',removed_ids:[completed.id],todos:[added],batch_id:batch,archive:archived(completed)})});await clearing;
 assert.equal(f.nodes['todo-list'].children.length,1);assert.equal(row().hidden,true);assert.equal(f.clearView.disabled,true);
 assert.equal(f.tabs[1].focused,true);assert.equal(f.tabs[1].textContent,'Completed (0)');
 await f.tabs[1].fire('keydown',{key:'ArrowLeft'});assert.equal(f.tabs[0]['aria-selected'],'true');assert.equal(row().hidden,false);
 await f.tabs[0].fire('keydown',{key:'End'});assert.equal(f.tabs[4]['aria-selected'],'true');
 await f.tabs[4].fire('keydown',{key:'ArrowLeft'});assert.equal(f.tabs[3]['aria-selected'],'true');
 clearing=f.clearView.fire('click');assert.deepEqual(JSON.parse(calls.at(-1).options.body),{action:'clear',ids:[added.id],status:'all'});
 resolve({ok:true,json:async()=>({ok:true,status:'all',removed_ids:[added.id],todos:[],batch_id:batch,archive:archived(completed,added)})});await clearing;
 assert.equal(f.nodes['todo-list'].children.length,0);assert.equal(f.clearView.disabled,true);
 await f.tabs[4].fire('keydown',{key:'ArrowRight'});assert.equal(f.tabs[0]['aria-selected'],'true');
 const nestedClearing=nested.clearView.fire('click');
 assert.deepEqual(nestedPayload,{action:'clear',ids:[child.id,grandchild.id,newChild.id,completedChild.id],status:'pending'});
 nestedResolve({ok:true,json:async()=>({ok:true,status:'pending',removed_ids:[child.id,grandchild.id,newChild.id,completedChild.id],todos:[parent],batch_id:batch,archive:archived(child,grandchild,newChild,completedChild)})});await nestedClearing;
 assert.equal(nestedRows().length,1);assert.equal(nestedRows()[0].hidden,true);assert.equal(nested.clearView.disabled,true);
 const single=fixture();let singlePayload;mount(single.doc,async(_,options)=>{singlePayload=JSON.parse(options.body);return {ok:true,json:async()=>({ok:true,item:{...single.initial,status:'removed'},todos:[],batch_id:batch,archive:archived(single.initial)})};});
 await single.nodes['todo-list'].fire('click',{target:single.nodes['todo-list'].querySelector('[data-todo-action=remove]')});
 assert.deepEqual(singlePayload,{action:'remove',id:single.initial.id});assert.equal(single.nodes['todo-list'].children.length,0);
 // Archive remains browseable after reload; failed undo preserves it; restore needs matching acknowledgement.
 const reload=fixture();reload.config.textContent=JSON.stringify({todos:[],archive:archived(single.initial),endpoint:'http://127.0.0.1:1234/todo',token:'token'});
 let restoreResolve,restorePayload;mount(reload.doc,(_,options)=>{restorePayload=JSON.parse(options.body);return new Promise(r=>{restoreResolve=r;});});
 assert.equal(reload.undo.disabled,false);await reload.tabs[4].fire('click');
 const archivedRow=()=>reload.nodes['todo-list'].children[0];assert.equal(archivedRow().querySelector('[data-todo-action=remove]'),null);assert.equal(reload.clearView.hidden,true);
 let undoing=reload.undo.fire('click');assert.deepEqual(restorePayload,{action:'undo',id:batch});restoreResolve({ok:false,json:async()=>({ok:false,error:'Undo failed'})});await undoing;
 assert.equal(archivedRow().dataset.todoId,single.initial.id);assert.match(reload.nodes['todo-status'].textContent,/Undo failed/);
 let restoring=reload.nodes['todo-list'].fire('click',{target:archivedRow().querySelector('[data-todo-action=restore]')});
 assert.deepEqual(restorePayload,{action:'restore',id:single.initial.id});restoreResolve({ok:true,json:async()=>({ok:true,todos:[single.initial],archive:[],restored_ids:[single.initial.id],batch_id:batch})});await restoring;
 assert.equal(reload.tabs[0]['aria-selected'],'true');assert.equal(reload.undoNotice.hidden,true);assert.equal(reload.nodes['todo-list'].children[0].hidden,false);
 const bulkUndo=f.undo.fire('click');assert.deepEqual(JSON.parse(calls.at(-1).options.body),{action:'undo',id:batch});
 resolve({ok:true,json:async()=>({ok:true,todos:[completed,added],archive:[],restored_ids:[completed.id,added.id],batch_id:batch})});await bulkUndo;
 assert.equal(f.nodes['todo-list'].children.length,2);assert.equal(f.undoNotice.hidden,true);
 assert.equal(confirmed({action:'undo',id:batch},{ok:true,todos:[],archive:[],restored_ids:[],batch_id:batch},archived(single.initial)),false);
 assert.equal(confirmed({action:'clear',ids:[added.id],status:'all'},{ok:true,status:'all',removed_ids:[added.id],todos:[added]}),false);
 assert.equal(confirmed({action:'clear',ids:[added.id],status:'all'},{ok:true,status:'pending',removed_ids:[added.id],todos:[],batch_id:batch,archive:archived(completed,added)}),false);
 assert.equal(confirmed({action:'clear',ids:[added.id,added.id],status:'all'},{ok:true,status:'all',removed_ids:[added.id,added.id],todos:[]}),false);
 assert.equal(archive.tabs[0].disabled,false);await archive.tabs[3].fire('click');assert.equal(archive.tabs[3]['aria-selected'],'true');
 await archive.clearView.fire('click');assert.equal(archiveCalls,0);
 assert.deepEqual(parseTags('  Transport   plan, transport plan, PrivateLink,  , PRIVATELINK  '),['Transport plan','PrivateLink']);
 assert.equal(matchesProject({project_tags:['Transport']},'tag:transport'),true);
 assert.equal(matchesProject({project_tags:[]},'__untagged__'),true);
 assert.equal(matchesProject({project_tags:['__untagged__']},'__untagged__'),false);
 assert.equal(matchesProject({project_tags:['__untagged__']},'tag:__untagged__'),true);

 // The add form submits normalized project tags and clears both fields after acknowledgement.
 const projectAdd=fixture(true,true);let projectAddResolve,projectAddPayload;
 mount(projectAdd.doc,(_,options)=>{projectAddPayload=JSON.parse(options.body);return new Promise(r=>{projectAddResolve=r;});});
 projectAdd.title.value='New project task';projectAdd.projectTags.value=' Transport   plan, transport plan, PrivateLink ';
 const addingProject=projectAdd.add.fire('submit');
 assert.deepEqual(projectAddPayload,{action:'add',title:'New project task',project_tags:['Transport plan','PrivateLink']});
 const addedProject={...projectAdd.initial,id:'7'.repeat(32),title:'New project task',project_tags:['Transport plan','PrivateLink']};
 projectAddResolve({ok:true,json:async()=>({ok:true,item:addedProject,todos:[projectAdd.initial,addedProject]})});await addingProject;
 assert.equal(projectAdd.projectTags.value,'');
 assert.deepEqual(projectAdd.projectOptions.children.map(option=>option.value),['PrivateLink','Transport plan']);

 // Tag edits keep old chips and the draft through failed/mismatched saves, then update on confirmation.
 const projectEdit=fixture(true,true),tagParent={...projectEdit.initial,title:'Parent',project_tags:['Original']};
 const tagChild={...projectEdit.initial,id:'8'.repeat(32),title:'Child',parent_id:tagParent.id,project_tags:['Transit']};
 projectEdit.config.textContent=JSON.stringify({todos:[tagParent,tagChild],endpoint:'http://127.0.0.1:1234/todo',token:'token'});
 let projectResolve,projectPayload,projectCalls=0;
 mount(projectEdit.doc,(_,options)=>{projectCalls++;projectPayload=JSON.parse(options.body);return new Promise(r=>{projectResolve=r;});});
 const projectList=projectEdit.nodes['todo-list'];
 const rowFor=(id)=>projectList.querySelector('[data-todo-id="'+id+'"]');
 const projectForm=()=>projectList.querySelector('.todo-project-form');
 const projectInput=()=>projectForm()?.querySelector('[name=project_tags]');
 const directTags=row=>row.querySelector('.todo-entry').querySelectorAll('.todo-project-tag').map(node=>node.textContent);
 await projectList.fire('click',{target:rowFor(tagParent.id).querySelector('[data-todo-action=projects]')});
 let tagDraft=projectInput();assert.equal(tagDraft.value,'Original');
 tagDraft.value='Transit, PRIVATE link';await tagDraft.fire('input');
 let editing=projectForm().fire('submit');
 assert.deepEqual(projectPayload,{action:'set_project_tags',id:tagParent.id,project_tags:['Transit','PRIVATE link']});
 projectResolve({ok:false,json:async()=>({ok:false,error:'Tag write failed'})});await editing;
 assert.deepEqual(directTags(rowFor(tagParent.id)),['Original']);
 assert.equal(projectInput().value,'Transit, PRIVATE link');
 editing=projectForm().fire('submit');
 const wrongParent={...tagParent,project_tags:['Wrong']};
 projectResolve({ok:true,json:async()=>({ok:true,item:wrongParent,todos:[wrongParent,tagChild]})});await editing;
 assert.deepEqual(directTags(rowFor(tagParent.id)),['Original']);
 assert.equal(projectInput().value,'Transit, PRIVATE link');
 editing=projectForm().fire('submit');
 const updatedParent={...tagParent,project_tags:['Transit','PRIVATE link']};
 projectResolve({ok:true,json:async()=>({ok:true,item:updatedParent,todos:[updatedParent,tagChild]})});await editing;
 assert.deepEqual(directTags(rowFor(tagParent.id)),['Transit','PRIVATE link']);
 assert.deepEqual(projectEdit.projectOptions.children.map(option=>option.value),['PRIVATE link','Transit']);
 assert.equal(projectForm(),null);
 await projectList.fire('click',{target:rowFor(tagParent.id).querySelector('[data-todo-action=projects]')});
 tagDraft=projectInput();tagDraft.value='Discard by Escape';await tagDraft.fire('input');
 const callsBeforeDismiss=projectCalls;await projectList.fire('keydown',{target:tagDraft,key:'Escape'});
 assert.equal(projectForm(),null);assert.equal(projectCalls,callsBeforeDismiss);
 await projectList.fire('click',{target:rowFor(tagParent.id).querySelector('[data-todo-action=projects]')});
 tagDraft=projectInput();tagDraft.value='Discard by button';await tagDraft.fire('input');
 await projectList.fire('click',{target:projectForm().querySelector('[data-todo-dismiss-projects]')});
 assert.equal(projectForm(),null);assert.equal(projectCalls,callsBeforeDismiss);

 // Project/status/archive filters retain parent context but clear only directly matching tasks.
 const projectFilterFixture=fixture(true,true),p={...projectFilterFixture.initial,title:'Untagged parent',project_tags:[]};
 const matchingChild={...p,id:'9'.repeat(32),title:'Transit child',parent_id:p.id,project_tags:['Transit']};
 const literalTag={...p,id:'a'.repeat(32),title:'Literal reserved name',parent_id:p.id,project_tags:['__untagged__']};
 const completedTransit={...p,id:'c'.repeat(32),title:'Completed transit',status:'completed',project_tags:['Transit']};
 const cancelledUntagged={...p,id:'d'.repeat(32),title:'Cancelled untagged',status:'cancelled',project_tags:[]};
 const archivedTransit={...p,id:'e'.repeat(32),title:'Archived transit',status:'pending',project_tags:['Transit'],batch_id:batch,cleared_at:stamp};
 projectFilterFixture.config.textContent=JSON.stringify({todos:[p,matchingChild,literalTag,completedTransit,cancelledUntagged],archive:[archivedTransit],endpoint:'http://127.0.0.1:1234/todo',token:'token'});
 let filterResolve,filterPayload;projectFilterFixture.doc.defaultView.confirm=()=>true;
 mount(projectFilterFixture.doc,(_,options)=>{filterPayload=JSON.parse(options.body);return new Promise(r=>{filterResolve=r;});});
 const filterList=projectFilterFixture.nodes['todo-list'],filterRow=id=>filterList.querySelector('[data-todo-id="'+id+'"]');
 const chooseProject=async value=>{projectFilterFixture.projectFilter.value=value;await projectFilterFixture.projectFilter.fire('change');};
 await chooseProject('tag:TRANSIT');
 assert.equal(filterRow(p.id).hidden,false);assert.equal(filterRow(matchingChild.id).hidden,false);
 assert.equal(filterRow(p.id).querySelector('.todo-context-note').textContent,'Parent task context');
 assert.equal(filterRow(literalTag.id).hidden,true);assert.equal(filterRow(completedTransit.id).hidden,true);
 await projectFilterFixture.tabs[1].fire('click');
 assert.equal(filterRow(completedTransit.id).hidden,false);assert.equal(filterRow(matchingChild.id).hidden,true);
 await projectFilterFixture.tabs[0].fire('click');
 await projectFilterFixture.tabs[4].fire('click');assert.equal(filterRow(archivedTransit.id).hidden,false);
 await projectFilterFixture.tabs[0].fire('click');await chooseProject('__untagged__');
 assert.equal(filterRow(p.id).hidden,false);assert.equal(filterRow(matchingChild.id).hidden,true);
 await chooseProject('tag:__untagged__');
 assert.equal(filterRow(literalTag.id).hidden,false);assert.equal(filterRow(p.id).hidden,false);
 await chooseProject('tag:Transit');
 const clearingProject=projectFilterFixture.clearView.fire('click');
 assert.deepEqual(filterPayload,{action:'clear',ids:[matchingChild.id],status:'pending'});
 const childArchived={...matchingChild,batch_id:batch,cleared_at:stamp};
 filterResolve({ok:true,json:async()=>({ok:true,status:'pending',removed_ids:[matchingChild.id],todos:[p,literalTag,completedTransit,cancelledUntagged],batch_id:batch,archive:[archivedTransit,childArchived]})});await clearingProject;
 assert.equal(filterRow(matchingChild.id),null);assert.equal(filterRow(p.id).hidden,true);

 // An editor draft survives both status and project changes until explicitly dismissed.
 await chooseProject('');await projectFilterFixture.tabs[1].fire('click');
 await filterList.fire('click',{target:filterRow(completedTransit.id).querySelector('[data-todo-action=projects]')});
 const switchingDraft=filterList.querySelector('.todo-project-form').querySelector('[name=project_tags]');
 switchingDraft.value='Unfinished project edit';await switchingDraft.fire('input');
 await projectFilterFixture.tabs[0].fire('click');await chooseProject('tag:Transit');
 await projectFilterFixture.tabs[1].fire('click');await chooseProject('');
 assert.equal(filterList.querySelector('.todo-project-form').querySelector('[name=project_tags]').value,'Unfinished project edit');
 console.log('Task actions, project tag editing, filter combinations, clear selection, and draft retention checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', script, str(SKILL)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
