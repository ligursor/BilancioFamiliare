// Delegated handlers to replace inline onclicks
(function(){
    // Async confirm helper: prefers global modal-based confirm, falls back to native confirm
    function confirmAction(message) {
        try {
            if (window.showGlobalConfirm && typeof window.showGlobalConfirm === 'function') {
                return window.showGlobalConfirm(message);
            }
        } catch (e) {}
        // If modal helper not available, treat as not confirmed to avoid native browser confirm
        return Promise.resolve(false);
    }

    function navigateMonth(direction) {
        // find current path and replace month via data attributes on container if present
        if (typeof window.navigateMonth === 'function') return window.navigateMonth(direction);
    }

    // ordinaDettaglio removed — sorting UI no longer present

    function modificaTransazioneAttrFromElement(el) {
        if (typeof window.modificaTransazioneAttr === 'function') return window.modificaTransazioneAttr(el);
    }
    function openInlineAddTransactionFromElement(el) {
        if (typeof window.toggleInlineAddTransaction === 'function') return window.toggleInlineAddTransaction(el);
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

    // applicaOrdinamento removed — sorting UI no longer present

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
                // 'ordina' removed — no-op (sorting controls removed)
                case 'modifica-transazione-attr':
                    modificaTransazioneAttrFromElement(el);
                    evt.preventDefault();
                    return;
                case 'open-inline-add-transaction':
                    openInlineAddTransactionFromElement(el);
                    evt.preventDefault();
                    return;
                case 'modifica-monthly-budget':
                    modificaMonthlyBudgetFromElement(el);
                    evt.preventDefault();
                    return;
                case 'confirm-delete':
                    evt.preventDefault(); evt.stopPropagation();
                    var msg = el.dataset.message || 'Sei sicuro?';
                    confirmAction(msg).then(function(ok){
                        if (!ok) return;
                        // If anchor with data-href, navigate
                        if (el.tagName === 'A' && el.dataset.href) {
                            window.location.href = el.dataset.href;
                            return;
                        }
                        // If inside a form, submit it programmatically (mark to skip confirm)
                        var form = el.closest('form');
                        if (form) {
                            try { form.setAttribute('data-skip-confirm', '1'); } catch(e) {}
                            try { if (!form.querySelector('input[name="confirm"]')) { var hidden=document.createElement('input'); hidden.type='hidden'; hidden.name='confirm'; hidden.value='1'; form.appendChild(hidden); } } catch(e) {}
                            try { form.submit(); } catch(e) {}
                        }
                    }).catch(function(){ /* ignore */ });
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
                // 'applica-ordinamento' removed — no-op
                default:
                    return;
            }
        } catch (e) {
            // swallow errors to avoid breaking other handlers
            /* console.warn removed */
        }
    }, false);
})();
