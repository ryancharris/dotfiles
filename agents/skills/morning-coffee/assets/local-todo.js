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
      (item.position===undefined || (Number.isSafeInteger(item.position) && item.position>=0)) &&
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
    const manual=items.some(item=>Number.isSafeInteger(item.position));
    const compare=(a,b)=>(manual ? (a.position ?? Infinity)-(b.position ?? Infinity) : Number(!importantGroups.has(a.id))-Number(!importantGroups.has(b.id))) ||
      (a.created_at||'').localeCompare(b.created_at||'') || a.id.localeCompare(b.id);
    children.forEach(siblings=>siblings.sort(compare));
    const ordered=[],stack=[...(children.get(null)||[])].reverse(),seen=new Set();
    while(stack.length){const item=stack.pop();if(seen.has(item.id))continue;seen.add(item.id);ordered.push(item);stack.push(...[...(children.get(item.id)||[])].reverse());}
    return ordered;
  }
  const topology=items=>orderedTodos(items).map(item=>[item.id,item.parent_id||null]);
  function moveOrder(items,request){
    if(!Array.isArray(items) || !request || !['before','after','inside','root-end'].includes(request.placement))return null;
    const ordered=orderedTodos(items),byId=new Map(items.map(item=>[item.id,item]));
    if(ordered.length!==items.length || byId.size!==items.length || !byId.has(request.id))return null;
    if(request.placement==='root-end' ? request.target_id!==null : !byId.has(request.target_id))return null;
    const descends=(item,id)=>{
      const seen=new Set();let current=item;
      while(current && !seen.has(current.id)){if(current.id===id)return true;seen.add(current.id);current=byId.get(current.parent_id);}
      return false;
    };
    const moving=byId.get(request.id),moved=ordered.filter(item=>descends(item,moving.id)),ids=new Set(moved.map(item=>item.id));
    if(ids.has(request.target_id))return null;
    const remaining=ordered.filter(item=>!ids.has(item.id)),target=byId.get(request.target_id);
    const parent=request.placement==='root-end'?null:request.placement==='inside'?target.id:target.parent_id||null;
    let index=request.placement==='root-end'?remaining.length:remaining.findIndex(item=>item.id===target.id);
    if(request.placement==='after' || request.placement==='inside'){
      index++;while(index<remaining.length && descends(remaining[index],target.id))index++;
    }
    const rows=remaining.slice();rows.splice(index,0,...moved.map(item=>item.id===moving.id?{...item,parent_id:parent}:item));
    const before=ordered.map(item=>[item.id,item.parent_id||null]),after=rows.map(item=>[item.id,item.parent_id||null]);
    return {rows,order:after,parent,previousParent:moving.parent_id||null,movedIds:[...ids],changed:JSON.stringify(before)!==JSON.stringify(after)};
  }
  function moveConfirmed(request,result,previous){
    const expected=moveOrder(previous,request);
    if(!expected || JSON.stringify(request.base_order)!==JSON.stringify(topology(previous)) || !result || !Array.isArray(result.todos) || result.todos.length!==previous.length || !result.todos.every(item=>validItem(item)) || new Set(result.todos.map(item=>item.id)).size!==previous.length)return false;
    const echo=result.move;
    if(!echo || echo.target_id!==request.target_id || echo.placement!==request.placement || echo.previous_parent_id!==expected.previousParent || echo.parent_id!==expected.parent)return false;
    if(JSON.stringify(topology(result.todos))!==JSON.stringify(expected.order))return false;
    const before=new Map(previous.map(item=>[item.id,item]));
    if(!result.todos.every(item=>{
      const original=before.get(item.id);if(!original)return false;
      const parent=item.id===request.id?expected.parent:original.parent_id||null;
      const rank=expected.changed?expected.order.findIndex(row=>row[0]===item.id):original.position;
      return (item.parent_id||null)===parent && item.position===rank;
    }))return false;
    const saved=result.todos.find(item=>item.id===request.id);
    return Boolean(saved && validItem(result.item) && ['id','title','status','position','created_at','updated_at'].every(key=>result.item[key]===saved[key]) &&
      (result.item.parent_id||null)===(saved.parent_id||null) && Boolean(result.item.important)===Boolean(saved.important) && sameTags(result.item,saved));
  }
  function validArchive(archive){
    return Array.isArray(archive) && archive.every(item=>validItem(item) && /^[a-f0-9]{32}$/.test(item.batch_id) && typeof item.cleared_at==='string' && Number.isFinite(Date.parse(item.cleared_at))) && new Set(archive.map(item=>item.id)).size===archive.length;
  }
  function confirmed(request,result,previousArchive=[],previousItems=[]){
    if(!result || result.ok!==true || !Array.isArray(result.todos) || !result.todos.every(item=>validItem(item)))return false;
    if(new Set(result.todos.map(item=>item.id)).size!==result.todos.length)return false;
    if(result.archive!==undefined && (!validArchive(result.archive) || result.archive.some(item=>result.todos.some(active=>active.id===item.id))))return false;
    if(request.action==='move')return moveConfirmed(request,result,previousItems) && (result.archive===undefined || JSON.stringify(result.archive)===JSON.stringify(previousArchive));
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
    }else if(request.action==='edit'){
      if(item.id!==request.id || item.status==='removed' || item.title!==request.title.trim().split(/\s+/).join(' '))return false;
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
    try{config=JSON.parse(configNode.textContent);}catch(error){notice.textContent='Local tasks unavailable. Reopen the live Morning Coffee workspace.';return;}
    const save=request || (typeof fetch==='function'?fetch:null),enabled=Boolean(config.endpoint && config.token && save);
    let items=Array.isArray(config.todos)?config.todos.filter(item=>validItem(item)):[],archive=validArchive(config.archive)?config.archive:[],busy=false,subtaskParentId=null,projectEditorId=null,editId=null,moveId=null,activeFilter='pending',activeProject='',drag=null,dragFrame=null,suppressDragClick=false;
    const list=section.querySelector('.todo-list'),tabs=Array.from(section.querySelectorAll('[data-todo-filter]')),panel=section.querySelector('#todo-panel'),clearView=section.querySelector('[data-todo-clear-view]'),empty=section.querySelector('.todo-empty'),counts=section.querySelector('.todo-counts'),add=section.querySelector('.todo-add');
    const undo=section.querySelector('[data-todo-undo]'),undoNotice=section.querySelector('.todo-undo');
    const projectFilter=section.querySelector('[data-todo-project-filter]'),projectOptions=section.querySelector('#todo-project-options');
    const view=doc.defaultView,moveDrafts=new Map();
    const moveHelp=doc.createElement('p');moveHelp.className='todo-move-help';
    moveHelp.textContent='Drag the handle to reorder. Drop on a task to nest; drop between tasks or at top level to unnest.';
    const moveNotice=doc.createElement('p');moveNotice.className='todo-move-status';moveNotice.setAttribute('role','status');moveNotice.setAttribute('aria-live','polite');
    const rootDrop=doc.createElement('div');rootDrop.className='todo-root-drop';rootDrop.dataset.todoRootDrop='';rootDrop.textContent='Drop here to move to the end of top-level tasks';rootDrop.hidden=true;
    if(typeof list.before==='function')list.before(moveHelp);else section.append(moveHelp);
    if(typeof list.after==='function')list.after(rootDrop,moveNotice);else section.append(rootDrop,moveNotice);
    const labels={pending:'Open',completed:'Completed',cancelled:'Cancelled',all:'All tasks',archive:'Archived'};
    const focusFilter=()=>tabs.find(tab=>tab.dataset.todoFilter===activeFilter)?.focus();
    const focusMore=row=>row.querySelector('.todo-more > summary')?.focus();
    function closeMenus(except=null){
      list.querySelectorAll('.todo-more').forEach(menu=>{if(menu!==except)menu.open=false;});
    }
    const element=(tag,text,className)=>{const node=doc.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
    const actionButton=(label,action)=>{const node=element('button',label);node.type='button';node.dataset.todoAction=action;node.disabled=!enabled || busy;return node;};
    const subtaskDrafts=new Map();
    const projectDrafts=new Map();
    const projectPickerDrafts=new Map();
    const editDrafts=new Map();
    function captureEditDraft(){
      const form=list.querySelector('.todo-edit-form');
      if(form && form.dataset.todoEdit===editId){const draft=editDrafts.get(editId);if(draft)draft.title=form.querySelector('[name=title]').value;}
    }
    function focusEdit(id){
      const form=list.querySelector('[data-todo-edit="'+id+'"]');
      if(form && !form.closest('[data-todo-id]').hidden)form.querySelector('[name=title]').focus();else focusFilter();
    }
    function dismissEdit(){
      if(!editId || busy)return;
      const id=editId;editDrafts.delete(id);editId=null;render();
      const row=list.querySelector('[data-todo-id="'+id+'"]');if(row && !row.hidden)focusMore(row);else focusFilter();
    }
    function editForm(item){
      const form=element('form',undefined,'todo-edit-form');form.dataset.todoEdit=item.id;
      const draft=editDrafts.get(item.id),label=element('label','Edit task'),input=element('input');
      input.id='todo-edit-title-'+item.id;label.setAttribute('for',input.id);
      input.name='title';input.type='text';input.maxLength=500;input.required=true;input.value=draft.title;input.disabled=!enabled || busy;
      input.addEventListener('input',()=>{draft.title=input.value;});
      const submit=element('button','Save changes');submit.type='submit';submit.disabled=!enabled || busy;
      const cancel=element('button','Cancel');cancel.type='button';cancel.dataset.todoDismissEdit='';cancel.disabled=busy;cancel.setAttribute('aria-label','Cancel editing task');
      form.append(label,input,submit,cancel);
      form.addEventListener('submit',async event=>{
        event.preventDefault();if(!enabled || busy)return;
        draft.title=input.value;
        if(await perform({action:'edit',id:item.id,title:draft.title,base_title:draft.baseTitle},'task updated'))dismissEdit();
        else focusEdit(item.id);
      });
      return form;
    }
    function captureProjectDraft(){
      const form=list.querySelector('.todo-project-form');
      if(form){const input=form.querySelector('[name=project_tags]');projectDrafts.set(form.dataset.todoProject,input.value);if(input.tagPicker)projectPickerDrafts.set(form.dataset.todoProject,input.tagPicker.getDraft());}
    }
    function focusProjects(id){
      const form=list.querySelector('[data-todo-project="'+id+'"]');
      if(form && !form.closest('[data-todo-id]').hidden){const input=form.querySelector('[name=project_tags]');if(input.tagPicker)input.tagPicker.focus();else input.focus();}
      else if(projectFilter)projectFilter.focus();
    }
    function dismissProjects(){
      if(!projectEditorId || busy)return;
      const id=projectEditorId;projectDrafts.delete(id);projectPickerDrafts.delete(id);projectEditorId=null;render(true,false);
      const row=list.querySelector('[data-todo-id="'+id+'"]');
      if(row && !row.hidden)focusMore(row);else focusFilter();
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
        if(input.tagPicker && !input.tagPicker.commit())return;
        projectDrafts.set(item.id,input.value);
        if(await perform({action:'set_project_tags',id:item.id,project_tags:parseTags(input.value)},'project tags saved')){
          projectDrafts.delete(item.id);projectPickerDrafts.delete(item.id);projectEditorId=null;render(true,false);
          const row=list.querySelector('[data-todo-id="'+item.id+'"]');
          if(row && !row.hidden)focusMore(row);else if(projectFilter)projectFilter.focus();
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
    function revealAdded(item){
      if(!['pending','all'].includes(activeFilter))activeFilter='pending';
      if(!matchesProject(item,activeProject))activeProject='';
    }
    function dismissSubtask(){
      const parentId=subtaskParentId;if(!parentId || busy)return;
      subtaskDrafts.delete(parentId);subtaskParentId=null;render(false);
      const row=list.querySelector('[data-todo-id="'+parentId+'"]');
      if(row && !row.hidden)focusMore(row);else focusFilter();
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
        const result=await perform({action:'add',title,parent_id:item.id},'subtask added');
        if(result){
          subtaskDrafts.set(item.id,'');
          revealAdded(result.item);render(false);
        }
        focusSubtask(item.id);
      });
      return form;
    }
    function focusMove(id){
      const row=list.querySelector('[data-todo-id="'+id+'"]');
      const handle=row?.querySelector('[data-todo-drag]');
      if(handle && !row.hidden)handle.focus({preventScroll:true});else focusFilter();
    }
    function dismissMove(){
      if(!moveId || busy || drag?.active)return;
      const id=moveId;moveId=null;moveDrafts.delete(id);render();focusMove(id);
    }
    function openMove(id){
      if(!enabled || busy || drag?.active || activeFilter==='archive')return;
      if(moveId===id){dismissMove();return;}
      moveId=id;render();list.querySelector('[data-todo-move="'+id+'"] [name=target_id]')?.focus();
    }
    function moveForm(item){
      const form=element('form',undefined,'todo-move-form');form.dataset.todoMove=item.id;
      const heading=element('p','Move '+item.title),targetLabel=element('label','Destination'),target=element('select');
      target.name='target_id';target.id='todo-move-target-'+item.id;targetLabel.setAttribute('for',target.id);
      target.append(Object.assign(element('option','End of top-level tasks'),{value:''}));
      const moved=moveOrder(items,{id:item.id,target_id:null,placement:'root-end'}),excluded=new Set(moved?.movedIds||[item.id]);
      orderedTodos(items).filter(row=>!excluded.has(row.id)).forEach(row=>target.append(Object.assign(element('option',row.title),{value:row.id})));
      const placementLabel=element('label','Position'),placement=element('select');placement.name='placement';placement.id='todo-move-placement-'+item.id;placementLabel.setAttribute('for',placement.id);
      [['before','Before task'],['inside','Inside task as last subtask'],['after','After task and its subtasks']].forEach(([value,label])=>placement.append(Object.assign(element('option',label),{value})));
      const draft=moveDrafts.get(item.id)||{target_id:'',placement:'before'};moveDrafts.set(item.id,draft);
      target.value=draft.target_id;placement.value=draft.placement;
      const update=()=>{draft.target_id=target.value;draft.placement=placement.value;placement.disabled=busy || !target.value;placementLabel.hidden=!target.value;placement.hidden=!target.value;};
      target.addEventListener('change',update);placement.addEventListener('change',update);update();
      target.disabled=!enabled || busy;
      const submit=element('button','Move task');submit.type='submit';submit.disabled=!enabled || busy;
      const cancel=element('button','Cancel');cancel.type='button';cancel.dataset.todoDismissMove='';cancel.disabled=busy;
      form.append(heading,targetLabel,target,placementLabel,placement,submit,cancel);
      form.addEventListener('submit',async event=>{
        event.preventDefault();if(!enabled || busy || drag?.active)return;
        const payload={action:'move',id:item.id,target_id:target.value||null,placement:target.value?placement.value:'root-end',base_order:topology(items)};
        if(!moveOrder(items,payload)){moveNotice.textContent='Choose a task outside this task’s subtasks.';return;}
        if(await perform(payload,'task moved')){moveId=null;moveDrafts.delete(item.id);render();focusMove(item.id);}
      });
      return form;
    }
    function clearDropCue(state=drag){
      if(state?.cue)delete state.cue.dataset.todoDrop;
      delete rootDrop.dataset.todoDrop;
      if(state)state.cue=null;
    }
    function previewMove(){
      if(!drag?.active)return;
      clearDropCue();drag.request=null;
      const node=doc.elementFromPoint?.(drag.event.clientX,drag.event.clientY);
      let entry=node?.closest?.('.todo-entry');
      const source=items.find(item=>item.id===drag.id);
      if(node && rootDrop.contains(node)){
        drag.request={action:'move',id:drag.id,target_id:null,placement:'root-end',base_order:drag.baseOrder};rootDrop.dataset.todoDrop='root-end';
        moveNotice.textContent='Move '+source.title+' to the end of top-level tasks.';return;
      }
      if(!entry && node && list.contains(node)){
        // Padding belongs to its row; bare list gaps choose the nearest visible task.
        const hitRow=node.closest?.('[data-todo-id]');
        if(hitRow && list.contains(hitRow))entry=Array.from(hitRow.children).find(child=>child.classList?.contains('todo-entry'));
        if(!entry){
          let nearest=Infinity;
          list.querySelectorAll('.todo-entry').forEach(candidate=>{
            const row=candidate.closest('[data-todo-id]'),rect=candidate.getBoundingClientRect();
            if(row?.hidden || !rect.height)return;
            const distance=Math.max(rect.top-drag.event.clientY,drag.event.clientY-rect.bottom,0);
            if(distance<nearest){nearest=distance;entry=candidate;}
          });
        }
      }
      const row=entry?.closest('[data-todo-id]');
      if(!row || !list.contains(row) || row.hidden){moveNotice.textContent='Drop on another task or the top-level area. Tasks stay unchanged until saved.';return;}
      const rect=entry.getBoundingClientRect(),ratio=(drag.event.clientY-rect.top)/Math.max(1,rect.height),placement=ratio<.25?'before':ratio>.75?'after':'inside';
      const request={action:'move',id:drag.id,target_id:row.dataset.todoId,placement,base_order:drag.baseOrder};
      if(!moveOrder(items,request)){moveNotice.textContent='A task cannot move into itself or its subtasks.';return;}
      drag.request=request;drag.cue=entry;entry.dataset.todoDrop=placement;
      const target=items.find(item=>item.id===request.target_id);
      moveNotice.textContent='Move '+source.title+(placement==='inside'?' inside ':placement==='before'?' before ':' after ')+target.title+(placement==='inside'?' as its last subtask.':placement==='after'?' and its subtasks.':'.');
    }
    function autoScrollMove(){
      if(!drag?.active)return;
      const y=drag.event.clientY,edge=70,height=view.innerHeight,amount=y<edge?-Math.ceil((edge-y)/5):y>height-edge?Math.ceil((y-height+edge)/5):0;
      if(amount){view.scrollBy?.({top:Math.max(-24,Math.min(24,amount)),behavior:'instant'});previewMove();}
      dragFrame=view.requestAnimationFrame(autoScrollMove);
    }
    function finishDrag(commit,event){
      if(!drag || (event && event.pointerId!==drag.pointer))return;
      if(drag.active && event){drag.event=event;previewMove();}
      const state=drag;clearDropCue(state);drag=null;
      if(dragFrame!==null)view?.cancelAnimationFrame?.(dragFrame);dragFrame=null;
      rootDrop.hidden=true;delete section.dataset.todoDragging;delete state.source.dataset.todoDragging;section.todoBusy=busy;
      if(state.source.hasPointerCapture?.(state.pointer))state.source.releasePointerCapture(state.pointer);
      if(!state.active)return;
      suppressDragClick=true;
      setTimeout(()=>{suppressDragClick=false;},0);
      if(commit && state.request){
        moveNotice.textContent='Saving task position…';
        void perform(state.request,'task moved').then(result=>{moveNotice.textContent=result?'':'Move not confirmed. Previous task order is still shown.';focusMove(state.id);});
      }else{moveNotice.textContent=commit?'Drop rejected. Task order unchanged.':'Move cancelled. Task order unchanged.';focusMove(state.id);}
    }
    function connectDrag(handle,id){
      handle.addEventListener('pointerdown',event=>{
        if(!enabled || busy || drag || activeFilter==='archive' || (event.button!==undefined && event.button!==0) || event.isPrimary===false)return;
        drag={id,source:handle,pointer:event.pointerId,x:event.clientX,y:event.clientY,event,active:false,baseOrder:topology(items),request:null,cue:null};
        section.todoBusy=true;handle.setPointerCapture?.(event.pointerId);
      });
      handle.addEventListener('pointermove',event=>{
        if(!drag || drag.pointer!==event.pointerId)return;
        if(!drag.active && Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<(event.pointerType==='touch'?10:6))return;
        drag.event=event;
        if(!drag.active){drag.active=true;section.dataset.todoDragging='true';handle.dataset.todoDragging='true';rootDrop.hidden=false;closeMenus();if(view?.requestAnimationFrame)dragFrame=view.requestAnimationFrame(autoScrollMove);}
        previewMove();event.preventDefault();
      });
      handle.addEventListener('pointerup',event=>finishDrag(true,event));
      handle.addEventListener('pointercancel',event=>finishDrag(false,event));
      handle.addEventListener('lostpointercapture',event=>finishDrag(false,event));
    }
    doc.addEventListener?.('keydown',event=>{if(event.key==='Escape' && drag){event.preventDefault();finishDrag(false);}});
    function render(captureDraft=true,captureTags=true){
      if(drag)finishDrag(false);
      captureEditDraft();
      if(captureDraft)captureSubtaskDraft();if(captureTags)captureProjectDraft();
      list.replaceChildren();
      renderProjectOptions();
      const totals=summarize(items);
      counts.textContent=totals.pending+' open · '+totals.completed+' completed · '+totals.cancelled+' cancelled · '+archive.length+' archived';
      const archived=activeFilter==='archive',shown=archived?archive:items;
      moveHelp.hidden=archived || !enabled;
      moveHelp.textContent='Drag the handle to reorder. Drop on a task to nest; drop between tasks or at top level to unnest.'+(items.some(item=>Number.isSafeInteger(item.position))?' Stars mark importance; your task order stays saved.':'');
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
      const ordered=archived?shown:orderedTodos(items);
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
        actions.append(cancelSlot);
        const more=element('details',undefined,'todo-more'),summary=element('summary','⋯');
        summary.title='More task actions';summary.setAttribute('aria-label','More actions for '+item.title);
        more.addEventListener('toggle',()=>{if(more.open)closeMenus(more);});
        const secondary=element('div',undefined,'todo-more-panel');
        const projects=actionButton('Project tags','projects');projects.setAttribute('aria-expanded',String(projectEditorId===item.id));projects.setAttribute('aria-label','Edit project tags for '+item.title);
        const clear=actionButton('Clear task','remove');clear.title='Move this task to Archived; keep its subtasks';clear.setAttribute('aria-label','Clear task: '+item.title);
        const edit=actionButton('Edit task','edit');edit.setAttribute('aria-expanded',String(editId===item.id));
        secondary.append(edit,actionButton('Add subtask','subtask'),projects,clear);more.append(summary,secondary);actions.append(more);
        }
        const entry=element('div',undefined,'todo-entry'),children=element('ul',undefined,'todo-children');
        if(!archived){
          const handle=element('button','⠿','todo-drag-handle');handle.type='button';handle.dataset.todoDrag=item.id;handle.disabled=!enabled || busy;
          handle.setAttribute('aria-label','Move task: '+item.title);handle.setAttribute('aria-expanded',String(moveId===item.id));handle.title='Drag to reorder; activate for move options';
          entry.append(handle);connectDrag(handle,item.id);
        }
        entry.append(copy,actions);row.append(entry);
        if(!archived && moveId===item.id)row.append(moveForm(item));
        if(!archived && editId===item.id)row.append(editForm(item));
        if(!archived && subtaskParentId===item.id)row.append(subtaskForm(item));
        if(!archived && projectEditorId===item.id)row.append(projectForm(item));
        row.append(children);nodes.set(item.id,{row,children});
      });
      ordered.forEach(item=>{const parent=archived?null:nodes.get(item.parent_id);(parent && item.parent_id!==item.id?parent.children:list).append(nodes.get(item.id).row);});
      nodes.forEach(node=>{node.children.hidden=node.children.children.length===0;});
      empty.hidden=matching.size>0;empty.textContent=activeProject?'No tasks match this project and status.':archived?'No archived tasks. Cleared tasks will appear here.':items.length?'No tasks in this tab. Choose All tasks to see the rest.':'No tasks yet. Add one above.';
      section.querySelectorAll('.todo-add input,.todo-add button,.todo-add select').forEach(node=>{node.disabled=!enabled || busy;});
      if(doc.defaultView?.BriefUI?.mountTagPicker){
        const known=Array.from(projectOptions?.children||[]).map(option=>option.value);
        section.querySelectorAll('[name=project_tags]').forEach(input=>doc.defaultView.BriefUI.mountTagPicker(input,known,projectPickerDrafts.get(input.closest('[data-todo-project]')?.dataset.todoProject)));
      }
    }
    async function perform(payload,label){
      if(!enabled || busy || drag?.active)return false;
      if(drag)finishDrag(false);
      const scroll=payload.action==='move' && view?{x:view.scrollX,y:view.scrollY}:null;
      let acknowledged=false;
      const controls=Array.from(section.querySelectorAll('input,button,select')).map(node=>[node,node.disabled]);
      busy=true;section.todoBusy=true;notice.textContent='Saving '+label+'…';controls.forEach(([node])=>{node.disabled=true;});
      try{
        const response=await save(config.endpoint,{method:'POST',credentials:'omit',signal:AbortSignal.timeout(10000),headers:{'Content-Type':'application/json','X-Brief-Token':config.token},body:JSON.stringify(payload)});
        const result=await response.json();
        if(!response.ok || result.ok!==true)throw Error(result.error || 'The task could not be saved.');
        if(!confirmed(payload,result,archive,items))throw Error('The local server did not confirm this task change.');
        acknowledged=true;items=result.todos;archive=result.archive||archive;
        if(subtaskParentId && !items.some(item=>item.id===subtaskParentId)){subtaskDrafts.delete(subtaskParentId);subtaskParentId=null;}
        if(projectEditorId && !items.some(item=>item.id===projectEditorId)){projectDrafts.delete(projectEditorId);projectEditorId=null;}
        if(editId && !items.some(item=>item.id===editId)){editDrafts.delete(editId);editId=null;}
        notice.textContent='Saved locally: '+label+'.';
        section.dispatchEvent(new CustomEvent('local-todo-change',{bubbles:true,detail:{todos:items,archive,summary:summarize(items)}}));
        return result;
      }catch(error){
        const unavailable=error instanceof TypeError || error.name==='TimeoutError' || error.name==='AbortError';
        notice.textContent=unavailable?'Local task service unavailable. Reopen the live Morning Coffee workspace. Previous tasks are still shown.':'Task save not confirmed: '+error.message+' Previous tasks are still shown.';
        return false;
      }finally{busy=false;section.todoBusy=false;if(payload.action==='move' && !acknowledged)controls.forEach(([node,disabled])=>{node.disabled=disabled;});else render();if(scroll)view.scrollTo?.({left:scroll.x,top:scroll.y,behavior:'instant'});}
    }
    add.addEventListener('submit',async event=>{
      event.preventDefault();if(drag?.active)return;const title=add.querySelector('[name=title]');
      const projects=add.querySelector('[name=project_tags]'),payload={action:'add',title:title.value};
      if(projects?.tagPicker && !projects.tagPicker.commit())return;
      if(projects)payload.project_tags=parseTags(projects.value);
      const result=await perform(payload,'task added');
      if(result){title.value='';if(projects){projects.value='';projects.tagPicker?.reset();}revealAdded(result.item);render();title.focus();}
    });
    if(projectFilter)projectFilter.addEventListener('change',()=>{if(busy || drag?.active)return;activeProject=projectFilter.value;render();projectFilter.focus();});
    doc.addEventListener?.('click',event=>{
      if(!event.target.closest?.('.todo-more'))closeMenus();
    });
    list.addEventListener('keydown',event=>{
      if(event.key==='Escape' && drag){event.preventDefault();finishDrag(false);return;}
      if(event.key==='Escape' && event.target.closest('.todo-move-form')){event.preventDefault();dismissMove();return;}
      const more=event.target.closest('.todo-more');
      if(event.key==='Escape' && more){event.preventDefault();more.open=false;more.querySelector('summary').focus();return;}
      if(event.key==='Escape' && event.target.closest('.todo-subtask-form')){event.preventDefault();dismissSubtask();}
      if(event.key==='Escape' && event.target.closest('.todo-edit-form')){event.preventDefault();dismissEdit();}
      if(event.key==='Escape' && event.target.closest('.todo-project-form')){event.preventDefault();dismissProjects();}
    });
    list.addEventListener('click',async event=>{
      if(drag?.active)return;
      const handle=event.target.closest('[data-todo-drag]');
      if(handle && list.contains(handle)){if(suppressDragClick && event.detail!==0){suppressDragClick=false;return;}suppressDragClick=false;openMove(handle.dataset.todoDrag);return;}
      const dismissMoveButton=event.target.closest('[data-todo-dismiss-move]');if(dismissMoveButton && list.contains(dismissMoveButton)){dismissMove();return;}
      const dismissEditButton=event.target.closest('[data-todo-dismiss-edit]');if(dismissEditButton && list.contains(dismissEditButton)){dismissEdit();return;}
      const dismiss=event.target.closest('[data-todo-dismiss-subtask]');
      if(dismiss && list.contains(dismiss)){dismissSubtask();return;}
      const dismissTags=event.target.closest('[data-todo-dismiss-projects]');
      if(dismissTags && list.contains(dismissTags)){dismissProjects();return;}
      const button=event.target.closest('[data-todo-action]');if(!button || !list.contains(button))return;
      const row=button.closest('[data-todo-id]'),item=(activeFilter==='archive'?archive:items).find(task=>task.id===row.dataset.todoId);if(!item)return;
      const action=button.dataset.todoAction;closeMenus();
      if(action==='edit'){
        if(!enabled || busy)return;
        if(editId===item.id){dismissEdit();return;}
        captureEditDraft();editId=item.id;
        if(!editDrafts.has(item.id))editDrafts.set(item.id,{title:item.title,baseTitle:item.title});
        render();focusEdit(item.id);return;
      }
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
      function select(){if(busy || drag?.active)return;activeFilter=tab.dataset.todoFilter;render();focusFilter();}
      tab.addEventListener('click',select);
      tab.addEventListener('keydown',event=>{
        const target={ArrowRight:(index+1)%tabs.length,ArrowLeft:(index+tabs.length-1)%tabs.length,Home:0,End:tabs.length-1}[event.key];
        if(target===undefined || busy || drag?.active)return;
        event.preventDefault();activeFilter=tabs[target].dataset.todoFilter;render();focusFilter();
      });
    });
    if(clearView)clearView.addEventListener('click',async()=>{
      if(!enabled || busy || drag?.active || activeFilter==='archive')return;
      const ids=items.filter(item=>(activeFilter==='all' || item.status===activeFilter) && matchesProject(item,activeProject)).map(item=>item.id);
      if(!ids.length)return;
      if(!doc.defaultView?.confirm('Clear '+ids.length+' '+(ids.length===1?'task':'tasks')+' from '+labels[activeFilter]+(activeProject?' / '+(activeProject==='__untagged__'?'Untagged':activeProject.slice(4)):'')+'? They will move to Archived. You can undo this.')){focusFilter();return;}
      await perform({action:'clear',ids,status:activeFilter},ids.length+' '+(ids.length===1?'task':'tasks')+' cleared');
      focusFilter();
    });
    if(undo)undo.addEventListener('click',async()=>{
      if(!archive.length || drag?.active)return;const latest=archive[0],target=latest.status;
      if(await perform({action:'undo',id:latest.batch_id},'clear undone'))activeFilter=target;
      render();focusFilter();
    });
    // Open tasks remain visible across reports and day changes until explicitly closed.
    section.applyConfirmedTasks=(result,options={})=>{
      if(busy || drag?.active || result?.ok!==true || !Array.isArray(result.todos) || !result.todos.every(item=>validItem(item)) || (result.archive!==undefined && !validArchive(result.archive)))return false;
      items=result.todos;archive=result.archive||archive;
      const added=options.revealId?items.find(item=>item.id===options.revealId):null;
      if(added)revealAdded(added);
      render();
      if(added)notice.textContent='Added to your local tasks: '+added.title+'.';
      return true;
    };
    render();
  }
  if(typeof module!=='undefined' && module.exports)module.exports={moveOrder,moveConfirmed,topology,mount,confirmed,summarize,group,orderedTodos,parseTags,matchesProject};
  if(typeof document!=='undefined')mount(document);
})();
