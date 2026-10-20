
(function () {
 function mountBrief(document) {
  const revealAnchor = hash => {
    const target = document.getElementById(hash.slice(1));
    if (!target) return;
    let parent = target.parentElement;
    while (parent) {
      if (parent.tagName === 'DETAILS') parent.open = true;
      parent = parent.parentElement;
    }
  };
  document.querySelectorAll('a[href^="#"]').forEach(link => {if(link.briefAnchorMounted)return;link.briefAnchorMounted=true;link.addEventListener('click', () => revealAnchor(link.getAttribute('href')));});
  if(!document.briefHashMounted){document.briefHashMounted=true;window.addEventListener('hashchange', () => revealAnchor(window.location.hash));}
  if (window.location.hash) revealAnchor(window.location.hash);
  document.querySelectorAll('.pr-queue').forEach(queue => {
    if(queue.briefMounted)return;
    queue.briefMounted=true;
    const controls = queue.querySelector('.pr-controls');
    if (!controls) return;
    const rows = Array.from(queue.querySelectorAll('tbody tr'));
    const text = controls.querySelector('[data-filter="text"]');
    const status = controls.querySelector('[data-filter="status"]');
    const effort = controls.querySelector('[data-filter="effort"]');
    const team = controls.querySelector('[data-filter="team"]');
    const authors = controls.querySelector('[data-filter="authors"]');
    const defaultAuthors = authors ? (authors.dataset.defaultValue || authors.value) : '';
    const requestType = controls.querySelector('[data-filter="request-type"]');
    const progress = controls.querySelector('[data-filter="progress"]');
    const pageSize = controls.querySelector('[data-page-size]');
    const count = queue.querySelector('.pr-count');
    const filterBadge = queue.querySelector('.pr-filter-badge');
    const empty = queue.querySelector('.pr-empty');
    const pagination = queue.querySelector('.pr-pagination');
    const previous = pagination.querySelector('[data-action="previous"]');
    const next = pagination.querySelector('[data-action="next"]');
    const pageLabel = pagination.querySelector('.pr-page');
    const normalizedRows = rows.map(row => ({row, text: row.textContent.toLocaleLowerCase()}));
    let page = 1;
    let pageCount = 0;
    const apply = () => {
      const needle = text.value.trim().toLocaleLowerCase();
      const matches = normalizedRows.filter(entry => {
        const row = entry.row;
        if (progress && progress.value && (row.dataset.reviewDone === 'true') !== (progress.value === 'done')) return false;
        return (!needle || entry.text.includes(needle)) && (!status.value || row.dataset.status === status.value) && (!effort.value || row.dataset.effort === effort.value) && (!team || !team.value || row.dataset.teams.split('|').includes(team.value)) && (!requestType.value || row.dataset.requestType === requestType.value) && (!authors || authors.value === 'all' || row.dataset.authorOnTransport === 'true');
      });
      const size = pageSize.value === 'all' ? Math.max(matches.length, 1) : Number(pageSize.value);
      pageCount = Math.ceil(matches.length / size);
      page = Math.max(1, Math.min(page, pageCount || 1));
      const start = (page - 1) * size;
      const shown = matches.slice(start, start + size);
      rows.forEach(row => {row.hidden = true;});
      shown.forEach(entry => {entry.row.hidden = false;});
      count.textContent = (shown.length ? 'Showing ' + (start + 1) + '–' + (start + shown.length) : 'Showing 0') + ' of ' + matches.length + ' matching · ' + rows.length + ' retained requests · Authors: ' + (authors && authors.value === 'transport' ? 'Transport team' : 'Everyone') + (progress ? ' · Review progress: ' + (progress.value === 'todo' ? 'To review' : progress.value === 'done' ? 'Done locally' : 'All') : '');
      if (filterBadge) {
        const active = [requestType, status, effort, team].filter(control => control && control.value).length;
        filterBadge.textContent = active + ' active';
        filterBadge.hidden = active === 0;
      }
      pageLabel.textContent = 'Page ' + (pageCount ? page : 0) + ' of ' + pageCount;
      previous.disabled = pageCount === 0 || page <= 1;
      next.disabled = pageCount === 0 || page >= pageCount;
      empty.hidden = matches.length !== 0;
    };
    controls.querySelectorAll('[data-filter]').forEach(control => control.addEventListener(control.tagName === 'INPUT' ? 'input' : 'change', () => {page = 1; apply();}));
    pageSize.addEventListener('change', () => {page = 1; apply();});
    controls.querySelector('[data-action="clear"]').addEventListener('click', () => {controls.querySelectorAll('[data-filter]').forEach(control => {control.value = control === authors ? defaultAuthors : control === progress ? 'todo' : '';}); page = 1; apply(); text.focus();});
    queue.addEventListener('local-review-change', () => {normalizedRows.forEach(entry => {entry.text = entry.row.textContent.toLocaleLowerCase();}); page = 1; apply();});
    const revealPage = () => {
      count.tabIndex = -1;
      count.focus({preventScroll: true});
      count.scrollIntoView({block: 'start', behavior: 'auto'});
    };
    previous.addEventListener('click', () => {if (page > 1) {page--; apply(); revealPage();}});
    next.addEventListener('click', () => {if (page < pageCount) {page++; apply(); revealPage();}});
    controls.hidden = false;
    pagination.hidden = false;
    queue.getBriefFilters=()=>({page,pageSize:pageSize.value,filters:Object.fromEntries(Array.from(controls.querySelectorAll('[data-filter]')).map(control=>[control.dataset.filter,control.value])),expanded:controls.querySelector('.pr-extra-filters')?.open});
    queue.restoreBriefFilters=state=>{
      if(!state)return;
      controls.querySelectorAll('[data-filter]').forEach(control=>{
        const value=state.filters?.[control.dataset.filter];if(value===undefined)return;
        if(control.tagName==='SELECT' && value && !Array.from(control.options).some(option=>option.value===value)){
          const option=document.createElement('option');option.value=value;option.textContent=value;control.append(option);
        }
        control.value=value;
      });
      if(state.pageSize)pageSize.value=state.pageSize;
      const extra=controls.querySelector('.pr-extra-filters');if(extra && state.expanded!==undefined)extra.open=state.expanded;
      page=Number.isInteger(state.page)?state.page:1;apply();
    };
    apply();
  });
 }
 if(typeof module!=='undefined' && module.exports)module.exports={mount:mountBrief};
 if(typeof window!=='undefined'){window.BriefUI=window.BriefUI||{};window.BriefUI.mountBrief=mountBrief;}
 if(typeof document!=='undefined')mountBrief(document);
})();
