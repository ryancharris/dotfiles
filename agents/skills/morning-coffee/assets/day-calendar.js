/* All movement is local visualization. No provider calls or snapshot mutation. */
(function () {
  'use strict';
  const focusName = value => {
    if(typeof value!=='string' || /[\p{Cc}\p{Cs}]/u.test(value))throw Error('Use a plain-text focus name without control characters.');
    const name=value.trim();
    if(Array.from(name).length>120)throw Error('Keep the focus name to 120 characters or fewer.');
    return name;
  };
  const overlap = (a, b) => a.start < b.end && b.start < a.end;
  const snap = n => Math.round(n / 15) * 15;
  const clock = n => String(Math.floor(n / 60)).padStart(2, '0') + ':' + String(n % 60).padStart(2, '0');
  const parseClock = value => /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value) ? Number(value.slice(0,2))*60+Number(value.slice(3)) : null;
  // Read the lane's current viewport geometry on every move, including after scroll.
  function dropMinute(event, rect, data, offset=0) {
    return rect.height > 0 && Number.isFinite(event.clientY) ? snap(data.start+(event.clientY-rect.top)/rect.height*(data.end-data.start)-offset) : null;
  }
  const visibleBounds = data => ({start:data.view_start ?? data.start,end:data.view_end ?? data.end});
  const contains = (rect, event) => rect.width > 0 && rect.height > 0 && event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
  function placement(value, duration, data) {
    const low = Math.ceil(data.start / 15) * 15;
    const high = Math.floor((data.end - duration) / 15) * 15;
    return Number.isFinite(value) && low <= high ? Math.min(high, Math.max(low, snap(value))) : null;
  }
  function canPlace(start, block, data, blocks) {
    const candidate = {start, end:start + block.minutes};
    return Number.isFinite(start) && start >= Math.max(data.start,block.min_start ?? data.start) && candidate.end <= Math.min(data.end,block.max_end ?? data.end) &&
      !data.fixed.some(event => overlap(candidate,event)) &&
      !blocks.some(other => other.kind !== block.kind && other.start !== null &&
        overlap(candidate,{start:other.start,end:other.start + other.minutes}));
  }
  function firstFree(block, data, blocks) {
    for(let start=Math.ceil(Math.max(data.start,data.now,block.min_start ?? data.start)/15)*15;start+block.minutes<=Math.min(data.end,block.max_end ?? data.end);start+=15) {
      if(canPlace(start,block,data,blocks))return start;
    }
    return null;
  }
  function warnings(data, blocks) {
    const placed = blocks.filter(b => b.start !== null);
    const issues = [];
    if (!data.verified) issues.push('Availability unverified');
    if (placed.some(b => b.start < data.now)) issues.push('Includes past time');
    if (placed.some(b => data.fixed.some(f => overlap({start:b.start,end:b.start+b.minutes},f)))) issues.push('Overlaps calendar');
    if (placed.some((b,i) => placed.slice(i+1).some(c => overlap({start:b.start,end:b.start+b.minutes},{start:c.start,end:c.start+c.minutes})))) issues.push('Plan blocks overlap');
    const unplaced = blocks.filter(b => b.start === null);
    if (unplaced.length) issues.push('Unplaced: ' + unplaced.map(b => b.label).join(', '));
    return issues;
  }
  function lanes(rows) {
    const sorted = rows.slice().sort((a,b) => a.start-b.start || b.end-a.end);
    let group = [], ends = [], groupEnd = -Infinity;
    const finish = () => group.forEach(row => {row.columns = ends.length;});
    sorted.forEach(row => {
      if (row.start >= groupEnd) {finish();group=[];ends=[];groupEnd=-Infinity;}
      let column=ends.findIndex(end => end <= row.start);
      if(column < 0) column=ends.length;
      ends[column]=row.end;row.column=column;group.push(row);groupEnd=Math.max(groupEnd,row.end);
    });
    finish();return sorted;
  }
  function mount(root) {
    if(root.dayPlanner)return;
    const payload=root.querySelector('.day-calendar-data');
    if(!payload){mountRemoval(root);return;}
    const data = JSON.parse(payload.textContent);
    const display = visibleBounds(data);
    if(data.read_only)return;
    const original = data.blocks.map(b => ({...b}));
    const accepted=[];
    original.forEach(block=>{
      if(block.start!==null&&!canPlace(block.start,block,data,accepted))block.start=null;
      accepted.push(block);
    });
    let blocks = original.map(b => ({...b}));
    root.getDayPlan=()=>JSON.parse(JSON.stringify({...data,blocks}));
    root.dayPlanner={getState:root.getDayPlan,setLocked,restoreState};
    const lane = root.querySelector('.day-plan-lane');
    const scroll = root.querySelector('.day-scroll');
    const status = root.querySelector('.day-warning');
    const view = root.ownerDocument && root.ownerDocument.defaultView;
    let drag = null, locked = false, ghost = null, frame = null, suppressClick = null;
    function setLocked(value) {
      if(drag)finishDrag(false);
      locked=Boolean(value);
      if(root.dataset)root.dataset.planLocked=String(locked);
      blocks.forEach(block=>{
        const button=lane.querySelector('[data-kind="'+block.kind+'"]');
        const control=root.querySelector('.day-control[data-kind="'+block.kind+'"]');
        button.disabled=locked;
        control.querySelector('input').disabled=locked;
        const duration=control.querySelector('[data-duration]');
        if(duration)duration.disabled=locked;
        const name=control.querySelector('[data-focus-name]');
        if(name)name.disabled=locked;
        control.querySelector('[data-place]').disabled=locked;
        control.querySelector('[data-remove]').disabled=locked;
      });
      root.querySelector('.day-reset').disabled=locked;
    }
    function restoreState(state) {
      if(locked || !state || !Array.isArray(state.blocks))return false;
      if(drag)finishDrag(false);
      // Restore personal placement choices onto the currently verified source bounds.
      blocks=original.map(block=>{
        const chosen=state.blocks.find(row=>row.kind===block.kind);
        if(!chosen)return {...block};
        const restored={...block,start:chosen.start,minutes:chosen.minutes,label:chosen.label || block.label};
        delete restored.name;
        if(chosen.name)restored.name=chosen.name;
        return restored;
      });
      render('Draft changes discarded');
      return true;
    }
    function announce(message) {
      status.textContent=(message ? message+' · ' : '')+warnings(data,blocks).join(' · ');
    }
    function render(message) {
      const rows=lanes(blocks.filter(b=>b.start!==null).map(b=>({kind:b.kind,start:b.start,end:b.start+b.minutes})));
      blocks.forEach(block => {
        const button = lane.querySelector('[data-kind="'+block.kind+'"]');
        const control = root.querySelector('.day-control[data-kind="'+block.kind+'"]');
        const input = control.querySelector('input');
        const absent = block.start === null;
        const completion=control.querySelector('[data-calendar-saved-key]');
        if(completion){
          const saved=completion.dataset;
          const matches=block.start===Number(saved.calendarSavedStart)&&block.minutes===Number(saved.calendarSavedMinutes);
          completion.hidden=!matches;
          if(matches){
            button.dataset.calendarKey=saved.calendarSavedKey;
            button.setAttribute('data-local-plan-end',saved.calendarSavedEnd);
            const mark=completion.getAttribute('data-calendar-done');
            if(mark===null)button.removeAttribute('data-calendar-done');else button.setAttribute('data-calendar-done',mark);
          }else{
            button.removeAttribute('data-calendar-key');button.removeAttribute('data-calendar-done');button.removeAttribute('data-local-plan-end');
            button.classList.remove('calendar-past','calendar-done');
          }
        }
        button.hidden=absent || block.start >= display.end || block.start + block.minutes <= display.start;
        input.value=absent?'':clock(block.start);
        const name=control.querySelector('[data-focus-name]'),label=control.querySelector('[data-block-label]');
        if(name)name.value=block.name || '';
        if(label)label.textContent=block.label;
        const heading=button.querySelector('b');
        if(heading)heading.textContent=block.label;
        input.setAttribute('aria-label',block.label+' start time, HH:MM (24 hour)');
        control.querySelector('[data-place]').setAttribute('aria-label','Place '+block.label+' in the first free slot, or drag into Your plan.');
        control.querySelector('[data-remove]').setAttribute('aria-label','Unplace '+block.label);
        const duration=control.querySelector('[data-duration]'),summary=control.querySelector('[data-duration-summary]');
        if(duration)duration.value=String(block.minutes);
        if(summary)summary.textContent=block.minutes+'m';
        button.classList.toggle('day-short',block.minutes<45);
        control.classList.toggle('day-unplaced',absent);
        control.querySelector('[data-place]').hidden=!absent;
        control.querySelector('[data-remove]').hidden=absent;
        if (!absent) {
          const end=block.start+block.minutes, row=rows.find(r=>r.kind===block.kind);
          button.style.top=((Math.max(block.start,display.start)-display.start)/(display.end-display.start)*100)+'%';
          button.style.height=(Math.max(0,Math.min(end,display.end)-Math.max(block.start,display.start))/(display.end-display.start)*100)+'%';
          button.style.left=(row.column/row.columns*100)+'%';
          button.style.width=(100/row.columns)+'%';
          button.querySelector('span').textContent=clock(block.start)+'–'+clock(end);
          button.setAttribute('aria-label',block.label+', '+clock(block.start)+' to '+clock(end)+'. Arrow keys move 15 minutes.');
          button.classList.toggle('day-conflict',block.start<data.now);
        }
      });
      root.ownerDocument?.defaultView?.BriefUI?.updateCalendarPast?.(root);
      announce(message);
      if(typeof CustomEvent!=='undefined'&&root.dispatchEvent)root.dispatchEvent(new CustomEvent('day-plan-change'));
    }
    function showPreview() {
      if(!drag || !drag.active)return;
      const block=blocks.find(b=>b.kind===drag.kind), rect=lane.getBoundingClientRect();
      const inside=contains(rect,drag.event) && (!scroll || contains(scroll.getBoundingClientRect(),drag.event));
      const next=dropMinute(drag.event,rect,display,drag.offset);
      drag.next=next;
      drag.valid=inside && next>=display.start && next+block.minutes<=display.end && canPlace(next,block,data,blocks);
      lane.classList.toggle('day-drop-valid',drag.valid);
      lane.classList.toggle('day-drop-invalid',!drag.valid);
      if(ghost){
        ghost.hidden=!inside || next===null;
        ghost.style.top=((Math.max(next,display.start)-display.start)/(display.end-display.start)*100)+'%';
        ghost.style.height=(Math.max(0,Math.min(next+block.minutes,display.end)-Math.max(next,display.start))/(display.end-display.start)*100)+'%';
        ghost.classList.toggle('day-drop-invalid',!drag.valid);
        ghost.querySelector('b').textContent=block.label;
        ghost.querySelector('span').textContent=clock(next)+'–'+clock(next+block.minutes);
      }
      announce(!inside ? 'Drop in Your plan; Escape cancels.' : drag.valid ? 'Release to place '+block.label+' at '+clock(next)+'.' : 'Unavailable time: overlaps a block or event, or is outside this block’s planning window.');
    }
    function autoScroll(timestamp) {
      if(!drag || !drag.active || !scroll)return;
      const rect=scroll.getBoundingClientRect(), event=drag.event, edge=36;
      const direction=event.clientX>=rect.left && event.clientX<=rect.right && event.clientY>=rect.top && event.clientY<=rect.bottom ?
        event.clientY<rect.top+edge ? -1 : event.clientY>rect.bottom-edge ? 1 : 0 : 0;
      const elapsed=Math.min(40,drag.frameTime===null ? 16 : timestamp-drag.frameTime);
      drag.frameTime=timestamp;
      if(direction){scroll.scrollTop+=direction*elapsed*.45;showPreview();}
      frame=view.requestAnimationFrame(autoScroll);
    }
    function beginDrag(event, source, kind, unplaced) {
      if(locked || drag || event.button!==0 || event.isPrimary===false)return;
      const block=blocks.find(b=>b.kind===kind);
      if(unplaced && block.start!==null)return;
      suppressClick=null;
      const rect=lane.getBoundingClientRect();
      drag={kind,source,pointer:event.pointerId,x:event.clientX,y:event.clientY,event,active:false,next:null,valid:false,frameTime:null,
        offset:unplaced ? 0 : display.start+(event.clientY-rect.top)/rect.height*(display.end-display.start)-block.start};
      source.setPointerCapture(event.pointerId);
      event.preventDefault();
    }
    function moveDrag(event) {
      if(!drag || drag.pointer!==event.pointerId)return;
      drag.event=event;
      if(!drag.active && Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<4)return;
      if(!drag.active){
        drag.active=true;
        drag.source.classList.add('day-moving');
        lane.classList.add('day-drop-active');
        if(root.ownerDocument){
          ghost=root.ownerDocument.createElement('div');
          ghost.className='day-block day-drag-preview';
          ghost.dataset.kind=drag.kind;
          ghost.setAttribute('aria-hidden','true');
          ghost.appendChild(root.ownerDocument.createElement('b'));
          ghost.appendChild(root.ownerDocument.createElement('span'));
          lane.appendChild(ghost);
        }
        if(view && scroll)frame=view.requestAnimationFrame(autoScroll);
      }
      showPreview();
      event.preventDefault();
    }
    function finishDrag(commit, event) {
      if(!drag || (event && drag.pointer!==event.pointerId))return;
      if(drag.active && event && Number.isFinite(event.clientX) && Number.isFinite(event.clientY)){drag.event=event;showPreview();}
      const current=drag, block=blocks.find(b=>b.kind===current.kind);
      drag=null;
      if(frame!==null && view)view.cancelAnimationFrame(frame);
      frame=null;
      if(ghost){ghost.remove();ghost=null;}
      current.source.classList.remove('day-moving');
      lane.classList.remove('day-drop-active','day-drop-valid','day-drop-invalid');
      if(current.source.hasPointerCapture && current.source.hasPointerCapture(current.pointer))current.source.releasePointerCapture(current.pointer);
      if(!current.active)return;
      suppressClick=current.kind;
      if(commit && current.valid){block.start=current.next;render(block.label+' placed at '+clock(block.start)+'.');}
      else announce(commit ? 'Drop rejected; choose a free time in Your plan. Plan unchanged.' : 'Drag cancelled. Plan unchanged.');
    }
    function connectDrag(source,kind,unplaced) {
      source.addEventListener('pointerdown',event=>beginDrag(event,source,kind,unplaced));
      source.addEventListener('pointermove',moveDrag);
      source.addEventListener('pointerup',event=>finishDrag(true,event));
      source.addEventListener('pointercancel',event=>finishDrag(false,event));
      source.addEventListener('lostpointercapture',event=>finishDrag(false,event));
      source.addEventListener('keydown',event=>{
        if(event.key==='Escape' && drag){event.preventDefault();finishDrag(false);}
      });
    }
    function setTime(kind,value,announce) {
      if(locked)return;
      const block=blocks.find(b=>b.kind===kind);
      const bounds={...data,start:Math.max(data.start,block.min_start ?? data.start),end:Math.min(data.end,block.max_end ?? data.end)};
      const next=placement(value,block.minutes,bounds);
      if(next===null){render('Block is longer than this planning window');return;}
      if(!canPlace(next,block,data,blocks)){render('That time overlaps another block or event. Choose a free slot.');return;}
      block.start=next;
      const adjusted=announce&&next!==value ? (value<bounds.start||value+block.minutes>bounds.end ? 'Moved to '+clock(next)+' · window '+clock(bounds.start)+'–'+clock(bounds.end) : 'Snapped to '+clock(next)) : '';
      render(adjusted);
    }
    root.querySelectorAll('.day-control').forEach(control=>{
      const kind=control.dataset.kind;
      const name=control.querySelector('[data-focus-name]');
      if(name)name.addEventListener('change',()=>{
        const block=blocks.find(b=>b.kind===kind);
        if(locked){name.value=block.name || '';return;}
        if(drag)finishDrag(false);
        let value;
        try{value=focusName(name.value);}catch(error){render(error.message);return;}
        if(value)block.name=value;else delete block.name;
        block.label=value?'🔎 '+value:'🔎 Focus';
        render(value?'Focus name updated.':'Focus name cleared.');
      });
      const duration=control.querySelector('[data-duration]');
      if(duration)duration.addEventListener('change',()=>{
        const block=blocks.find(b=>b.kind===kind),minutes=Number(duration.value);
        if(locked){duration.value=String(block.minutes);return;}
        if(drag)finishDrag(false);
        const maximum=Math.floor((Math.min(data.end,block.max_end ?? data.end)-Math.max(data.start,block.min_start ?? data.start))/15)*15;
        if(!Number.isInteger(minutes) || minutes<15 || minutes%15 || minutes>maximum){
          render('Choose a focus duration in 15-minute increments within the checked planning window.');return;
        }
        if(block.start!==null && !canPlace(block.start,{...block,minutes},data,blocks)){
          render('That duration overlaps another block or event, or exceeds the checked planning window. Unplace focus or choose a shorter duration.');return;
        }
        block.minutes=minutes;render('Focus duration set to '+minutes+' minutes.');
      });
      const place=control.querySelector('[data-place]');
      place.textContent='Place / drag';
      place.setAttribute('title','Drag into Your plan, or activate to place in the first free slot.');
      place.setAttribute('aria-label','Place '+blocks.find(b=>b.kind===kind).label+' in the first free slot, or drag into Your plan.');
      connectDrag(place,kind,true);
      control.querySelector('input').addEventListener('change',event=>{
        if(locked){const block=blocks.find(b=>b.kind===kind);event.target.value=block.start===null?'':clock(block.start);return;}
        const value=event.target.value;
        if(!value){blocks.find(b=>b.kind===kind).start=null;render();return;}
        const parsed=parseClock(value);
        if(parsed===null){render('Enter a 24-hour time as HH:MM, such as 09:30 or 14:00.');return;}
        setTime(kind,parsed,true);
      });
      control.querySelector('[data-place]').addEventListener('click',event=>{
        const dragged=suppressClick===kind;
        suppressClick=null;
        if(dragged && event.detail!==0)return;
        if(locked)return;
        const block=blocks.find(b=>b.kind===kind),next=firstFree(block,{...data,start:display.start,end:display.end},blocks);
        if(next===null){render('No free slot for '+block.label+'.');return;}
        setTime(kind,next);
      });
      control.querySelector('[data-remove]').addEventListener('click',()=>{if(locked)return;blocks.find(b=>b.kind===kind).start=null;render();});
    });
    lane.querySelectorAll('.day-block').forEach(button=>{
      const kind=button.dataset.kind;
      button.addEventListener('keydown',event=>{
        if(locked)return;
        if(!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key))return;
        event.preventDefault();
        const current=blocks.find(b=>b.kind===kind);
        setTime(kind,current.start+(['ArrowUp','ArrowLeft'].includes(event.key)?-15:15));
      });
      connectDrag(button,kind,false);
    });
    if(scroll)scroll.addEventListener('scroll',showPreview);
    root.querySelector('.day-reset').addEventListener('click',()=>{if(locked)return;if(drag)finishDrag(false);blocks=original.map(b=>({...b,start:null}));render('All blocks unplaced');});
    render();
  }
  function mountRemoval(root) {
    if(!root || typeof root.querySelector!=='function')return;
    if(root.removalMounted)return;
    const node=root.querySelector('.day-plan-removal-data');
    if(!node)return;
    root.removalMounted=true;
    const config=JSON.parse(node.textContent),status=root.querySelector('.day-remove-status');
    const buttons=Array.from(root.querySelectorAll('.day-remove-submitted'));
    let saving=false;
    async function refreshSavedPlan() {
      try {
        await refreshPlanSurfaces(root);
      } catch(error) {
        status.textContent='Block removed locally. The updated view could not load: '+error.message+' Refresh the saved plan to update this view.';
        const retry=root.ownerDocument.createElement('button');
        retry.type='button';retry.textContent='Refresh saved plan';
        retry.addEventListener('click',async()=>{retry.disabled=true;await refreshSavedPlan();});
        status.append(retry);
      }
    }
    buttons.forEach(button=>button.addEventListener('click',async()=>{
      if(saving)return;
      saving=true;root.dataset.planLocked='true';buttons.forEach(item=>{item.disabled=true;});
      status.textContent='Removing your local plan block…';
      try {
        const block={kind:button.dataset.kind,start:Number(button.dataset.start),minutes:Number(button.dataset.minutes)};
        const sameBlock=(left,right)=>left && right && ['kind','start','minutes'].every(key=>left[key]===right[key]);
        const expected=Array.isArray(config.blocks)?config.blocks.filter(row=>!sameBlock(row,block)):null;
        if(!expected || config.blocks.length!==expected.length+1)throw Error('Reload the workspace to verify this saved block before removing it.');
        const response=await fetch(config.endpoint,{method:'POST',credentials:'omit',signal:AbortSignal.timeout(10000),headers:{'Content-Type':'application/json','X-Brief-Token':config.token},
          body:JSON.stringify({date:config.date,timezone:config.timezone,revision:config.revision,
            block})});
        const result=await response.json();
        if(!response.ok || !result.ok || !Array.isArray(result.blocks) || result.blocks.length!==expected.length ||
          !expected.every(row=>result.blocks.filter(saved=>sameBlock(row,saved) && row.name===saved.name).length===1))throw Error(result.error || 'The local change was not acknowledged with the expected remaining blocks.');
      } catch(error) {
        status.textContent='Removal not confirmed saved: '+error.message;
        saving=false;root.dataset.planLocked='false';buttons.forEach(item=>{item.disabled=false;});
        return;
      }
      status.textContent='Block removed locally. Refreshing your saved plan…';
      await refreshSavedPlan();
    }));
  }
  async function refreshPlanSurfaces(root,message='Block removed locally.',preserveDraft=false) {
    const doc=root.ownerDocument,view=doc.defaultView;
    const response=await fetch(view.location.href,{credentials:'omit',cache:'no-store',signal:AbortSignal.timeout(10000)});
    if(!response.ok)throw Error('The local report is unavailable.');
    const fresh=new view.DOMParser().parseFromString(await response.text(),'text/html');
    const agenda=source=>{
      const link=source.querySelector('#day-overview a[href="#today"]');
      return link && link.closest('.check-in-card');
    };
    const pairs=['#focus-exercise','#today'].map(selector=>[doc.querySelector(selector),fresh.querySelector(selector)]);
    const oldAgenda=agenda(doc);
    if(oldAgenda)pairs.push([oldAgenda,agenda(fresh)]);
    const overview=doc.querySelector('.world-status [data-calendar-event-count]');
    if(overview)pairs.push([overview,fresh.querySelector('.world-status [data-calendar-event-count]')]);
    if(pairs.some(([before,after])=>!before || !after))throw Error('The refreshed plan view is incomplete.');
    // Validate and prepare every replacement before touching the live document.
    const replacements=pairs.map(([before,after])=>[before,doc.importNode(after,true)]);
    const previous=doc.querySelector('#focus-exercise');
    const editing=preserveDraft && !previous.hidden;
    const draft=editing?previous.dayPlanner?.getState():null;
    const baseline=editing?previous.scheduleEditor?.getBaseline():null;
    const revision=editing?previous.planSubmission?.getBaseRevision():undefined;
    const inputs=editing?Array.from(previous.querySelectorAll('.day-control input')).map(input=>input.value):[];
    const oldScroll=doc.querySelector('.day-scroll'),scrollTop=oldScroll?oldScroll.scrollTop:0;
    const scrollX=view.scrollX,scrollY=view.scrollY,hadFocus=root.contains(doc.activeElement);
    replacements.forEach(([before,after])=>before.replaceWith(after));
    const calendar=replacements[0][1];
    mount(calendar);mountRemoval(calendar);
    mountRemoval(doc.querySelector('#today'));
    if(view.BriefUI?.mountSubmission)doc.querySelectorAll('.plan-submission').forEach(view.BriefUI.mountSubmission);
    if(editing && draft){
      calendar.dayPlanner?.restoreState(draft);
      calendar.scheduleEditor?.restoreBaseline(baseline);
      if(revision!==undefined)calendar.planSubmission?.restoreBaseRevision(revision);
      calendar.scheduleEditor?.setVisible(true);
      Array.from(calendar.querySelectorAll('.day-control input')).forEach((input,index)=>{if(inputs[index]!==undefined)input.value=inputs[index];});
    }
    const scroll=calendar.querySelector('.day-scroll');
    if(scroll)scroll.scrollTop=scrollTop;
    const status=preserveDraft?doc.querySelector('.calendar-removal-status'):(doc.querySelector('#today .day-remove-status') || calendar.querySelector('.day-remove-status'));
    if(status){status.textContent=message;if(hadFocus){status.tabIndex=-1;status.focus({preventScroll:true});}}
    view.BriefUI?.updateCalendarPast?.(doc);
    if(typeof view.CustomEvent==='function')doc.dispatchEvent(new view.CustomEvent('local-plan-saved'));
    view.scrollTo(scrollX,scrollY);
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={focusName,overlap,snap,parseClock,dropMinute,placement,canPlace,firstFree,warnings,lanes,mount,mountRemoval,refreshPlanSurfaces};
  if(typeof window!=='undefined'){window.BriefUI=window.BriefUI||{};Object.assign(window.BriefUI,{mountCalendar:mount,mountRemoval,refreshPlanSurfaces});}
  if(typeof document!=='undefined'){
    document.querySelectorAll('.day-calendar').forEach(mount);
    const today=document.querySelector('#today');if(today)mountRemoval(today);
    document.querySelectorAll('.day-scroll').forEach(view=>{const board=view.querySelector('.day-board');if(board)view.scrollTop=(Number(view.dataset.scrollMinute||0)-Number(view.dataset.scrollStart||0))/(Number(view.dataset.scrollEnd||1440)-Number(view.dataset.scrollStart||0))*board.getBoundingClientRect().height;});
  }
})();
