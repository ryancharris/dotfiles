/* Local task actions change the page only after the store acknowledges them. */
(function () {
  'use strict';
  const statuses=['pending','completed','cancelled'];
  function validItem(item,removed=false){
    return Boolean(item && typeof item.id==='string' && /^[a-f0-9]{32}$/.test(item.id) && typeof item.title==='string' && item.title.trim() && item.title.length<=500 &&
      (statuses.includes(item.status) || (removed && item.status==='removed')) && /^\d{4}-\d{2}-\d{2}$/.test(item.due_date) &&
      (item.parent_id==null || (typeof item.parent_id==='string' && /^[a-f0-9]{32}$/.test(item.parent_id))) &&
      (item.important===undefined || typeof item.important==='boolean'));
  }
  function group(item,today){return item.status==='pending' ? (item.due_date<today?'overdue':item.due_date===today?'today':'upcoming') : item.status;}
  function summarize(items,today){
    const counts={overdue:0,today:0,upcoming:0};
    items.forEach(item=>{const key=group(item,today);if(Object.hasOwn(counts,key))counts[key]++;});
    return counts;
  }
  function orderedTodos(items,matching){
    const byId=new Map(items.map(item=>[item.id,item])),importantGroups=new Set(),children=new Map();
    items.forEach(item=>{
      const parent=byId.has(item.parent_id) && item.parent_id!==item.id?item.parent_id:null;
      if(!children.has(parent))children.set(parent,[]);children.get(parent).push(item);
      if(item.important===true && (!matching || matching.has(item.id))){
        let id=item.id;const seen=new Set();while(byId.has(id) && !seen.has(id)){seen.add(id);importantGroups.add(id);id=byId.get(id).parent_id;}
      }
    });
    const compare=(a,b)=>Number(!importantGroups.has(a.id))-Number(!importantGroups.has(b.id)) ||
      a.due_date.localeCompare(b.due_date) || (a.created_at||'').localeCompare(b.created_at||'') || a.id.localeCompare(b.id);
    children.forEach(siblings=>siblings.sort(compare));
    const ordered=[],stack=[...(children.get(null)||[])].reverse(),seen=new Set();
    while(stack.length){const item=stack.pop();if(seen.has(item.id))continue;seen.add(item.id);ordered.push(item);stack.push(...[...(children.get(item.id)||[])].reverse());}
    return ordered;
  }
  function confirmed(request,result){
    if(!result || result.ok!==true || !validItem(result.item,true) || !Array.isArray(result.todos) || !result.todos.every(item=>validItem(item)))return false;
    if(new Set(result.todos.map(item=>item.id)).size!==result.todos.length)return false;
    const item=result.item;
    if(request.action==='add'){
      if(item.title!==request.title.trim().split(/\s+/).join(' ') || item.due_date!==request.due_date || item.status!=='pending' || (item.parent_id||null)!==(request.parent_id||null) || Boolean(item.important)!==Boolean(request.important))return false;
    }else if(request.action==='set_importance'){
      if(typeof request.important!=='boolean' || item.id!==request.id || item.status==='removed' || item.important!==request.important)return false;
    }else{
      const expected={complete:'completed',cancel:'cancelled',reopen:'pending',reschedule:'pending',remove:'removed'}[request.action];
      if(item.id!==request.id || item.status!==expected || (request.action==='reschedule' && item.due_date!==request.due_date))return false;
    }
    const saved=result.todos.find(entry=>entry.id===item.id);
    return item.status==='removed' ? !saved : Boolean(saved && saved.title===item.title && saved.due_date===item.due_date && saved.status===item.status && (saved.parent_id||null)===(item.parent_id||null) && Boolean(saved.important)===Boolean(item.important));
  }
  function mount(doc,request){
    const section=doc.querySelector('#todos'),configNode=doc.querySelector('#todo-config');
    if(!section || !configNode || section.todoMounted)return;
    section.todoMounted=true;
    const notice=section.querySelector('.todo-status');
    let config;
    try{config=JSON.parse(configNode.textContent);}catch(error){notice.textContent='Local tasks unavailable. Reopen a live Coffee or Tea report.';return;}
    const save=request || (typeof fetch==='function'?fetch:null),enabled=Boolean(config.endpoint && config.token && save);
    const today=config.today;
    let items=Array.isArray(config.todos)?config.todos.filter(item=>validItem(item)):[],busy=false,parentId=null;
    const list=section.querySelector('.todo-list'),filter=section.querySelector('#todo-filter'),empty=section.querySelector('.todo-empty'),counts=section.querySelector('.todo-counts'),add=section.querySelector('.todo-add');
    const element=(tag,text,className)=>{const node=doc.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
    const actionButton=(label,action)=>{const node=element('button',label);node.type='button';node.dataset.todoAction=action;node.disabled=!enabled || busy;return node;};
    const parentContext=section.querySelector('.todo-add-context');
    function showParent(){
      if(!parentContext)return;
      const parent=items.find(item=>item.id===parentId);parentContext.hidden=!parent;
      if(parent)parentContext.querySelector('span').textContent='Subtask of '+parent.title;
    }
    function render(){
      list.replaceChildren();
      const totals=summarize(items,today);
      counts.textContent=totals.overdue+' overdue · '+totals.today+' due today · '+totals.upcoming+' upcoming';
      const byId=new Map(items.map(item=>[item.id,item])),matching=new Set(),visibleIds=new Set(),nodes=new Map();
      items.forEach(item=>{const key=group(item,today);if(filter.value==='all' || filter.value===key || (filter.value==='due' && (key==='overdue' || key==='today')))matching.add(item.id);});
      matching.forEach(id=>{const seen=new Set();while(byId.has(id) && !seen.has(id)){seen.add(id);visibleIds.add(id);id=byId.get(id).parent_id;}});
      const ordered=orderedTodos(items,matching);
      ordered.forEach(item=>{
        const key=group(item,today),row=element('li',undefined,'todo-row');row.dataset.todoId=item.id;row.dataset.todoGroup=key;
        row.dataset.todoImportant=String(item.important===true);
        row.hidden=!visibleIds.has(item.id);
        const copy=element('div',undefined,'todo-copy');copy.append(element('b',item.title,'todo-title'));
        if(visibleIds.has(item.id) && !matching.has(item.id))copy.append(element('span','Parent task context','todo-context-note'));
        const meta=element('span',undefined,'todo-meta');meta.append(doc.createTextNode({overdue:'Overdue',today:'Due today',upcoming:'Upcoming',completed:'Completed',cancelled:'Cancelled'}[key]+' · '));
        const time=element('time',item.due_date);time.dateTime=item.due_date;meta.append(time);copy.append(meta);
        const actions=element('div',undefined,'todo-actions'),star=actionButton(item.important===true?'⭐️':'☆','set_importance');star.className='todo-star';
        const starLabel=item.important===true?'Remove high importance':'Mark high importance';star.title=starLabel;star.setAttribute('aria-label',starLabel);star.setAttribute('aria-pressed',String(item.important===true));actions.append(star);
        actions.append(actionButton(item.status==='pending'?'Complete':'Reopen',item.status==='pending'?'complete':'reopen'));
        actions.append(actionButton('Add subtask','subtask'));
        const details=element('details'),summary=element('summary','Manage'),manage=element('div',undefined,'todo-manage'),form=element('form');form.dataset.todoReschedule='';
        const label=element('label','New due date'),input=element('input');input.type='date';input.name='due_date';input.value=item.due_date;input.required=true;input.id='todo-date-'+item.id;input.disabled=!enabled || busy;label.htmlFor=input.id;
        const reschedule=element('button','Reschedule');reschedule.type='submit';reschedule.disabled=!enabled || busy;
        form.append(label,input,reschedule);manage.append(form);
        if(item.status!=='cancelled')manage.append(actionButton('Cancel task','cancel'));
        manage.append(actionButton('Remove task (keep subtasks)','remove'));details.append(summary,manage);actions.append(details);
        const entry=element('div',undefined,'todo-entry'),children=element('ul',undefined,'todo-children');entry.append(copy,actions);row.append(entry,children);nodes.set(item.id,{row,children});
      });
      ordered.forEach(item=>{const parent=nodes.get(item.parent_id);(parent && item.parent_id!==item.id?parent.children:list).append(nodes.get(item.id).row);});
      nodes.forEach(node=>{node.children.hidden=node.children.children.length===0;});
      empty.hidden=matching.size>0;empty.textContent=items.length?'No tasks in this view. Choose All tasks to see the rest.':'No tasks yet. Add one above.';
      section.querySelectorAll('.todo-add input,.todo-add button').forEach(node=>{node.disabled=!enabled || busy;});
      showParent();
    }
    async function perform(payload,label){
      if(!enabled || busy)return false;
      busy=true;notice.textContent='Saving '+label+'…';section.querySelectorAll('input,button').forEach(node=>{node.disabled=true;});
      try{
        const response=await save(config.endpoint,{method:'POST',credentials:'omit',signal:AbortSignal.timeout(10000),headers:{'Content-Type':'application/json','X-Brief-Token':config.token},body:JSON.stringify(payload)});
        const result=await response.json();
        if(!response.ok || result.ok!==true)throw Error(result.error || 'The task could not be saved.');
        if(!confirmed(payload,result))throw Error('The local server did not confirm this task change.');
        items=result.todos;notice.textContent='Saved locally: '+label+'.';
        section.dispatchEvent(new CustomEvent('local-todo-change',{bubbles:true,detail:{todos:items,summary:summarize(items,today)}}));
        return true;
      }catch(error){
        const unavailable=error instanceof TypeError || error.name==='TimeoutError' || error.name==='AbortError';
        notice.textContent=unavailable?'Local task service unavailable. Reopen a live Coffee or Tea report. Previous tasks are still shown.':'Task save not confirmed: '+error.message+' Previous tasks are still shown.';
        return false;
      }finally{busy=false;render();}
    }
    add.addEventListener('submit',async event=>{
      event.preventDefault();const title=add.querySelector('[name=title]'),due=add.querySelector('[name=due_date]');
      const payload={action:'add',title:title.value,due_date:due.value};if(parentId)payload.parent_id=parentId;
      if(await perform(payload,'task added')){title.value='';parentId=null;showParent();title.focus();}
    });
    const rootButton=section.querySelector('[data-todo-root]');if(rootButton)rootButton.addEventListener('click',()=>{parentId=null;showParent();add.querySelector('[name=title]').focus();});
    list.addEventListener('click',async event=>{
      const button=event.target.closest('[data-todo-action]');if(!button || !list.contains(button))return;
      const row=button.closest('[data-todo-id]'),item=items.find(task=>task.id===row.dataset.todoId);if(!item)return;
      const action=button.dataset.todoAction;
      if(action==='subtask'){if(!enabled || busy)return;parentId=item.id;showParent();add.querySelector('[name=title]').focus();return;}
      if(action==='set_importance'){
        const important=item.important!==true;
        await perform({action,id:item.id,important},important?'task marked high importance':'high importance removed');
        const savedRow=list.querySelector('[data-todo-id="'+item.id+'"]'),savedStar=savedRow && savedRow.querySelector('[data-todo-action="set_importance"]');
        if(savedStar && !savedRow.hidden)savedStar.focus();else filter.focus();return;
      }
      const labels={complete:'task completed',cancel:'task cancelled',reopen:'task reopened',remove:'task removed'};
      const saved=await perform({action,id:item.id},labels[action]);
      if(saved && parentId===item.id && action==='remove'){parentId=null;showParent();}
      filter.focus();
    });
    list.addEventListener('submit',async event=>{
      const form=event.target.closest('[data-todo-reschedule]');if(!form)return;event.preventDefault();
      const row=form.closest('[data-todo-id]');await perform({action:'reschedule',id:row.dataset.todoId,due_date:form.querySelector('[name=due_date]').value},'task rescheduled');filter.focus();
    });
    filter.addEventListener('change',render);
    // Default to outstanding work due by this report date; every other item remains discoverable.
    filter.value='due';render();
  }
  if(typeof module!=='undefined' && module.exports)module.exports={mount,confirmed,summarize,group,orderedTodos};
  if(typeof document!=='undefined')mount(document);
})();
