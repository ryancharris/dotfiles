/* Local task actions change the page only after the store acknowledges them. */
(function () {
  'use strict';
  const statuses=['pending','completed','cancelled'];
  const tagKey=value=>value.toLowerCase();
  function parseTags(value){
    const seen=new Set();
    return value.split(',').map(tag=>tag.trim().split(/\s+/).join(' ')).filter(tag=>{
      const key=tagKey(tag);if(!tag || seen.has(key))return false;seen.add(key);return true;
    });
  }
  const tagsOf=item=>item.project_tags||[];
  const sameTags=(a,b)=>JSON.stringify(tagsOf(a))===JSON.stringify(tagsOf(b));
  const matchesProject=(item,project)=>!project || (project==='__untagged__'?tagsOf(item).length===0:tagsOf(item).some(tag=>tagKey(tag)===tagKey(project.slice(4))));
  function validItem(item,removed=false){
    return Boolean(item && typeof item.id==='string' && /^[a-f0-9]{32}$/.test(item.id) && typeof item.title==='string' && item.title.trim() && item.title.length<=500 &&
      (statuses.includes(item.status) || (removed && item.status==='removed')) &&
      (item.parent_id==null || (typeof item.parent_id==='string' && /^[a-f0-9]{32}$/.test(item.parent_id))) &&
      (item.important===undefined || typeof item.important==='boolean') &&
      (item.project_tags===undefined || (Array.isArray(item.project_tags) && item.project_tags.length<=10 && item.project_tags.every(tag=>typeof tag==='string' && tag.trim() && [...tag].length<=60 && !/[,\u0000-\u001f\u007f-\u009f]/.test(tag)))));
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
  function validArchive(archive){
    return Array.isArray(archive) && archive.every(item=>validItem(item) && /^[a-f0-9]{32}$/.test(item.batch_id) && typeof item.cleared_at==='string' && Number.isFinite(Date.parse(item.cleared_at))) && new Set(archive.map(item=>item.id)).size===archive.length;
  }
  function confirmed(request,result,previousArchive=[]){
    if(!result || result.ok!==true || !Array.isArray(result.todos) || !result.todos.every(item=>validItem(item)))return false;
    if(new Set(result.todos.map(item=>item.id)).size!==result.todos.length)return false;
    if(result.archive!==undefined && (!validArchive(result.archive) || result.archive.some(item=>result.todos.some(active=>active.id===item.id))))return false;
    if(['clear','remove','restore','undo'].includes(request.action) && !validArchive(result.archive))return false;
    if(['restore','undo'].includes(request.action)){
      const ids=request.action==='restore'?[request.id]:previousArchive.filter(item=>item.batch_id===request.id).map(item=>item.id);
      return ids.length>0 && result.batch_id===(request.action==='undo'?request.id:previousArchive.find(item=>item.id===request.id)?.batch_id) &&
        Array.isArray(result.restored_ids) && result.restored_ids.length===ids.length && new Set(result.restored_ids).size===ids.length &&
        ids.every(id=>result.restored_ids.includes(id) && result.todos.some(item=>item.id===id) && !result.archive.some(item=>item.id===id));
    }
    if(request.action==='clear'){
      if(!['all',...statuses].includes(request.status) || result.status!==request.status ||
        !Array.isArray(request.ids) || !request.ids.length || !request.ids.every(id=>typeof id==='string' && /^[a-f0-9]{32}$/.test(id)) || new Set(request.ids).size!==request.ids.length ||
        !Array.isArray(result.removed_ids) || result.removed_ids.length!==request.ids.length ||
        new Set(result.removed_ids).size!==request.ids.length)return false;
      return request.ids.every(id=>result.removed_ids.includes(id) && !result.todos.some(item=>item.id===id) && result.archive.some(item=>item.id===id && item.batch_id===result.batch_id));
    }
    if(!validItem(result.item,true))return false;
    const item=result.item;
    if(request.action==='add'){
      if(item.title!==request.title.trim().split(/\s+/).join(' ') || item.status!=='pending' || (item.parent_id||null)!==(request.parent_id||null) || Boolean(item.important)!==Boolean(request.important))return false;
      if(request.project_tags!==undefined && !sameTags(item,{project_tags:parseTags(request.project_tags.join(','))}))return false;
    }else if(request.action==='set_importance'){
      if(typeof request.important!=='boolean' || item.id!==request.id || item.status==='removed' || item.important!==request.important)return false;
    }else if(request.action==='set_project_tags'){
      if(!Array.isArray(request.project_tags) || item.id!==request.id || item.status==='removed' || !sameTags(item,{project_tags:parseTags(request.project_tags.join(','))}))return false;
    }else{
      const expected={complete:'completed',cancel:'cancelled',reopen:'pending',remove:'removed'}[request.action];
      if(item.id!==request.id || item.status!==expected)return false;
    }
    const saved=result.todos.find(entry=>entry.id===item.id);
    return item.status==='removed' ? !saved && result.archive.some(entry=>entry.id===item.id && entry.batch_id===result.batch_id) : Boolean(saved && saved.title===item.title && saved.status===item.status && (saved.parent_id||null)===(item.parent_id||null) && Boolean(saved.important)===Boolean(item.important) && sameTags(saved,item));
  }
  function mount(doc,request){
    const section=doc.querySelector('#todos'),configNode=doc.querySelector('#todo-config');
    if(!section || !configNode || section.todoMounted)return;
    section.todoMounted=true;
    const notice=section.querySelector('.todo-status');
    let config;
    try{config=JSON.parse(configNode.textContent);}catch(error){notice.textContent='Local tasks unavailable. Reopen a live Coffee or Tea report.';return;}
    const save=request || (typeof fetch==='function'?fetch:null),enabled=Boolean(config.endpoint && config.token && save);
    let items=Array.isArray(config.todos)?config.todos.filter(item=>validItem(item)):[],archive=validArchive(config.archive)?config.archive:[],busy=false,subtaskParentId=null,projectEditorId=null,activeFilter='pending',activeProject='';
    const list=section.querySelector('.todo-list'),tabs=Array.from(section.querySelectorAll('[data-todo-filter]')),panel=section.querySelector('#todo-panel'),clearView=section.querySelector('[data-todo-clear-view]'),empty=section.querySelector('.todo-empty'),counts=section.querySelector('.todo-counts'),add=section.querySelector('.todo-add');
    const undo=section.querySelector('[data-todo-undo]'),undoNotice=section.querySelector('.todo-undo');
    const projectFilter=section.querySelector('[data-todo-project-filter]'),projectOptions=section.querySelector('#todo-project-options');
    const labels={pending:'Open',completed:'Completed',cancelled:'Cancelled',all:'All tasks',archive:'Archived'};
    const focusFilter=()=>tabs.find(tab=>tab.dataset.todoFilter===activeFilter)?.focus();
    const element=(tag,text,className)=>{const node=doc.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
    const actionButton=(label,action)=>{const node=element('button',label);node.type='button';node.dataset.todoAction=action;node.disabled=!enabled || busy;return node;};
    const subtaskDrafts=new Map();
    const projectDrafts=new Map();
    function captureProjectDraft(){
      const form=list.querySelector('.todo-project-form');
      if(form)projectDrafts.set(form.dataset.todoProject,form.querySelector('[name=project_tags]').value);
    }
    function focusProjects(id){
      const form=list.querySelector('[data-todo-project="'+id+'"]');
      if(form && !form.closest('[data-todo-id]').hidden)form.querySelector('[name=project_tags]').focus();
      else if(projectFilter)projectFilter.focus();
    }
    function dismissProjects(){
      if(!projectEditorId || busy)return;
      const id=projectEditorId;projectDrafts.delete(id);projectEditorId=null;render(true,false);
      const row=list.querySelector('[data-todo-id="'+id+'"]');
      if(row && !row.hidden)row.querySelector('[data-todo-action=projects]').focus();else focusFilter();
    }
    function projectForm(item){
      const form=element('form',undefined,'todo-project-form');form.dataset.todoProject=item.id;
      const label=element('label','Project tags for '+item.title),input=element('input');
      input.id='todo-project-tags-'+item.id;label.setAttribute('for',input.id);
      input.name='project_tags';input.type='text';input.maxLength=700;input.placeholder='e.g. Transport, PrivateLink';
      input.setAttribute('list','todo-project-options');input.setAttribute('aria-describedby','todo-project-help');
      input.value=projectDrafts.has(item.id)?projectDrafts.get(item.id):tagsOf(item).join(', ');input.disabled=!enabled || busy;
      input.addEventListener('input',()=>projectDrafts.set(item.id,input.value));
      const submit=element('button','Save tags');submit.type='submit';submit.disabled=!enabled || busy;
      const cancel=element('button','Cancel');cancel.type='button';cancel.dataset.todoDismissProjects='';cancel.disabled=busy;
      form.append(label,input,submit,cancel);
      form.addEventListener('submit',async event=>{
        event.preventDefault();if(!enabled || busy)return;
        projectDrafts.set(item.id,input.value);
        if(await perform({action:'set_project_tags',id:item.id,project_tags:parseTags(input.value)},'project tags saved')){
          projectDrafts.delete(item.id);projectEditorId=null;render(true,false);
          const row=list.querySelector('[data-todo-id="'+item.id+'"]');
          if(row && !row.hidden)row.querySelector('[data-todo-action=projects]').focus();else if(projectFilter)projectFilter.focus();
        }else focusProjects(item.id);
      });
      return form;
    }
    function renderProjectOptions(){
      const known=new Map();[...items,...archive].forEach(item=>tagsOf(item).forEach(tag=>{if(!known.has(tagKey(tag)))known.set(tagKey(tag),tag);}));
      const names=[...known.values()].sort((a,b)=>a.localeCompare(b));
      if(projectOptions){projectOptions.replaceChildren();names.forEach(name=>{const option=element('option');option.value=name;projectOptions.append(option);});}
      if(projectFilter){
        if(activeProject.startsWith('tag:') && known.has(tagKey(activeProject.slice(4))))activeProject='tag:'+known.get(tagKey(activeProject.slice(4)));
        projectFilter.replaceChildren();
        [['','All projects'],['__untagged__','Untagged'],...names.map(name=>['tag:'+name,name])].forEach(([value,label])=>{const option=element('option',label);option.value=value;projectFilter.append(option);});
        // Keep an empty selected project accessible after its last task is retagged or cleared.
        if(activeProject && activeProject!=='__untagged__' && !known.has(tagKey(activeProject.slice(4)))){const option=element('option',activeProject.slice(4));option.value=activeProject;projectFilter.append(option);}
        projectFilter.value=activeProject;projectFilter.disabled=busy;
      }
    }
    function captureSubtaskDraft(){
      const form=list.querySelector('.todo-subtask-form');
      if(form && form.dataset.todoSubtask===subtaskParentId)subtaskDrafts.set(form.dataset.todoSubtask,form.querySelector('[name=title]').value);
    }
    function focusSubtask(parentId){
      const form=list.querySelector('[data-todo-subtask="'+parentId+'"]');
      if(form && !form.closest('[data-todo-id]').hidden)form.querySelector('[name=title]').focus();
    }
    function dismissSubtask(){
      const parentId=subtaskParentId;if(!parentId || busy)return;
      subtaskDrafts.delete(parentId);subtaskParentId=null;render(false);
      const row=list.querySelector('[data-todo-id="'+parentId+'"]');
      if(row && !row.hidden)row.querySelector('[data-todo-action=subtask]').focus();else focusFilter();
    }
    function subtaskForm(item){
      const form=element('form',undefined,'todo-subtask-form');form.dataset.todoSubtask=item.id;
      const label=element('label','Subtask of '+item.title),input=element('input');
      input.id='todo-subtask-title-'+item.id;label.setAttribute('for',input.id);
      input.name='title';input.type='text';input.required=true;input.maxLength=500;input.placeholder='Add a subtask';
      input.value=subtaskDrafts.get(item.id)||'';input.disabled=!enabled || busy;
      input.addEventListener('input',()=>subtaskDrafts.set(item.id,input.value));
      const submit=element('button','Add subtask');submit.type='submit';submit.disabled=!enabled || busy;
      const cancel=element('button','Cancel');cancel.type='button';cancel.dataset.todoDismissSubtask='';
      cancel.setAttribute('aria-label','Cancel adding subtask');cancel.disabled=busy;
      form.append(label,input,submit,cancel);
      form.addEventListener('submit',async event=>{
        event.preventDefault();if(!enabled || busy || !input.value.trim())return;
        const title=input.value;subtaskDrafts.set(item.id,title);
        if(await perform({action:'add',title,parent_id:item.id},'subtask added')){
          subtaskDrafts.set(item.id,'');
          // An open child belongs in Open even when its parent was completed or cancelled.
          if(!['pending','all'].includes(activeFilter))activeFilter='pending';render(false);
        }
        focusSubtask(item.id);
      });
      return form;
    }
    function render(captureDraft=true,captureTags=true){
      if(captureDraft)captureSubtaskDraft();if(captureTags)captureProjectDraft();
      list.replaceChildren();
      renderProjectOptions();
      const totals=summarize(items);
      counts.textContent=totals.pending+' open · '+totals.completed+' completed · '+totals.cancelled+' cancelled · '+archive.length+' archived';
      const archived=activeFilter==='archive',shown=archived?archive:items;
      const byId=new Map(shown.map(item=>[item.id,item])),matching=new Set(),visibleIds=new Set(),nodes=new Map();
      shown.forEach(item=>{const key=group(item);if((archived || activeFilter==='all' || activeFilter===key) && matchesProject(item,activeProject))matching.add(item.id);});
      tabs.forEach(tab=>{
        const key=tab.dataset.todoFilter,selected=key===activeFilter;
        tab.textContent=labels[key]+' ('+(key==='archive'?archive.length:key==='all'?items.length:totals[key])+')';
        tab.setAttribute('aria-selected',String(selected));tab.setAttribute('tabindex',selected?'0':'-1');tab.disabled=busy;
      });
      if(panel)panel.setAttribute('aria-labelledby','todo-tab-'+activeFilter);
      if(clearView){
        clearView.hidden=archived;clearView.disabled=!enabled || busy || archived || matching.size===0;
        clearView.setAttribute('aria-label','Clear '+matching.size+' tasks in '+labels[activeFilter]);
        clearView.title='Move tasks in this tab to the archive. You can undo or restore them later.';
      }
      if(undoNotice)undoNotice.hidden=archive.length===0;
      if(undo){undo.disabled=!enabled || busy || !archive.length;const count=archive.filter(item=>item.batch_id===archive[0]?.batch_id).length;undo.textContent='Undo last clear ('+count+')';}
      if(undoNotice && archive.length)undoNotice.querySelector('span').textContent='Cleared tasks are saved in Archived.';
      matching.forEach(id=>{const seen=new Set();while(byId.has(id) && !seen.has(id)){seen.add(id);visibleIds.add(id);id=byId.get(id).parent_id;}});
      const ordered=archived?shown:orderedTodos(items,matching);
      ordered.forEach(item=>{
        const key=group(item),row=element('li',undefined,'todo-row');row.dataset.todoId=item.id;row.dataset.todoGroup=key;
        row.dataset.todoImportant=String(item.important===true);
        row.hidden=!visibleIds.has(item.id);
        const copy=element('div',undefined,'todo-copy');copy.append(element('b',item.title,'todo-title'));
        if(visibleIds.has(item.id) && !matching.has(item.id))copy.append(element('span','Parent task context','todo-context-note'));
        copy.append(element('span',{pending:'Open',completed:'Completed',cancelled:'Cancelled'}[key],'todo-meta'));
        if(tagsOf(item).length){const tags=element('div',undefined,'todo-project-tags');tagsOf(item).forEach(tag=>tags.append(element('span',tag,'todo-project-tag')));copy.append(tags);}
        const actions=element('div',undefined,'todo-actions');
        if(archived){copy.append(element('span','Cleared '+new Date(item.cleared_at).toLocaleString('en-GB',{timeZone:config.timezone||'UTC',hour12:false}),'todo-meta'));actions.append(actionButton('Restore','restore'));}
        else {
        const star=actionButton(item.important===true?'⭐️':'☆','set_importance');star.className='todo-star';
        const starLabel=item.important===true?'Remove high importance':'Mark high importance';star.title=starLabel;star.setAttribute('aria-label',starLabel);star.setAttribute('aria-pressed',String(item.important===true));actions.append(star);
        actions.append(actionButton(item.status==='pending'?'Complete':'Reopen',item.status==='pending'?'complete':'reopen'));
        const cancelSlot=element('span',undefined,'todo-cancel-slot');
        if(item.status!=='cancelled')cancelSlot.append(actionButton('Cancel','cancel'));else cancelSlot.setAttribute('aria-hidden','true');
        actions.append(cancelSlot,actionButton('Add subtask','subtask'));
        const projects=actionButton('Projects','projects');projects.setAttribute('aria-expanded',String(projectEditorId===item.id));projects.setAttribute('aria-label','Edit project tags for '+item.title);actions.append(projects);
        const clear=actionButton('Clear','remove');clear.title='Clear this task; keep its subtasks';clear.setAttribute('aria-label','Clear task: '+item.title);actions.append(clear);
        }
        const entry=element('div',undefined,'todo-entry'),children=element('ul',undefined,'todo-children');entry.append(copy,actions);row.append(entry);
        if(!archived && subtaskParentId===item.id)row.append(subtaskForm(item));
        if(!archived && projectEditorId===item.id)row.append(projectForm(item));
        row.append(children);nodes.set(item.id,{row,children});
      });
      ordered.forEach(item=>{const parent=archived?null:nodes.get(item.parent_id);(parent && item.parent_id!==item.id?parent.children:list).append(nodes.get(item.id).row);});
      nodes.forEach(node=>{node.children.hidden=node.children.children.length===0;});
      empty.hidden=matching.size>0;empty.textContent=activeProject?'No tasks match this project and status.':archived?'No archived tasks. Cleared tasks will appear here.':items.length?'No tasks in this tab. Choose All tasks to see the rest.':'No tasks yet. Add one above.';
      section.querySelectorAll('.todo-add input,.todo-add button').forEach(node=>{node.disabled=!enabled || busy;});
    }
    async function perform(payload,label){
      if(!enabled || busy)return false;
      busy=true;section.todoBusy=true;notice.textContent='Saving '+label+'…';section.querySelectorAll('input,button,select').forEach(node=>{node.disabled=true;});
      try{
        const response=await save(config.endpoint,{method:'POST',credentials:'omit',signal:AbortSignal.timeout(10000),headers:{'Content-Type':'application/json','X-Brief-Token':config.token},body:JSON.stringify(payload)});
        const result=await response.json();
        if(!response.ok || result.ok!==true)throw Error(result.error || 'The task could not be saved.');
        if(!confirmed(payload,result,archive))throw Error('The local server did not confirm this task change.');
        items=result.todos;archive=result.archive||archive;
        if(subtaskParentId && !items.some(item=>item.id===subtaskParentId)){subtaskDrafts.delete(subtaskParentId);subtaskParentId=null;}
        if(projectEditorId && !items.some(item=>item.id===projectEditorId)){projectDrafts.delete(projectEditorId);projectEditorId=null;}
        notice.textContent='Saved locally: '+label+'.';
        section.dispatchEvent(new CustomEvent('local-todo-change',{bubbles:true,detail:{todos:items,archive,summary:summarize(items)}}));
        return true;
      }catch(error){
        const unavailable=error instanceof TypeError || error.name==='TimeoutError' || error.name==='AbortError';
        notice.textContent=unavailable?'Local task service unavailable. Reopen a live Coffee or Tea report. Previous tasks are still shown.':'Task save not confirmed: '+error.message+' Previous tasks are still shown.';
        return false;
      }finally{busy=false;section.todoBusy=false;render();}
    }
    add.addEventListener('submit',async event=>{
      event.preventDefault();const title=add.querySelector('[name=title]');
      const projects=add.querySelector('[name=project_tags]'),payload={action:'add',title:title.value};
      if(projects)payload.project_tags=parseTags(projects.value);
      if(await perform(payload,'task added')){title.value='';if(projects)projects.value='';title.focus();}
    });
    if(projectFilter)projectFilter.addEventListener('change',()=>{if(busy)return;activeProject=projectFilter.value;render();projectFilter.focus();});
    list.addEventListener('keydown',event=>{
      if(event.key==='Escape' && event.target.closest('.todo-subtask-form')){event.preventDefault();dismissSubtask();}
      if(event.key==='Escape' && event.target.closest('.todo-project-form')){event.preventDefault();dismissProjects();}
    });
    list.addEventListener('click',async event=>{
      const dismiss=event.target.closest('[data-todo-dismiss-subtask]');
      if(dismiss && list.contains(dismiss)){dismissSubtask();return;}
      const dismissTags=event.target.closest('[data-todo-dismiss-projects]');
      if(dismissTags && list.contains(dismissTags)){dismissProjects();return;}
      const button=event.target.closest('[data-todo-action]');if(!button || !list.contains(button))return;
      const row=button.closest('[data-todo-id]'),item=(activeFilter==='archive'?archive:items).find(task=>task.id===row.dataset.todoId);if(!item)return;
      const action=button.dataset.todoAction;
      if(action==='restore'){if(await perform({action,id:item.id},'task restored'))activeFilter=item.status;render();focusFilter();return;}
      if(action==='subtask'){if(!enabled || busy)return;captureSubtaskDraft();subtaskParentId=item.id;render();focusSubtask(item.id);return;}
      if(action==='projects'){if(!enabled || busy)return;captureProjectDraft();if(projectEditorId===item.id){dismissProjects();return;}projectEditorId=item.id;render();focusProjects(item.id);return;}
      if(action==='set_importance'){
        const important=item.important!==true;
        await perform({action,id:item.id,important},important?'task marked high importance':'high importance removed');
        const savedRow=list.querySelector('[data-todo-id="'+item.id+'"]'),savedStar=savedRow && savedRow.querySelector('[data-todo-action="set_importance"]');
        if(savedStar && !savedRow.hidden)savedStar.focus();else focusFilter();return;
      }
      const labels={complete:'task completed',cancel:'task cancelled',reopen:'task reopened',remove:'task cleared'};
      await perform({action,id:item.id},labels[action]);
      focusFilter();
    });
    tabs.forEach((tab,index)=>{
      function select(){if(busy)return;activeFilter=tab.dataset.todoFilter;render();focusFilter();}
      tab.addEventListener('click',select);
      tab.addEventListener('keydown',event=>{
        const target={ArrowRight:(index+1)%tabs.length,ArrowLeft:(index+tabs.length-1)%tabs.length,Home:0,End:tabs.length-1}[event.key];
        if(target===undefined || busy)return;
        event.preventDefault();activeFilter=tabs[target].dataset.todoFilter;render();focusFilter();
      });
    });
    if(clearView)clearView.addEventListener('click',async()=>{
      if(!enabled || busy || activeFilter==='archive')return;
      const ids=items.filter(item=>(activeFilter==='all' || item.status===activeFilter) && matchesProject(item,activeProject)).map(item=>item.id);
      if(!ids.length)return;
      if(!doc.defaultView?.confirm('Clear '+ids.length+' '+(ids.length===1?'task':'tasks')+' from '+labels[activeFilter]+(activeProject?' / '+(activeProject==='__untagged__'?'Untagged':activeProject.slice(4)):'')+'? They will move to Archived. You can undo this.')){focusFilter();return;}
      await perform({action:'clear',ids,status:activeFilter},ids.length+' '+(ids.length===1?'task':'tasks')+' cleared');
      focusFilter();
    });
    if(undo)undo.addEventListener('click',async()=>{
      if(!archive.length)return;const latest=archive[0],target=latest.status;
      if(await perform({action:'undo',id:latest.batch_id},'clear undone'))activeFilter=target;
      render();focusFilter();
    });
    // Open tasks remain visible across reports and day changes until explicitly closed.
    section.applyConfirmedTasks=result=>{
      if(busy || result?.ok!==true || !Array.isArray(result.todos) || !result.todos.every(item=>validItem(item)) || (result.archive!==undefined && !validArchive(result.archive)))return false;
      items=result.todos;archive=result.archive||archive;render();return true;
    };
    render();
  }
  if(typeof module!=='undefined' && module.exports)module.exports={mount,confirmed,summarize,group,orderedTodos,parseTags,matchesProject};
  if(typeof document!=='undefined')mount(document);
})();
