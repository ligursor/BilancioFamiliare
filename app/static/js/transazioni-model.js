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
  } catch(e) { /* console.warn removed */ }
    },
    getOriginali(){ return this.originali; },
    getFiltrate(){ return this.filtrate; },
    applyFilters(opts){
      try {
  // Category filter removed. Only consider 'tipo' (entrata/uscita).
  // The tipo filter UI was removed; default to no filter when not provided.
  const tipo = opts && typeof opts.tipo !== 'undefined' ? opts.tipo : '';
        const orig = this.originali || [];
        this.filtrate = orig.filter(t => {
          let matchTipo = true;
          if (tipo) matchTipo = String(t.tipo) === String(tipo);
          return matchTipo;
        });
    if (typeof window.aggiornaTabella === 'function') try { window.aggiornaTabella(); } catch(e){}
  } catch(e) { /* console.warn removed */ }
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
  } catch(e) { /* console.warn removed */ }
    },
    setFiltrate(arr){
      try {
        this.filtrate = Array.isArray(arr) ? arr : [];
    if (typeof window.aggiornaTabella === 'function') try { window.aggiornaTabella(); } catch(e){}
  } catch(e) { /* console.warn removed */ }
    },
    onReady(cb){ if (this.ready) { try{ cb(); }catch(e){} } else this._listeners.push(cb); }
  };
  try { window.BilancioTransazioni = Model; } catch(e) {}
})();
