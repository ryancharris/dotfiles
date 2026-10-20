/* Completion marks belong to this local brief store, independently of provider approvals. */
(function () {
  'use strict';
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
      if(enabled)status.textContent='Local only';
      button.addEventListener('click',async()=>{
        if(!enabled || busy)return;
        const kind=row.dataset.reviewKind,url=row.dataset.reviewUrl,done=row.dataset.reviewDone!=='true';
        busy=true;button.disabled=true;
        show(done ? 'Saving local done mark…' : 'Undoing local done mark…');
        try{
          const response=await save(config.endpoint,{method:'POST',credentials:'omit',headers:{'Content-Type':'application/json','X-Brief-Token':config.token},body:JSON.stringify({kind,url,done})});
          const result=await response.json();
          if(!response.ok || !result.ok)throw Error(result.error || 'The local review mark could not be saved.');
          const record=result.record;
          if(!record || record.kind!==kind || record.url!==url || record.done!==done)throw Error('The local server did not confirm this review mark.');
          row.dataset.reviewDone=String(done);
          label.textContent=done ? 'Done locally' : 'To review';
          button.textContent=done ? 'Undo local done' : 'Mark done locally';
          button.setAttribute('aria-pressed',String(done));
          show(done ? 'Saved: Done locally.' : 'Saved: back To review.');
          row.dispatchEvent(new CustomEvent('local-review-change',{bubbles:true}));
          if(row.hidden){
            const queue=row.closest('.pr-queue'),count=queue && queue.querySelector('.pr-count');
            if(count){count.tabIndex=-1;count.focus({preventScroll:true});}
          }
        }catch(error){
          show('Save not confirmed: '+error.message+' Previous local status is still shown. Retry to save.');
        }finally{busy=false;button.disabled=false;}
      });
    });
  }
  if(typeof module!=='undefined' && module.exports)module.exports={mount};
  if(typeof document!=='undefined')mount(document);
})();
