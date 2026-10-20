/* Completion marks belong to this local brief store, independently of provider approvals. */
(function () {
  'use strict';
  function regroupRfc(doc, row, button, message) {
    if(row.dataset.reviewKind!=='rfc')return;
    const section=row.closest('#rfcs-to-review');
    if(!section)return;
    const pending=section.querySelector('[data-rfc-pending]');
    const completed=section.querySelector('[data-rfc-completed-list]');
    const archive=section.querySelector('[data-rfc-completed]');
    if(!pending || !completed || !archive)return;
    const grouped=row.dataset.sourceApproved==='true' || row.dataset.reviewDone==='true';
    const destination=grouped ? completed : pending;
    const moved=row.parentElement!==destination;
    if(moved){
      const next=Array.from(destination.children).find(other=>Number(other.dataset.reviewOrder)>Number(row.dataset.reviewOrder));
      destination.insertBefore(row,next || null);
    }
    const pendingCount=pending.children.length,completedCount=completed.children.length;
    section.querySelector('[data-rfc-pending-count]').textContent=String(pendingCount);
    section.querySelector('[data-rfc-completed-count]').textContent=String(completedCount);
    section.querySelector('[data-rfc-empty]').hidden=pendingCount!==0;
    archive.hidden=completedCount===0;
    const teaOverview=typeof doc.getElementById==='function' && doc.getElementById('day-overview');
    const overview=teaOverview && teaOverview.querySelector('[data-rfc-overview]');
    if(overview){
      overview.querySelector('[data-rfc-overview-pending]').textContent=String(pendingCount);
      overview.querySelector('[data-rfc-overview-completed]').textContent=String(completedCount);
      overview.querySelector('[data-rfc-overview-note]').textContent=pendingCount ? 'Full review list below.' : 'No pending RFCs.';
      overview.querySelectorAll('[data-rfc-overview-url]').forEach(item=>{
        if(item.dataset.rfcOverviewUrl===row.dataset.reviewUrl)item.hidden=grouped;
      });
    }
    const announcement=section.querySelector('[data-rfc-group-status]');
    if(announcement)announcement.textContent=message+(moved ? (grouped ? ' Moved to Approved or done.' : ' Returned to RFCs to review.') : '');
    if(moved && grouped && !archive.open)return archive.querySelector('summary');
    if(moved && !grouped)return button;
  }
  function mount(doc, request) {
    const configNode=doc.querySelector('.review-interaction-data');
    const notice=doc.querySelector('.local-review-save-status');
    let config=null;
    if(configNode){
      try{config=JSON.parse(configNode.textContent);}catch(error){if(notice)notice.textContent='Local review saving unavailable. Reopen a live Coffee or Tea session.';}
    }
    const save=request || (typeof fetch==='function' ? fetch : null);
    const enabled=Boolean(config && config.endpoint && config.token && save);
    doc.querySelectorAll('[data-local-review]').forEach(row=>{
      if(row.localReviewMounted)return;
      row.localReviewMounted=true;
      const button=row.querySelector('[data-review-toggle]');
      const label=row.querySelector('.local-review-label');
      const status=row.querySelector('.local-review-message');
      let busy=false;
      const show=message=>{status.textContent=message;if(notice)notice.textContent=message;};
      button.disabled=!enabled;
      if(enabled)status.textContent='';
      button.addEventListener('click',async()=>{
        if(!enabled || busy)return;
        const kind=row.dataset.reviewKind,url=row.dataset.reviewUrl,done=row.dataset.reviewDone!=='true';
        let focusTarget=null;
        busy=true;button.disabled=true;
        show(done ? 'Saving local done mark…' : 'Undoing local done mark…');
        try{
          const response=await save(config.endpoint,{method:'POST',credentials:'omit',signal:AbortSignal.timeout(10000),headers:{'Content-Type':'application/json','X-Brief-Token':config.token},body:JSON.stringify({kind,url,done})});
          const result=await response.json();
          if(!response.ok || !result.ok)throw Error(result.error || 'The local review mark could not be saved.');
          const record=result.record;
          if(!record || record.kind!==kind || record.url!==url || record.done!==done)throw Error('The local server did not confirm this review mark.');
          row.dataset.reviewDone=String(done);
          label.textContent=done ? 'Done locally' : 'To review';
          button.textContent=done ? 'Undo local done' : 'Mark done locally';
          button.setAttribute('aria-pressed',String(done));
          const savedMessage=done ? 'Saved: Done locally.' : 'Saved: back To review.';
          show(savedMessage);
          focusTarget=regroupRfc(doc,row,button,savedMessage);
          row.dispatchEvent(new CustomEvent('local-review-change',{bubbles:true}));
          if(row.hidden){
            const queue=row.closest('.pr-queue'),count=queue && queue.querySelector('.pr-count');
            if(count){count.tabIndex=-1;count.focus({preventScroll:true});}
          }
        }catch(error){
          const unavailable=error instanceof TypeError || error.name==='TimeoutError' || error.name==='AbortError';
          show(unavailable ? 'Local save service unavailable. Reopen today’s live Coffee or Tea report. Previous local status is still shown.' : 'Save not confirmed: '+error.message+' Previous local status is still shown. Retry to save.');
        }finally{
          busy=false;button.disabled=false;
          if(focusTarget)focusTarget.focus({preventScroll:true});
        }
      });
    });
  }
  if(typeof module!=='undefined' && module.exports)module.exports={mount};
  if(typeof document!=='undefined')mount(document);
})();
