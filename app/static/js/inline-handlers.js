// Delegated handlers to replace inline onclicks
(function(){
    function confirmAction(message) {
        return window.confirm ? window.confirm(message) : true;
    }

    function navigateMonth(direction) {
        // find current path and replace month via data attributes on container if present
        if (typeof window.navigateMonth === 'function') return window.navigateMonth(direction);
    }

    function ordinaDettaglio(tipo) {
        if (typeof window.ordinaDettaglio === 'function') return window.ordinaDettaglio(tipo);
    }

    function modificaTransazioneAttrFromElement(el) {
        if (typeof window.modificaTransazioneAttr === 'function') return window.modificaTransazioneAttr(el);
    }
    function modificaMonthlyBudgetFromElement(el) {
        if (typeof window.modificaMonthlyBudget === 'function') return window.modificaMonthlyBudget(el);
    }

    function modificaAppunto(id) {
        if (typeof window.modificaAppunto === 'function') return window.modificaAppunto(id);
    }

    function trasferisciAppunto(id) {
        if (typeof window.trasferisciAppunto === 'function') return window.trasferisciAppunto(id);
    }

    function eliminaAppuntoFromData(el) {
        if (typeof window.eliminaAppuntoFromData === 'function') return window.eliminaAppuntoFromData(el);
    }

    function setVeicoloId(id) {
        if (typeof window.setVeicoloId === 'function') return window.setVeicoloId(id);
    }

    function modificaAbbonamento(id) {
        if (typeof window.modificaAbbonamento === 'function') return window.modificaAbbonamento(id);
    }

    function applicaOrdinamento(tipo) {
        if (typeof window.applicaOrdinamento === 'function') return window.applicaOrdinamento(tipo);
    }

    document.addEventListener('click', function(evt){
        var el = evt.target;
        // climb up until actionable element
        while(el && el !== document.documentElement) {
            if (el.dataset && el.dataset.action) break;
            el = el.parentElement;
        }
        if (!el || el === document.documentElement) return;

        var action = el.dataset.action;
        try {
            switch(action) {
                case 'navigate-month':
                    navigateMonth(parseInt(el.dataset.direction,10));
                    evt.preventDefault();
                    return;
                case 'ordina':
                    ordinaDettaglio(el.dataset.tipo);
                    evt.preventDefault();
                    return;
                case 'modifica-transazione-attr':
                    modificaTransazioneAttrFromElement(el);
                    evt.preventDefault();
                    return;
                case 'modifica-monthly-budget':
                    modificaMonthlyBudgetFromElement(el);
                    evt.preventDefault();
                    return;
                case 'confirm-delete':
                    var msg = el.dataset.message || 'Sei sicuro?';
                    if (!confirmAction(msg)) {
                        evt.preventDefault();
                        return;
                    }
                    // If anchor with data-href, navigate
                    if (el.tagName === 'A' && el.dataset.href) {
                        window.location.href = el.dataset.href;
                        evt.preventDefault();
                        return;
                    }
                    // Form will submit normally; no-op here
                    return;
                case 'modifica-appunto':
                    modificaAppunto(el.dataset.id);
                    evt.preventDefault();
                    return;
                case 'trasferisci-appunto':
                    trasferisciAppunto(el.dataset.id);
                    evt.preventDefault();
                    return;
                case 'elimina-appunto':
                    eliminaAppuntoFromData(el);
                    evt.preventDefault();
                    return;
                case 'set-veicolo-id':
                    setVeicoloId(el.dataset.id);
                    return;
                case 'modifica-abbonamento':
                    modificaAbbonamento(el.dataset.id);
                    return;
                case 'applica-ordinamento':
                    applicaOrdinamento(el.dataset.tipo);
                    return;
                default:
                    return;
            }
        } catch (e) {
            // swallow errors to avoid breaking other handlers
            /* console.warn removed */
        }
    }, false);
})();
