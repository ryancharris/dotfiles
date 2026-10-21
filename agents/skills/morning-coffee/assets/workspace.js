/* Poll local state only. Source collection starts exclusively on an explicit click. */
(function () {
  'use strict';
  function busy(doc) {
    return Boolean(doc.querySelector('[data-review-saving="true"],[data-plan-locked="true"]') || doc.querySelector('#todos')?.todoBusy);
  }
  function patchWorkspace(doc, fresh) {
    const view=doc.defaultView,ui=view.BriefUI||{};
    const selectors=['.shop-sign','.world-status','#workspace-coverage','#what-changed','#today','#on-call','#daily-priorities','#rfcs-to-review','#reviews-waiting','#yesterday','#source-notes','#focus-exercise'];
    const pairs=selectors.map(selector=>[doc.querySelector(selector),fresh.querySelector(selector)]);
    if(pairs.some(pair=>!pair[0]||!pair[1]))throw Error('The updated workspace is incomplete. Previous facts remain visible.');
    const queues=Array.from(doc.querySelectorAll('.pr-queue')).map(queue=>queue.getBriefFilters?.());
    const open=new Set(Array.from(doc.querySelectorAll('details[open]')).map(node=>(node.closest('[id]')?.id||'')+'|'+node.querySelector('summary')?.textContent));
    const active=doc.activeElement,focusId=active?.id,focusFilter=active?.dataset.filter;
    const selection=active && typeof active.selectionStart==='number'?[active.selectionStart,active.selectionEnd]:null;
    const calendar=doc.querySelector('#focus-exercise'),oldDate=JSON.parse(doc.querySelector('.workspace-state-data').textContent).date;
    const newDate=JSON.parse(fresh.querySelector('.workspace-state-data').textContent).date;
    const editing=!calendar.hidden && oldDate===newDate;
    const draft=editing?calendar.dayPlanner?.getState():null,baseline=editing?calendar.scheduleEditor?.getBaseline():null;
    const baseRevision=editing?calendar.planSubmission?.getBaseRevision():undefined;
    const planInputs=editing?Array.from(calendar.querySelectorAll('.day-control input')).map(input=>input.value):[];
    const scroll=calendar.querySelector('.day-scroll')?.scrollTop||0,x=view.scrollX,y=view.scrollY;
    const replacements=pairs.map(([before,after])=>[before,doc.importNode(after,true)]);
    replacements.forEach(([before,after])=>before.replaceWith(after));
    doc.title=fresh.title;
    ui.mountBrief?.(doc);ui.mountReviews?.(doc);
    Array.from(doc.querySelectorAll('.pr-queue')).forEach((queue,index)=>queue.restoreBriefFilters?.(queues[index]));
    const nextCalendar=doc.querySelector('#focus-exercise');ui.mountCalendar?.(nextCalendar);
    doc.querySelectorAll('.plan-submission').forEach(node=>ui.mountSubmission?.(node));
    ui.mountRemoval?.(doc.querySelector('#today'));
    if(editing && draft){
      nextCalendar.dayPlanner?.restoreState(draft);
      nextCalendar.scheduleEditor?.restoreBaseline(baseline);
      if(baseRevision!==undefined)nextCalendar.planSubmission?.restoreBaseRevision(baseRevision);
      nextCalendar.scheduleEditor?.setVisible(true);
      Array.from(nextCalendar.querySelectorAll('.day-control input')).forEach((input,index)=>{if(planInputs[index]!==undefined)input.value=planInputs[index];});
    }
    const nextScroll=nextCalendar.querySelector('.day-scroll');if(nextScroll)nextScroll.scrollTop=scroll;
    doc.querySelectorAll('details').forEach(node=>{if(open.has((node.closest('[id]')?.id||'')+'|'+node.querySelector('summary')?.textContent))node.open=true;});
    doc.querySelector('.workspace-state-data').textContent=fresh.querySelector('.workspace-state-data').textContent;
    // Todo DOM is deliberately retained: drafts, hierarchy editing and filters belong to the user.
    let focus=focusId?doc.getElementById(focusId):null;
    if(!focus && focusFilter)focus=Array.from(doc.querySelectorAll('[data-filter]')).find(node=>node.dataset.filter===focusFilter);
    if(focus){focus.focus({preventScroll:true});if(selection&&focus.setSelectionRange)try{focus.setSelectionRange(...selection);}catch(_) {}}
    ui.updateCalendarPast?.(doc);
    view.scrollTo(x,y);
  }
  function mount(doc) {
    const root=doc.querySelector('#workspace-controls');if(!root||root.workspaceMounted)return;
    root.workspaceMounted=true;
    const view=doc.defaultView,config=JSON.parse(root.querySelector('.workspace-interaction-data').textContent);
    let state=JSON.parse(root.querySelector('.workspace-state-data').textContent),renderedVersion=state.version;
    let checking=false,acting=false,applying=false,timer=null,disposed=false,editEpoch=0;
    ['input','change','local-review-change','day-plan-change','local-plan-saved'].forEach(name=>doc.addEventListener(name,()=>{editEpoch++;}));
    const refresh=root.querySelector('[data-workspace-refresh]'),refreshLabel=root.querySelector('[data-workspace-refresh-label]'),start=root.querySelector('[data-workspace-start]'),status=root.querySelector('[data-workspace-status]');
    const pending=()=>['pending','running'].includes(state.refresh?.status);
    const today=()=>{const parts=new Intl.DateTimeFormat('en-CA',{timeZone:state.timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());const value=type=>parts.find(row=>row.type===type)?.value;return value('year')+'-'+value('month')+'-'+value('day');};
    function show(message) {
      const newDay=today()!==state.date;
      refresh.disabled=acting||pending()||!state.bridge_configured||newDay;
      start.hidden=!newDay;start.disabled=acting||pending()||!state.bridge_configured;
      refreshLabel.textContent=pending()?'Refreshing…':'Refresh';
      refresh.setAttribute('aria-label',pending()?'Refreshing sources':'Refresh all sources');
      refresh.setAttribute('aria-busy',String(pending()));
      status.textContent=message||(pending()?'Checking sources. You can keep working.':!state.bridge_configured?'Source refresh is currently unavailable.':state.refresh?.status==='failed'?'Refresh failed. Your previous report is still shown.':newDay?'Viewing '+state.date+'. Start today to begin a fresh day.':'');
      status.hidden=!status.textContent;
    }
    async function request(endpoint,body) {
      const response=await view.fetch(endpoint,{method:body===undefined?'GET':'POST',credentials:'omit',cache:'no-store',signal:AbortSignal.timeout(15000),headers:{'X-Brief-Token':config.token,...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
      const result=await response.json();if(!response.ok||!result.ok)throw Error(result.error||'The local workspace is unavailable.');return result;
    }
    async function update() {
      if(applying||busy(doc)||acting||state.version===renderedVersion)return;
      applying=true;
      const epoch=editEpoch;
      try {
        const response=await view.fetch(view.location.href,{credentials:'omit',cache:'no-store',signal:AbortSignal.timeout(15000)});
        if(!response.ok)throw Error('The updated source view could not load.');
        const fresh=new view.DOMParser().parseFromString(await response.text(),'text/html');
        if(busy(doc)||acting||epoch!==editEpoch)return;
        const next=JSON.parse(fresh.querySelector('.workspace-state-data').textContent);
        patchWorkspace(doc,fresh);state=next;renderedVersion=next.version;show();
      } catch(error) {show('The updated report could not load. Your previous report is still shown. Retrying…');}
      finally {applying=false;}
    }
    async function poll() {
      if(checking||disposed)return;checking=true;
      try {const result=await request(config.status_endpoint);state=result.workspace;show();await update();}
      catch(error) {show('This report is offline. Your previous report is still shown.');}
      finally {checking=false;if(!disposed){view.clearTimeout(timer);timer=view.setTimeout(poll,pending()||state.version!==renderedVersion?1000:8000);}}
    }
    async function run(endpoint) {
      if(acting||pending())return;acting=true;let message='';show('Requesting a refresh…');
      try {state=(await request(endpoint,{})).workspace;show();}
      catch(error) {message='Refresh could not start. Your previous report is still shown.';}
      finally {acting=false;await poll();if(message)show(message);}
    }
    refresh.addEventListener('click',()=>run(config.refresh_endpoint));
    start.addEventListener('click',()=>run(config.start_today_endpoint));
    doc.addEventListener('click',async event=>{
      const button=event.target.closest?.('[data-suggestion-action]');if(!button||acting||applying)return;
      const section=doc.querySelector('#todos');if(section?.todoBusy)return;
      acting=true;const controls=section?Array.from(section.querySelectorAll('input,button,select')).map(node=>[node,node.disabled]):[];
      if(section)section.todoBusy=true;controls.forEach(([node])=>{node.disabled=true;});
      doc.querySelectorAll('[data-suggestion-action]').forEach(node=>{node.disabled=true;});
      const notice=doc.querySelector('.workspace-suggestion-status');notice.textContent='Saving your choice locally…';
      try {
        const result=await request(config.suggestion_endpoint,{id:button.dataset.suggestionId,action:button.dataset.suggestionAction,fingerprint:button.dataset.suggestionFingerprint});
        if(section){section.todoBusy=false;if(!section.applyConfirmedTasks?.({...result,archive:result.todo_archive}))throw Error('Choice saved. Reload the workspace to see the updated task list.');}
        state=result.workspace;
      } catch(error) {notice.textContent='Choice not confirmed in this view: '+error.message;}
      finally {if(section)section.todoBusy=false;controls.forEach(([node,disabled])=>{node.disabled=disabled;});acting=false;doc.querySelectorAll('[data-suggestion-action]').forEach(node=>{node.disabled=false;});await update();show();}
    });
    doc.addEventListener('visibilitychange',()=>{if(!doc.hidden)poll();});
    view.addEventListener('pagehide',()=>{disposed=true;view.clearTimeout(timer);});
    show();poll();
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={mount,patchWorkspace,busy};
  if(typeof document!=='undefined')mount(document);
})();
