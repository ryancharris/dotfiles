/* Local task actions change the page only after the store acknowledges them. */
(function () {
  'use strict';
  const statuses=['pending','completed','cancelled'];
  function validItem(item,removed=false){
    return Boolean(item && typeof item.id==='string' && /^[a-f0-9]{32}$/.test(item.id) && typeof item.title==='string' && item.title.trim() && item.title.length<=500 &&
      (statuses.includes(item.status) || (removed && item.status==='removed')) &&
      (item.parent_id==null || (typeof item.parent_id==='string' && /^[a-f0-9]{32}$/.test(item.parent_id))) &&
      (item.important===undefined || typeof item.important==='boolean'));
  }
  function group(item){return item.status;}
  function summarize(items){
    const counts={pending:0,completed:0,cancelled:0};
    items.forEach(item=>{const key=group(item);if(Object.hasOwn(counts,key))counts[key]++;});
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
      (a.created_at||'').localeCompare(b.created_at||'') || a.id.localeCompare(b.id);
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
      if(item.title!==request.title.trim().split(/\s+/).join(' ') || item.status!=='pending' || (item.parent_id||null)!==(request.parent_id||null) || Boolean(item.important)!==Boolean(request.important))return false;
    }else if(request.action==='set_importance'){
      if(typeof request.important!=='boolean' || item.id!==request.id || item.status==='removed' || item.important!==request.important)return false;
    }else{
      const expected={complete:'completed',cancel:'cancelled',reopen:'pending',remove:'removed'}[request.action];
      if(item.id!==request.id || item.status!==expected)return false;
    }
    const saved=result.todos.find(entry=>entry.id===item.id);
    return item.status==='removed' ? !saved : Boolean(saved && saved.title===item.title && saved.status===item.status && (saved.parent_id||null)===(item.parent_id||null) && Boolean(saved.important)===Boolean(item.important));
  }
  function mount(doc,request){
    const section=doc.querySelector('#todos'),configNode=doc.querySelector('#todo-config');
    if(!section || !configNode || section.todoMounted)return;
    section.todoMounted=true;
    const notice=section.querySelector('.todo-status');
    let config;
    try{config=JSON.parse(configNode.textContent);}catch(error){notice.textContent='Local tasks unavailable. Reopen a live Coffee or Tea report.';return;}
    const save=request || (typeof fetch==='function'?fetch:null),enabled=Boolean(config.endpoint && config.token && save);
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
      const totals=summarize(items);
      counts.textContent=totals.pending+' open · '+totals.completed+' completed · '+totals.cancelled+' cancelled';
      const byId=new Map(items.map(item=>[item.id,item])),matching=new Set(),visibleIds=new Set(),nodes=new Map();
      items.forEach(item=>{const key=group(item);if(filter.value==='all' || filter.value===key)matching.add(item.id);});
      matching.forEach(id=>{const seen=new Set();while(byId.has(id) && !seen.has(id)){seen.add(id);visibleIds.add(id);id=byId.get(id).parent_id;}});
      const ordered=orderedTodos(items,matching);
      ordered.forEach(item=>{
        const key=group(item),row=element('li',undefined,'todo-row');row.dataset.todoId=item.id;row.dataset.todoGroup=key;
        row.dataset.todoImportant=String(item.important===true);
        row.hidden=!visibleIds.has(item.id);
        const copy=element('div',undefined,'todo-copy');copy.append(element('b',item.title,'todo-title'));
        if(visibleIds.has(item.id) && !matching.has(item.id))copy.append(element('span','Parent task context','todo-context-note'));
        copy.append(element('span',{pending:'Open',completed:'Completed',cancelled:'Cancelled'}[key],'todo-meta'));
        const actions=element('div',undefined,'todo-actions'),star=actionButton(item.important===true?'⭐️':'☆','set_importance');star.className='todo-star';
        const starLabel=item.important===true?'Remove high importance':'Mark high importance';star.title=starLabel;star.setAttribute('aria-label',starLabel);star.setAttribute('aria-pressed',String(item.important===true));actions.append(star);
        actions.append(actionButton(item.status==='pending'?'Complete':'Reopen',item.status==='pending'?'complete':'reopen'));
        actions.append(actionButton('Add subtask','subtask'));
        const details=element('details'),summary=element('summary','Manage'),manage=element('div',undefined,'todo-manage');
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
        section.dispatchEvent(new CustomEvent('local-todo-change',{bubbles:true,detail:{todos:items,summary:summarize(items)}}));
        return true;
      }catch(error){
        const unavailable=error instanceof TypeError || error.name==='TimeoutError' || error.name==='AbortError';
        notice.textContent=unavailable?'Local task service unavailable. Reopen a live Coffee or Tea report. Previous tasks are still shown.':'Task save not confirmed: '+error.message+' Previous tasks are still shown.';
        return false;
      }finally{busy=false;render();}
    }
    add.addEventListener('submit',async event=>{
      event.preventDefault();const title=add.querySelector('[name=title]');
      const payload={action:'add',title:title.value};if(parentId)payload.parent_id=parentId;
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
    filter.addEventListener('change',render);
    // Open tasks remain visible across reports and day changes until explicitly closed.
    filter.value='pending';render();
  }
  if(typeof module!=='undefined' && module.exports)module.exports={mount,confirmed,summarize,group,orderedTodos};
  if(typeof document!=='undefined')mount(document);
})();
