
(() => {
  document.querySelectorAll('.pr-queue').forEach(queue => {
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
    const pageSize = controls.querySelector('[data-page-size]');
    const count = queue.querySelector('.pr-count');
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
        return (!needle || entry.text.includes(needle)) && (!status.value || row.dataset.status === status.value) && (!effort.value || row.dataset.effort === effort.value) && (!team || !team.value || row.dataset.teams.split('|').includes(team.value)) && (!requestType.value || row.dataset.requestType === requestType.value) && (!authors || authors.value === 'all' || row.dataset.authorOnTransport === 'true');
      });
      const size = pageSize.value === 'all' ? Math.max(matches.length, 1) : Number(pageSize.value);
      pageCount = Math.ceil(matches.length / size);
      page = Math.max(1, Math.min(page, pageCount || 1));
      const start = (page - 1) * size;
      const shown = matches.slice(start, start + size);
      rows.forEach(row => {row.hidden = true;});
      shown.forEach(entry => {entry.row.hidden = false;});
      count.textContent = (shown.length ? 'Showing ' + (start + 1) + '–' + (start + shown.length) : 'Showing 0') + ' of ' + matches.length + ' matching · ' + rows.length + ' retained requests · Authors: ' + (authors && authors.value === 'transport' ? 'Transport team' : 'Everyone');
      pageLabel.textContent = 'Page ' + (pageCount ? page : 0) + ' of ' + pageCount;
      previous.disabled = pageCount === 0 || page <= 1;
      next.disabled = pageCount === 0 || page >= pageCount;
      empty.hidden = matches.length !== 0;
    };
    controls.querySelectorAll('[data-filter]').forEach(control => control.addEventListener(control.tagName === 'INPUT' ? 'input' : 'change', () => {page = 1; apply();}));
    pageSize.addEventListener('change', () => {page = 1; apply();});
    controls.querySelector('[data-action="clear"]').addEventListener('click', () => {controls.querySelectorAll('[data-filter]').forEach(control => {control.value = control === authors ? defaultAuthors : '';}); page = 1; apply(); text.focus();});
    previous.addEventListener('click', () => {if (page > 1) {page--; apply();}});
    next.addEventListener('click', () => {if (page < pageCount) {page++; apply();}});
    controls.hidden = false;
    pagination.hidden = false;
    apply();
  });
})();
