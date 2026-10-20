/* Notes are user-owned plain text. One in-flight save; conflicting pages retain their draft. */
(() => {
  function mount(section, config, save=fetch, timers={set:(fn,ms)=>setTimeout(fn,ms),clear:id=>clearTimeout(id)}) {
    const input=section.querySelector('textarea'),status=section.querySelector('[role=status]'),retry=section.querySelector('[data-notes-retry]');
    if(!config.endpoint || !config.token){input.readOnly=true;return;}
    let revision=config.notes.revision,confirmed=input.value,busy=false,timer=null,blocked=false;
    const savedTime=stamp=>new Date(stamp).toLocaleTimeString('en-GB',{timeZone:config.timezone||'UTC',hour:'2-digit',minute:'2-digit',hour12:false});
    function schedule(){if(timer!==null)timers.clear(timer);timer=timers.set(()=>{timer=null;persist();},500);}
    async function persist(){
      if(busy || blocked || input.value===confirmed)return;
      const text=input.value,expected=revision;
      busy=true;status.textContent='Saving notes…';retry.hidden=true;
      let success=false;
      try{
        const response=await save(config.endpoint,{method:'POST',credentials:'omit',signal:AbortSignal.timeout(10000),headers:{'Content-Type':'application/json','X-Brief-Token':config.token},body:JSON.stringify({text,revision:expected})});
        const result=await response.json();
        if(response.status===409)blocked=true;
        if(!response.ok || result.ok!==true)throw Error(result.error || 'Notes could not be saved.');
        const note=result.notes;
        if(!note || note.text!==text || !Number.isInteger(note.revision) || note.revision!==expected+1 || typeof note.updated_at!=='string' || !Number.isFinite(Date.parse(note.updated_at)))throw Error('The local server did not confirm this draft.');
        revision=note.revision;confirmed=text;success=true;
        status.textContent=input.value===confirmed?'Saved locally at '+savedTime(note.updated_at)+'.':'Unsaved changes…';
      }catch(error){
        status.textContent='Notes not saved: '+error.message+' Your draft is still here.';
        retry.hidden=blocked;
      }finally{
        busy=false;
        if(success && input.value!==confirmed)schedule();
      }
    }
    input.addEventListener('input',()=>{
      if(blocked)return;
      status.textContent='Unsaved changes…';retry.hidden=true;schedule();
    });
    input.addEventListener('blur',()=>{if(timer!==null){timers.clear(timer);timer=null;}persist();});
    retry.addEventListener('click',persist);
    window.addEventListener('beforeunload',event=>{if(input.value!==confirmed){event.preventDefault();event.returnValue='';}});
    return {persist};
  }
  if(typeof module!=='undefined' && module.exports)module.exports={mount};
  if(typeof document!=='undefined')document.querySelectorAll('#notes').forEach(section=>{
    const node=section.querySelector('#notes-config');if(node)mount(section,JSON.parse(node.textContent));
  });
})();
