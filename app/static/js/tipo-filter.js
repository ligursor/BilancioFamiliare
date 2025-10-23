(function(){
  // Moved and renamed from categoria-filter.js -> tipo-filter.js
  const tipoKey = 'dettaglio_selected_tipo';
  let selectedTipo = sessionStorage.getItem(tipoKey) || '';

  function initFilter() {
    const tipoBtn = document.getElementById('filterTipoDropdown');
    const tipoMenu = document.getElementById('filter_tipo_menu');
    if (!tipoBtn || !tipoMenu) return;

    let tipoPopulated = false;
    tipoBtn.addEventListener('click', function(){
      if (!tipoPopulated) { renderTipoMenu(); tipoPopulated = true; }
    });

    try { updateTipoIcon(!!selectedTipo, ''); updateTipoBadgeFromModel(); } catch(e){}
    document.addEventListener('transazioni:ready', function(){ try { if (typeof runApplyFilters === 'function') runApplyFilters(); } catch(e){} });
  }

  function renderTipoMenu(){
    const tipoMenu = document.getElementById('filter_tipo_menu');
    if (!tipoMenu) return;
    tipoMenu.innerHTML = '';
    const entries = [ {id: '', nome: 'Tutte'}, {id: 'entrata', nome: 'Entrata'}, {id: 'uscita', nome: 'Uscita'} ];
    entries.forEach(e => {
      const li = document.createElement('li');
      const b = document.createElement('button'); b.type='button'; b.className='dropdown-item'; b.textContent = e.nome; b.dataset.id = e.id;
      b.addEventListener('click', ()=> selectTipo(e.id, e.nome));
      li.appendChild(b); tipoMenu.appendChild(li);
    });
    markActiveTipoItem();
  }

  function markActiveTipoItem(){
    try {
      const tipoMenu = document.getElementById('filter_tipo_menu'); if (!tipoMenu) return;
      const items = tipoMenu.querySelectorAll('.dropdown-item');
      const cur = selectedTipo || '';
      items.forEach(it => { const id = it.dataset.id || ''; if (String(id) === String(cur)) it.classList.add('active'); else it.classList.remove('active'); });
    } catch(e){}
  }

  function selectTipo(id, nome){
    try {
      if (!id) { selectedTipo = ''; sessionStorage.removeItem(tipoKey); }
      else { selectedTipo = String(id); sessionStorage.setItem(tipoKey, selectedTipo); }
      try { runApplyFilters(); } catch(e){}
      updateTipoIcon(!!selectedTipo, nome);
      updateTipoBadgeFromModel();
      markActiveTipoItem();
    } catch(e){}
  }

  function runApplyFilters(){
    try {
      if (typeof applicaFiltriDettaglio === 'function') { applicaFiltriDettaglio(); return; }
      if (window.BilancioTransazioni && typeof window.BilancioTransazioni.applyFilters === 'function') {
        try { window.BilancioTransazioni.applyFilters({ tipo: selectedTipo || '' }); } catch(e){}
        return;
      }
      applyClientSideTipoFilter();
    } catch(e){ try { applyClientSideTipoFilter(); } catch(e){} }
  }

  function applyClientSideTipoFilter(){
    try {
      const tbody = document.querySelector('#tabella-transazioni table tbody');
      if (!tbody) return;
      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.forEach(r => {
        try {
          const tipoCell = r.querySelector('td:nth-child(4)');
          const rowTipo = tipoCell ? (tipoCell.textContent.includes('Entrata') ? 'entrata' : 'uscita') : '';
          const match = !selectedTipo || (String(rowTipo) === String(selectedTipo));
          r.style.display = match ? '' : 'none';
        } catch(e){}
      });
      const visibleCount = rows.filter(rr => rr.style.display !== 'none').length;
      updateTipoBadge(visibleCount);
  } catch(e){ /* console.warn removed */ }
  }

  function updateTipoBadgeFromModel(){
    try {
      let count = 0;
      if (window.BilancioTransazioni && typeof window.BilancioTransazioni.getFiltrate === 'function') count = (window.BilancioTransazioni.getFiltrate() || []).length;
      updateTipoBadge(count);
    } catch(e){}
  }

  function updateTipoBadge(count){
    try {
      const tipoBtn = document.getElementById('filterTipoDropdown');
      if (!tipoBtn) return;
      const wrapper = tipoBtn.parentElement || tipoBtn;
      let badge = document.getElementById('filterTipoBadge');
      if (!badge) { badge = document.createElement('span'); badge.id = 'filterTipoBadge'; badge.className = 'badge bg-danger text-white d-none'; try { wrapper.style.position = wrapper.style.position || 'relative'; } catch(e){} wrapper.appendChild(badge); }
      if (!selectedTipo) { badge.classList.add('d-none'); return; }
      badge.textContent = String(count);
      badge.classList.remove('d-none');
    } catch(e){}
  }

  function updateTipoIcon(active, label){
    try {
      const tipoBtn = document.getElementById('filterTipoDropdown'); if (!tipoBtn) return;
      const icon = tipoBtn.querySelector('i'); if (!icon) return;
      if (active) { icon.classList.add('text-primary'); icon.classList.remove('filter-muted'); } else { icon.classList.remove('text-primary'); icon.classList.add('filter-muted'); }
      try { tipoBtn.setAttribute('aria-label', label || (active ? 'Filtro tipo applicato' : 'Filtra per tipo')); } catch(e){}
    } catch(e){}
  }

  // expose API
  window.__tipoFilter = { updateTipoIcon, updateTipoBadge };
  try { window.runApplyFilters = runApplyFilters; } catch(e){}

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initFilter); else initFilter();
})();
