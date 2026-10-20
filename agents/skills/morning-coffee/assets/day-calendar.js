/* All movement is local visualization. No provider calls or snapshot mutation. */
(function () {
  'use strict';
  const overlap = (a, b) => a.start < b.end && b.start < a.end;
  const snap = n => Math.round(n / 15) * 15;
  const clock = n => String(Math.floor(n / 60)).padStart(2, '0') + ':' + String(n % 60).padStart(2, '0');
  const parseClock = value => /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value) ? Number(value.slice(0,2))*60+Number(value.slice(3)) : null;
  // Read the lane's current viewport geometry on every move, including after scroll.
  function dropMinute(event, rect, data, offset=0) {
    return rect.height > 0 && Number.isFinite(event.clientY) ? snap(data.start+(event.clientY-rect.top)/rect.height*(data.end-data.start)-offset) : null;
  }
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
    const payload=root.querySelector('.day-calendar-data');
    if(!payload)return;
    const data = JSON.parse(payload.textContent);
    if(data.read_only)return;
    const original = data.blocks.map(b => ({...b}));
    const accepted=[];
    original.forEach(block=>{
      if(block.start!==null&&!canPlace(block.start,block,data,accepted))block.start=null;
      accepted.push(block);
    });
    let blocks = original.map(b => ({...b}));
    root.getDayPlan=()=>JSON.parse(JSON.stringify({...data,blocks}));
    root.dayPlanner={getState:root.getDayPlan,setLocked};
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
        control.querySelector('[data-place]').disabled=locked;
        control.querySelector('[data-remove]').disabled=locked;
      });
      root.querySelector('.day-reset').disabled=locked;
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
        button.hidden=absent;
        input.value=absent?'':clock(block.start);
        control.classList.toggle('day-unplaced',absent);
        control.querySelector('[data-place]').hidden=!absent;
        control.querySelector('[data-remove]').hidden=absent;
        if (!absent) {
          const end=block.start+block.minutes, row=rows.find(r=>r.kind===block.kind);
          button.style.top=((block.start-data.start)/(data.end-data.start)*100)+'%';
          button.style.height=(block.minutes/(data.end-data.start)*100)+'%';
          button.style.left=(row.column/row.columns*100)+'%';
          button.style.width=(100/row.columns)+'%';
          button.querySelector('span').textContent=clock(block.start)+'–'+clock(end);
          button.setAttribute('aria-label',block.label+', '+clock(block.start)+' to '+clock(end)+'. Arrow keys move 15 minutes.');
          button.classList.toggle('day-conflict',block.start<data.now);
        }
      });
      announce(message);
      if(typeof CustomEvent!=='undefined'&&root.dispatchEvent)root.dispatchEvent(new CustomEvent('day-plan-change'));
    }
    function showPreview() {
      if(!drag || !drag.active)return;
      const block=blocks.find(b=>b.kind===drag.kind), rect=lane.getBoundingClientRect();
      const inside=contains(rect,drag.event) && (!scroll || contains(scroll.getBoundingClientRect(),drag.event));
      const next=dropMinute(drag.event,rect,data,drag.offset);
      drag.next=next;
      drag.valid=inside && canPlace(next,block,data,blocks);
      lane.classList.toggle('day-drop-valid',drag.valid);
      lane.classList.toggle('day-drop-invalid',!drag.valid);
      if(ghost){
        ghost.hidden=!inside || next===null;
        ghost.style.top=((next-data.start)/(data.end-data.start)*100)+'%';
        ghost.style.height=(block.minutes/(data.end-data.start)*100)+'%';
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
        offset:unplaced ? 0 : data.start+(event.clientY-rect.top)/rect.height*(data.end-data.start)-block.start};
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
        const block=blocks.find(b=>b.kind===kind),next=firstFree(block,data,blocks);
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
  if(typeof module!=='undefined'&&module.exports)module.exports={overlap,snap,parseClock,dropMinute,placement,canPlace,firstFree,warnings,lanes,mount};
  if(typeof document!=='undefined'){
    document.querySelectorAll('.day-calendar').forEach(mount);
    document.querySelectorAll('.day-scroll').forEach(view=>{const board=view.querySelector('.day-board');if(board)view.scrollTop=Number(view.dataset.scrollMinute||0)/1440*board.getBoundingClientRect().height;});
  }
})();
