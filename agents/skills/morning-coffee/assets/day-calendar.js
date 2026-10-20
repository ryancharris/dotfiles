/* All movement is local visualization. No provider calls or snapshot mutation. */
(function () {
  'use strict';
  const overlap = (a, b) => a.start < b.end && b.start < a.end;
  const snap = n => Math.round(n / 15) * 15;
  const clock = n => String(Math.floor(n / 60)).padStart(2, '0') + ':' + String(n % 60).padStart(2, '0');
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
    const board = root.querySelector('.day-board');
    const lane = root.querySelector('.day-plan-lane');
    const status = root.querySelector('.day-warning');
    let drag = null, locked = false;
    function setLocked(value) {
      locked=Boolean(value);
      if(root.dataset)root.dataset.planLocked=String(locked);
      drag=null;
      blocks.forEach(block=>{
        const button=lane.querySelector('[data-kind="'+block.kind+'"]');
        const control=root.querySelector('.day-control[data-kind="'+block.kind+'"]');
        button.disabled=locked;
        button.classList.remove('day-moving');
        control.querySelector('input').disabled=locked;
        control.querySelector('[data-place]').disabled=locked;
        control.querySelector('[data-remove]').disabled=locked;
      });
      root.querySelector('.day-reset').disabled=locked;
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
      status.textContent=(message ? message+' · ' : '')+warnings(data,blocks).join(' · ');
      if(typeof CustomEvent!=='undefined'&&root.dispatchEvent)root.dispatchEvent(new CustomEvent('day-plan-change'));
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
      control.querySelector('input').addEventListener('change',event=>{
        if(locked){const block=blocks.find(b=>b.kind===kind);event.target.value=block.start===null?'':clock(block.start);return;}
        const value=event.target.value;
        if(!value){blocks.find(b=>b.kind===kind).start=null;render();return;}
        const parts=value.split(':').map(Number);setTime(kind,parts[0]*60+parts[1],true);
      });
      control.querySelector('[data-place]').addEventListener('click',()=>{
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
      button.addEventListener('pointerdown',event=>{
        if(locked||event.button!==0)return;
        drag={kind,pointer:event.pointerId,y:event.clientY,start:blocks.find(b=>b.kind===kind).start};
        button.setPointerCapture(event.pointerId);button.classList.add('day-moving');event.preventDefault();
      });
      button.addEventListener('pointermove',event=>{
        if(locked || !drag || drag.kind!==kind || drag.pointer!==event.pointerId)return;
        const height=board.getBoundingClientRect().height;
        if(height)setTime(kind,drag.start+(event.clientY-drag.y)/height*(data.end-data.start));
      });
      const finish=event=>{
        if(locked)return;
        if(drag&&drag.kind===kind&&drag.pointer===event.pointerId){
          if(event.type==='pointercancel'){
            const block=blocks.find(b=>b.kind===kind);
            if(canPlace(drag.start,block,data,blocks))block.start=drag.start;
            render();
          }
          drag=null;button.classList.remove('day-moving');
        }
      };
      button.addEventListener('pointerup',finish);button.addEventListener('pointercancel',finish);button.addEventListener('lostpointercapture',finish);
    });
    root.querySelector('.day-reset').addEventListener('click',()=>{if(locked)return;blocks=original.map(b=>({...b}));render('Original suggestions restored');});
    render();
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={overlap,snap,placement,canPlace,firstFree,warnings,lanes,mount};
  if(typeof document!=='undefined'){
    document.querySelectorAll('.day-calendar').forEach(mount);
    document.querySelectorAll('.day-scroll').forEach(view=>{const board=view.querySelector('.day-board');if(board)view.scrollTop=Number(view.dataset.scrollMinute||0)/1440*board.getBoundingClientRect().height;});
  }
})();
