(function(){
  function initFilter() {
  const btn = document.getElementById('filterCategoriaDropdown');
    const menu = document.getElementById('filter_categoria_menu');
    if (!btn || !menu) return; // nothing to do on pages without the dropdown
    // get bootstrap dropdown instance if available
    let bsDropdown = null;
    try { bsDropdown = bootstrap.Dropdown.getOrCreateInstance(btn); } catch(e){ bsDropdown = null; }
  const selectedKey = 'dettaglio_selected_categoria_id';
  let selectedCategoriaId = sessionStorage.getItem(selectedKey) || null;
  const tipoKey = 'dettaglio_selected_tipo';
  let selectedTipo = sessionStorage.getItem(tipoKey) || '';
  // Note: test-mode removed. Filtering is always active. (previously supported disable_filtri_test)

  let categorieList = [];
  try {
    const raw = document.getElementById('categorie-data').textContent;
    categorieList = raw ? JSON.parse(raw) : [];
  } catch(e) { categorieList = []; }

    // Using Bootstrap dropdown: positioning and open/close are handled by Bootstrap JS/CSS.
    // We only populate the menu items below.

  function renderMenu(items) {
    menu.innerHTML = '';
    // 'Tutte' option
    const liAll = document.createElement('li');
    const btnAll = document.createElement('button'); btnAll.type='button'; btnAll.className='dropdown-item'; btnAll.textContent='Tutte';
    btnAll.addEventListener('click', ()=> selectCategoria(null, 'Tutte'));
    liAll.appendChild(btnAll); menu.appendChild(liAll);
    if (!items || items.length === 0) {
      const liEmpty = document.createElement('li');
      const b = document.createElement('span'); b.className = 'dropdown-item text-muted'; b.textContent = 'Nessuna categoria';
      liEmpty.appendChild(b); menu.appendChild(liEmpty); return;
    }
    items.forEach(c => {
      const li = document.createElement('li');
      const b = document.createElement('button'); b.type='button'; b.className='dropdown-item'; b.textContent = c.nome; b.dataset.id = c.id;
      b.addEventListener('click', ()=> selectCategoria(c.id, c.nome));
      li.appendChild(b);
      menu.appendChild(li);
    });
    // mark active item according to current selection
    markActiveMenuItem();
  }

  // --- Tipo filter menu ---
  const tipoBtnEl = document.getElementById('filterTipoDropdown');
  const tipoMenuEl = document.getElementById('filter_tipo_menu');
  function renderTipoMenu() {
    if (!tipoMenuEl) return;
    tipoMenuEl.innerHTML = '';
    const entries = [ {id: '', nome: 'Tutte'}, {id: 'entrata', nome: 'Entrata'}, {id: 'uscita', nome: 'Uscita'} ];
    entries.forEach(e => {
      const li = document.createElement('li');
      const b = document.createElement('button'); b.type='button'; b.className='dropdown-item'; b.textContent = e.nome; b.dataset.id = e.id;
      b.addEventListener('click', ()=> selectTipo(e.id, e.nome));
      li.appendChild(b); tipoMenuEl.appendChild(li);
    });
    // mark active based on current data-filtro on fallback button
    markActiveTipoItem();
  }

  function markActiveTipoItem() {
    try {
      if (!tipoMenuEl) return;
      const items = tipoMenuEl.querySelectorAll('.dropdown-item');
      const current = selectedTipo || '';
      items.forEach(it => {
        const id = it.dataset.id || '';
        if (String(id) === String(current)) it.classList.add('active'); else it.classList.remove('active');
      });
    } catch(e){}
  }

  function selectTipo(id, nome) {
    try {
      // store selection similarly to categories
      if (!id) { selectedTipo = ''; sessionStorage.removeItem(tipoKey); }
      else {
        selectedTipo = String(id);
        sessionStorage.setItem(tipoKey, selectedTipo);
      }
      // Mutually exclusive: when tipo is selected, clear categoria
      if (selectedTipo) {
        selectedCategoriaId = null;
        sessionStorage.removeItem(selectedKey);
        // reflect in UI
        try { if (window.__categoriaFilter && typeof window.__categoriaFilter.updateButtonIcon === 'function') window.__categoriaFilter.updateButtonIcon('Tutte'); } catch(e){}
        try { markActiveMenuItem(); } catch(e){}
      }
  // apply filters via unified helper
  try { runApplyFilters(); } catch(e){}
      // update badge and icon via exported API
      try { if (window.__categoriaFilter && typeof window.__categoriaFilter.updateTipoIcon === 'function') window.__categoriaFilter.updateTipoIcon(!!selectedTipo, nome); } catch(e){}
      // update badge: prefer the model's filtrate length, fallback to DOM count
      try {
        let visibleCount = 0;
        if (window.BilancioTransazioni && typeof window.BilancioTransazioni.getFiltrate === 'function') {
          visibleCount = (window.BilancioTransazioni.getFiltrate() || []).length;
        } else {
          const tbody = document.querySelector('#tabella-transazioni tbody');
          const rows = tbody ? Array.from(tbody.querySelectorAll('tr')) : [];
          visibleCount = rows.filter(r => r.style.display !== 'none').length;
        }
        if (window.__categoriaFilter && typeof window.__categoriaFilter.updateTipoBadge === 'function') window.__categoriaFilter.updateTipoBadge(visibleCount);
      } catch(e){}
    } catch(e){}
  }

  function markActiveMenuItem() {
    try {
      const items = menu.querySelectorAll('.dropdown-item');
      items.forEach(it => {
        const id = it.dataset.id;
        if (!selectedCategoriaId) {
          // 'Tutte' should be active when no selection
          if (!id) it.classList.add('active'); else it.classList.remove('active');
        } else {
          if (id && String(id) === String(selectedCategoriaId)) it.classList.add('active'); else it.classList.remove('active');
        }
      });
    } catch(e){}
  }

  function selectCategoria(id, nome) {
  if (!id) { selectedCategoriaId = null; sessionStorage.removeItem(selectedKey); }
  else { selectedCategoriaId = String(id); sessionStorage.setItem(selectedKey, selectedCategoriaId); }
  // mark active in menu
  markActiveMenuItem();
  // update icon color and tooltip to reflect selection
  updateButtonIcon(nome || 'Tutte');
  // close bootstrap dropdown if available
  try { if (bsDropdown && typeof bsDropdown.hide === 'function') bsDropdown.hide(); } catch(e){}
    // apply filter immediately by id (if set)
    // always set global for compatibility
    window.selectedCategoriaId = selectedCategoriaId;
    // Mutually exclusive: selecting a category should clear tipo
    try {
      if (selectedCategoriaId) {
        selectedTipo = '';
        sessionStorage.removeItem(tipoKey);
        try { if (window.__categoriaFilter && typeof window.__categoriaFilter.updateTipoIcon === 'function') window.__categoriaFilter.updateTipoIcon(false, ''); } catch(e){}
        try { if (window.__categoriaFilter && typeof window.__categoriaFilter.updateTipoBadge === 'function') window.__categoriaFilter.updateTipoBadge(0); } catch(e){}
        try { markActiveTipoItem(); } catch(e){}
      }
    } catch(e){}
    // Run unified filter invocation (prefers server-side applicaFiltriDettaglio, falls back to client-side)
  try { runApplyFilters(); } catch(e) { /* ignore */ }
  }

  // Helper to run filters preferring server-side function when present
  function runApplyFilters() {
    try {
      // normal flow: prefer server-side applicaFiltriDettaglio, otherwise prefer model.applyFilters if available,
      // finally fallback to client-side reconstruction
      if (typeof applicaFiltriDettaglio === 'function') {
        applicaFiltriDettaglio();
        return;
      }
      if (window.BilancioTransazioni && typeof window.BilancioTransazioni.applyFilters === 'function') {
        // prefer model-driven filtering (reads sessionStorage keys internally)
        try { window.BilancioTransazioni.applyFilters({}); } catch(e) { /* continue to fallback */ }
        return;
      }
      applyClientSideFilter();
    } catch (e) { try { applyClientSideFilter(); } catch(e){} }
  }

  function updateButtonIcon(name) {
    try {
      // keep only the filter icon inside the button
      btn.innerHTML = '';
      const icon = document.createElement('i');
      // always use solid icon to avoid missing FA style; vary color/opacità
      icon.className = 'fas fa-filter';
      if (selectedCategoriaId) {
        icon.classList.add('text-primary');
        icon.classList.remove('filter-muted');
      } else {
        icon.classList.remove('text-primary');
        icon.classList.add('filter-muted');
      }
      btn.appendChild(icon);

      // accessibility label only; do not set native title to avoid tooltips
      btn.setAttribute('aria-label', selectedCategoriaId ? (name || '') : 'Filtra per categoria');

      // ensure badge exists
      let badge = document.getElementById('filterCategoriaBadge');
      if (!badge) {
        badge = document.createElement('span');
        badge.id = 'filterCategoriaBadge';
        badge.className = 'badge bg-danger text-white d-none';
        // place badge as sibling inside the dropdown wrapper (parent of btn)
        const wrapper = btn.parentElement || btn;
        // ensure wrapper is positioned
        try { wrapper.style.position = wrapper.style.position || 'relative'; } catch(e){}
        wrapper.appendChild(badge);
      }
    } catch(e){}
  }

  function applyClientSideFilter(query){
    try {
      // If filters are disabled, try to reset via model or DOM fallback
      if (typeof DISABLE_FILTERS !== 'undefined' && DISABLE_FILTERS) {
        if (window.BilancioTransazioni && typeof window.BilancioTransazioni.applyFilters === 'function') {
          try { window.BilancioTransazioni.applyFilters({categoriaId: null, tipo: ''}); } catch(e){}
          try { if (typeof window.aggiornaTabella === 'function') window.aggiornaTabella(); } catch(e){}
          return;
        }
        if (Array.isArray(window.__serialized_transazioni_originali)) {
          try {
            const arr = window.__serialized_transazioni_originali || [];
            if (window.BilancioTransazioni && typeof window.BilancioTransazioni.setFiltrate === 'function') {
              window.BilancioTransazioni.setFiltrate(arr);
            }
          } catch(e){}
          try { if (typeof window.aggiornaTabella === 'function') window.aggiornaTabella(); } catch(e){}
          return;
        }
        const tbodyReset = document.querySelector('#tabella-transazioni table tbody');
        if (tbodyReset) Array.from(tbodyReset.querySelectorAll('tr')).forEach(r => r.style.display = '');
        try { if (typeof window.aggiornaTabella === 'function') window.aggiornaTabella(); } catch(e){}
        return;
      }

      // Preferred: delegate filtering to the model which implements AND semantics
      const q = (typeof query === 'string') ? query.trim().toLowerCase() : '';
      if (window.BilancioTransazioni && typeof window.BilancioTransazioni.applyFilters === 'function') {
        try {
          window.BilancioTransazioni.applyFilters({ categoriaId: selectedCategoriaId || null, tipo: selectedTipo || '' });
          try { updateBadge((window.BilancioTransazioni.getFiltrate() || []).length); } catch(e){}
        } catch(e) { console.warn('Errore modello rebuild transazioniFiltrate', e); }
        return;
      }

      // Fallback: legacy DOM-only show/hide
      const tbody = document.querySelector('#tabella-transazioni table tbody');
      if (!tbody) return;
      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.forEach(r => {
        const editBtn = r.querySelector('button[onclick^="modificaTransazioneAttr"]');
        const dataCat = editBtn ? editBtn.getAttribute('data-categoria') : null;
        const badge = r.querySelector('td:nth-child(3) .badge');
        const nome = badge ? badge.textContent.trim().toLowerCase() : '';
        let match = true;
        if (selectedCategoriaId) {
          if (dataCat) match = String(dataCat) === String(selectedCategoriaId);
          else {
            const found = categorieList.find(c => String(c.id) === String(selectedCategoriaId));
            const selectedNameRaw = found ? (found.nome || '') : '';
            const norm = s => s ? s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().trim() : '';
            const selectedName = norm(selectedNameRaw);
            const rowName = norm(nome);
            match = selectedName ? rowName === selectedName : false;
          }
        } else if (q) {
          match = nome && nome.includes(q);
        }
        try {
          const tipoCell = r.querySelector('td:nth-child(4)');
          const rowTipo = tipoCell ? (tipoCell.textContent.includes('Entrata') ? 'entrata' : 'uscita') : '';
          if (selectedTipo) match = match && (String(rowTipo) === String(selectedTipo));
        } catch(e){}
        r.style.display = match ? '' : 'none';
      });
      try {
        const visibleCount = rows.filter(rr => rr.style.display !== 'none').length;
        updateBadge(visibleCount);
      } catch(e){}
    } catch(e){ console.warn('Errore filtro client-side', e); }
  }

  function updateBadge(count) {
    try {
      let badge = document.getElementById('filterCategoriaBadge');
      if (!badge) return;
      // show badge only when a specific category is selected (not 'Tutte')
      if (!selectedCategoriaId) {
        badge.classList.add('d-none');
        return;
      }
      badge.textContent = String(count);
      badge.classList.remove('d-none');
    } catch(e){}
  }

  function updateTipoBadge(count) {
    try {
      let badge = document.getElementById('filterTipoBadge');
      const tipoBtn = document.getElementById('filterTipoDropdown');
      if (!tipoBtn) return;
      const wrapper = tipoBtn.parentElement || tipoBtn;
      if (!badge) {
        badge = document.createElement('span'); badge.id = 'filterTipoBadge'; badge.className = 'badge bg-danger text-white d-none';
        try { wrapper.style.position = wrapper.style.position || 'relative'; } catch(e){}
        wrapper.appendChild(badge);
      }
      if (!selectedTipo) { badge.classList.add('d-none'); return; }
      badge.textContent = String(count);
      badge.classList.remove('d-none');
    } catch(e){}
  }

  function updateTipoIcon(active, label) {
    try {
      const tipoBtn = document.getElementById('filterTipoDropdown');
      if (!tipoBtn) return;
      const icon = tipoBtn.querySelector('i');
      if (!icon) return;
      if (active) {
        icon.classList.add('text-primary');
        icon.classList.remove('filter-muted');
      } else {
        icon.classList.remove('text-primary');
        icon.classList.add('filter-muted');
      }
      try { tipoBtn.setAttribute('aria-label', label || (active ? 'Filtro tipo applicato' : 'Filtra per tipo')); } catch(e){}
    } catch(e){}
  }

    // populate menu once when user first toggles it; Bootstrap handles showing/hiding
    let populated = false;
    btn.addEventListener('click', function(e){
      if (!populated) { renderMenu(categorieList); populated = true; }
    });

    // populate tipo menu lazily
    let tipoPopulated = false;
    if (tipoBtnEl) {
      tipoBtnEl.addEventListener('click', function(e){ if (!tipoPopulated) { renderTipoMenu(); tipoPopulated = true; } });
    }

    // Workaround: dropdown menus inside containers with overflow:auto/hidden
    // may be clipped (table-responsive). Temporarily set overflow: visible on
    // ancestor elements while the dropdown is open, and restore after close.
    const alteredAncestors = [];
    function makeAncestorsOverflowVisible() {
      let el = btn.parentElement; // start from dropdown wrapper
      while (el && el !== document.body) {
        try {
          const style = window.getComputedStyle(el);
          if (style && style.overflow !== 'visible') {
            alteredAncestors.push({el, old: el.style.overflow || ''});
            el.style.overflow = 'visible';
          }
        } catch (e) { /* ignore cross-origin or read errors */ }
        el = el.parentElement;
      }
    }
    function restoreAncestorsOverflow() {
      while (alteredAncestors.length) {
        const a = alteredAncestors.pop();
        try { a.el.style.overflow = a.old; } catch(e){}
      }
    }

    // Hook into Bootstrap dropdown show/hide events to toggle overflow fixes
    try {
      btn.addEventListener('show.bs.dropdown', function() { makeAncestorsOverflowVisible(); });
      btn.addEventListener('hidden.bs.dropdown', function() { restoreAncestorsOverflow(); });
    } catch (e) { /* if Bootstrap not present, no-op */ }

    // restore: read both stored categoria and tipo; enforce mutual-exclusivity (tipo wins if present)
    (function(){
      try {
        const storedCategoria = sessionStorage.getItem(selectedKey);
        const storedTipo = sessionStorage.getItem(tipoKey);
        if (storedTipo) {
          // tipo takes precedence: clear categoria
          selectedTipo = storedTipo;
          sessionStorage.setItem(tipoKey, selectedTipo);
          selectedCategoriaId = null;
          sessionStorage.removeItem(selectedKey);
          window.selectedCategoriaId = null;
          // do not auto-apply filters on load; user interaction will apply
        } else if (storedCategoria) {
          selectedCategoriaId = storedCategoria;
          window.selectedCategoriaId = selectedCategoriaId;
          // do not auto-apply filters on load; user interaction will apply
        } else {
          selectedCategoriaId = null;
          window.selectedCategoriaId = null;
        }

        // set initial button label based on stored selection
        if (selectedCategoriaId) {
          const found = categorieList.find(c => String(c.id) === String(selectedCategoriaId));
          updateButtonIcon(found ? found.nome : 'Selezionata');
        } else {
          updateButtonIcon('Tutte');
        }

        // initialize tipo icon/badge
        try {
          const tipoBtn = document.getElementById('filterTipoDropdown');
          if (tipoBtn) {
            if (selectedTipo) {
              if (window.__categoriaFilter && typeof window.__categoriaFilter.updateTipoIcon === 'function') window.__categoriaFilter.updateTipoIcon(true, '');
              try { if (window.__categoriaFilter && typeof window.__categoriaFilter.updateTipoBadge === 'function') window.__categoriaFilter.updateTipoBadge((window.BilancioTransazioni && typeof window.BilancioTransazioni.getFiltrate === 'function') ? (window.BilancioTransazioni.getFiltrate().length || 0) : 0); } catch(e){}
              markActiveTipoItem();
            } else {
              if (window.__categoriaFilter && typeof window.__categoriaFilter.updateTipoIcon === 'function') window.__categoriaFilter.updateTipoIcon(false, '');
            }
          }
        } catch(e){}
      } catch(e) { console.warn('[FILTRO] restore init error', e); }
    })();

    // no custom positioning/transition handling: Bootstrap manages it

  // export API for other scripts after initialization
  window.__categoriaFilter = { selectCategoria, updateBadge, updateTipoBadge, updateButtonIcon, updateTipoIcon };
  // expose runApplyFilters globally for other scripts to call
  try { window.runApplyFilters = runApplyFilters; } catch(e){}

  // If transazioni-model is used, wait for its ready event to update badges and apply initial state
  try {
    document.addEventListener('transazioni:ready', function(){
      try {
        // update tipo badge if needed
        const storedTipo = sessionStorage.getItem(tipoKey) || '';
        if (window.__categoriaFilter && typeof window.__categoriaFilter.updateTipoIcon === 'function') window.__categoriaFilter.updateTipoIcon(!!storedTipo, '');
        try { if (typeof window.runApplyFilters === 'function') window.runApplyFilters(); } catch(e){}
      } catch(e){}
    });
  } catch(e){}
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initFilter); else initFilter();
})();
