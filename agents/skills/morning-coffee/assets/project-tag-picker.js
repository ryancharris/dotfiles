/* Existing and new tags edit the same unsaved task draft. */
(function () {
  'use strict';
  const normalize=value=>value.trim().split(/\s+/).join(' ');
  const tags=value=>{const seen=new Set();return value.split(',').map(normalize).filter(tag=>{if(!tag||seen.has(tag.toLowerCase()))return false;seen.add(tag.toLowerCase());return true;});};
  function mountTagPicker(input,names,draft) {
    if(input.tagPicker){input.tagPicker.update(names);return input.tagPicker;}
    const doc=input.ownerDocument,view=doc.defaultView;
    const node=(tag,text)=>{const item=doc.createElement(tag);if(text!==undefined)item.textContent=text;return item;};
    const wrapper=node('div');wrapper.className='project-tag-picker';
    input.parentNode.insertBefore(wrapper,input);wrapper.append(input);input.removeAttribute('list');
    const select=node('select');select.id=input.id+'-choices';select.className='project-tag-choices';select.setAttribute('aria-label','Choose an existing project tag or create one');
    select.setAttribute('aria-describedby','todo-project-help');
    const chips=node('div');chips.className='project-tag-selections';chips.setAttribute('aria-label','Selected project tags');
    input.hidden=true;
    doc.querySelector('label[for="'+input.id+'"]')?.setAttribute('for',select.id);
    const panel=node('div');panel.className='project-tag-create';panel.hidden=true;
    const label=node('label','New tag');label.htmlFor=input.id+'-new';
    const create=node('input');create.id=label.htmlFor;create.type='text';create.maxLength=120;create.placeholder='New project name';create.autocomplete='off';
    const add=node('button','Add tag');add.type='button';
    const cancel=node('button','Cancel');cancel.type='button';
    const status=node('span');status.className='project-tag-picker-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    panel.append(label,create,add,cancel);wrapper.append(chips,select,panel,status);
    let known=names||[];
    function update(next) {
      if(next)known=next;
      const current=tags(input.value),selected=new Set(current.map(tag=>tag.toLowerCase()));
      chips.replaceChildren();chips.hidden=current.length===0;
      current.forEach(name=>{
        const chip=node('button');chip.type='button';chip.className='project-tag-selection';chip.disabled=input.disabled;
        chip.setAttribute('aria-label','Remove project tag '+name);chip.append(node('span',name));
        const cross=node('span','×');cross.setAttribute('aria-hidden','true');chip.append(cross);
        chip.addEventListener('click',()=>{
          if(input.disabled)return;
          input.value=tags(input.value).filter(tag=>tag.toLowerCase()!==name.toLowerCase()).join(', ');
          input.dispatchEvent(new view.Event('input',{bubbles:true}));
          status.textContent='Tag removed from this draft.';select.focus();
        });chips.append(chip);
      });
      select.replaceChildren();
      const placeholder=node('option','+ Add project');placeholder.value='';select.append(placeholder);
      known.forEach(name=>{const option=node('option',name+(selected.has(name.toLowerCase())?' ✓':''));option.value='tag:'+name;option.disabled=selected.has(name.toLowerCase());select.append(option);});
      const option=node('option','+ Create new tag…');option.value='__create__';select.append(option);
      select.value='';select.disabled=input.disabled;
      [create,add,cancel].forEach(control=>{control.disabled=input.disabled;});
    }
    function append(value) {
      const name=normalize(value),current=tags(input.value);
      if(!name || [...name].length>60 || /[,\u0000-\u001f\u007f-\u009f]/.test(name)){status.textContent='Enter one tag, up to 60 characters, without commas.';return false;}
      if(current.some(tag=>tag.toLowerCase()===name.toLowerCase())){status.textContent='That tag is already selected.';return false;}
      if(current.length>=10){status.textContent='Choose up to 10 tags per task.';return false;}
      input.value=[...current,name].join(', ');input.dispatchEvent(new view.Event('input',{bubbles:true}));
      status.textContent='';update();return true;
    }
    function close() {panel.hidden=true;create.value='';select.value='';select.focus();}
    select.addEventListener('change',()=>{
      if(input.disabled)return;
      if(select.value==='__create__'){panel.hidden=false;create.focus();}
      else if(select.value.startsWith('tag:')){if(append(select.value.slice(4)))close();}
    });
    add.addEventListener('click',()=>{if(!input.disabled && append(create.value))close();else create.focus();});
    cancel.addEventListener('click',()=>{close();status.textContent='';});
    create.addEventListener('keydown',event=>{
      if(event.key==='Enter'){event.preventDefault();event.stopPropagation();add.click();}
      if(event.key==='Escape'){event.preventDefault();event.stopPropagation();cancel.click();}
    });
    input.addEventListener('input',()=>update());
    input.tagPicker={update,focus:()=>select.focus(),getDraft:()=>({open:!panel.hidden,value:create.value}),
      commit:()=>{if(panel.hidden||!create.value.trim())return true;if(append(create.value)){close();return true;}create.focus();return false;},
      reset:()=>{panel.hidden=true;create.value='';status.textContent='';update();}};
    if(draft){panel.hidden=!draft.open;create.value=draft.value||'';}
    update();return input.tagPicker;
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={mountTagPicker};
  if(typeof window!=='undefined'){window.BriefUI=window.BriefUI||{};window.BriefUI.mountTagPicker=mountTagPicker;}
})();
