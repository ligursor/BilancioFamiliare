// Minimal transazioni model singleton
(function(){
  const Model = {
    originali: [],
    filtrate: [],
    ready: false,
    _listeners: [],
    setOriginali(arr){
      try {
        this.originali = Array.isArray(arr) ? arr : [];
        this.filtrate = [...this.originali];
        // Do NOT write legacy globals here; consumers should use model API.
        this.ready = true;
        document.dispatchEvent(new Event('transazioni:ready'));
        this._listeners.forEach(cb => { try{ cb(); }catch(e){} });
        this._listeners = [];
      } catch(e) { console.warn('[MODEL] setOriginali error', e); }
    },
    getOriginali(){ return this.originali; },
    getFiltrate(){ return this.filtrate; },
    applyFilters(opts){
      try {
        const categoriaId = opts && typeof opts.categoriaId !== 'undefined' ? opts.categoriaId : (sessionStorage.getItem('dettaglio_selected_categoria_id') || null);
        const tipo = opts && typeof opts.tipo !== 'undefined' ? opts.tipo : (sessionStorage.getItem('dettaglio_selected_tipo') || '');
        const orig = this.originali || [];
        // fallback to window.getCategoriaNomeById if available
        const getNome = (id) => { try { return (typeof getCategoriaNomeById === 'function') ? getCategoriaNomeById(id) : ''; } catch(e){ return ''; } };
        this.filtrate = orig.filter(t => {
          let matchCat = true;
          if (categoriaId) {
            matchCat = (String(t.categoriaId || '') === String(categoriaId)) || (String(t.categoria || '') === String(getNome(categoriaId) || ''));
          }
          let matchTipo = true;
          if (tipo) matchTipo = String(t.tipo) === String(tipo);
          return matchCat && matchTipo;
        });
        if (typeof window.aggiornaTabella === 'function') try { window.aggiornaTabella(); } catch(e){}
        try { if (window.__categoriaFilter && typeof window.__categoriaFilter.updateTipoBadge === 'function') window.__categoriaFilter.updateTipoBadge(this.filtrate.length || 0); } catch(e){}
      } catch(e) { console.warn('[MODEL] applyFilters error', e); }
    },
    // Sort the filtered list in-place using known ordering keys and refresh the table
    sortFiltrate(order){
      try {
        const parseDate = (s) => {
          if (!s) return 0;
          try {
            if (s.indexOf('/') !== -1) {
              const parts = s.split('/'); // dd/mm/yyyy
              return parseInt(parts[2] + parts[1].padStart(2,'0') + parts[0].padStart(2,'0'));
            }
            if (s.indexOf('-') !== -1) {
              // yyyy-mm-dd or iso
              return parseInt(s.replace(/-/g,''));
            }
            return parseInt(s) || 0;
          } catch(e){ return 0; }
        };
        switch(order) {
          case 'data_asc':
            this.filtrate.sort((a,b) => parseDate(a.data) - parseDate(b.data));
            break;
          case 'data_desc':
            this.filtrate.sort((a,b) => parseDate(b.data) - parseDate(a.data));
            break;
          case 'importo_asc':
            this.filtrate.sort((a,b) => (a.importo || 0) - (b.importo || 0));
            break;
          case 'importo_desc':
            this.filtrate.sort((a,b) => (b.importo || 0) - (a.importo || 0));
            break;
          default:
            break;
        }
        if (typeof window.aggiornaTabella === 'function') try { window.aggiornaTabella(); } catch(e){}
      } catch(e) { console.warn('[MODEL] sortFiltrate error', e); }
    },
    setFiltrate(arr){
      try {
        this.filtrate = Array.isArray(arr) ? arr : [];
        if (typeof window.aggiornaTabella === 'function') try { window.aggiornaTabella(); } catch(e){}
        try { if (window.__categoriaFilter && typeof window.__categoriaFilter.updateTipoBadge === 'function') window.__categoriaFilter.updateTipoBadge(this.filtrate.length || 0); } catch(e){}
      } catch(e) { console.warn('[MODEL] setFiltrate error', e); }
    },
    onReady(cb){ if (this.ready) { try{ cb(); }catch(e){} } else this._listeners.push(cb); }
  };
  try { window.BilancioTransazioni = Model; } catch(e) { console.warn('[MODEL] expose failed', e); }
  // Note: legacy global proxies removed. Consumers should use the model API exposed on
  // window.BilancioTransazioni: setOriginali, getOriginali, getFiltrate, applyFilters, sortFiltrate, setFiltrate, onReady
})();
