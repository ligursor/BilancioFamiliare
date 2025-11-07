// Shared JS for dettaglio_mese - expects initDettaglio(config) to be called.
(function(window){
    'use strict';

    function formatEuro(v){ return '€ ' + Number(v || 0).toFixed(2); }

    function createTransactionRow(tx, cfg){
        var tr = document.createElement('tr');
        var descr = document.createElement('td'); descr.className='text-start'; descr.textContent = tx.descrizione || '';
        var dataTd = document.createElement('td'); dataTd.className='text-center'; dataTd.textContent = tx.data ? new Date(tx.data).toLocaleDateString('it-IT') : '';
    var catTd = document.createElement('td'); catTd.className='text-center'; var spanCat = document.createElement('span'); spanCat.className = 'badge ' + (tx.tipo==='entrata' ? 'bg-success' : 'bg-danger'); var catName = tx.categoria_nome || tx.categoria || ''; spanCat.textContent = catName; catTd.appendChild(spanCat);
        var tipoTd = document.createElement('td'); tipoTd.className='text-center'; tipoTd.innerHTML = tx.tipo==='entrata' ? '<span class="text-success"><i class="fas fa-arrow-up"></i> Entrata</span>' : '<span class="text-danger"><i class="fas fa-arrow-down"></i> Uscita</span>';
        var importoTd = document.createElement('td'); importoTd.className='text-center ' + (tx.tipo==='entrata' ? 'text-success' : 'text-danger'); importoTd.textContent = (tx.tipo==='entrata' ? '+' : '-') + formatEuro(Number(tx.importo||0));
        var azTd = document.createElement('td'); azTd.className='text-center';
        var btnGroup = document.createElement('div'); btnGroup.className='btn-group btn-group-sm'; btnGroup.setAttribute('role','group');
    var editBtn = document.createElement('button'); editBtn.className='btn btn-outline-primary btn-sm'; editBtn.setAttribute('title','Modifica transazione'); editBtn.setAttribute('data-id', tx.id); editBtn.setAttribute('data-descrizione', JSON.stringify(tx.descrizione||'')); editBtn.setAttribute('data-importo', tx.importo); editBtn.setAttribute('data-data', JSON.stringify(tx.data||'')); editBtn.setAttribute('data-categoria', tx.categoriaId || tx.categoria_id || tx.categoria || ''); editBtn.setAttribute('data-action','modifica-transazione-attr'); editBtn.innerHTML = '<i class="fas fa-edit" aria-hidden="true"></i>';
        btnGroup.appendChild(editBtn);
        var delForm = document.createElement('form'); delForm.method='POST'; delForm.style.display='inline'; delForm.setAttribute('action', '/dettaglio/' + encodeURIComponent(cfg.start_date) + '/' + encodeURIComponent(cfg.end_date) + '/elimina_transazione/' + encodeURIComponent(tx.id)); delForm.setAttribute('data-action','confirm-delete'); delForm.setAttribute('data-message','Sei sicuro di voler eliminare questa transazione?');
        var delBtn = document.createElement('button'); delBtn.type='submit'; delBtn.className='btn btn-outline-danger btn-sm'; delBtn.setAttribute('title','Elimina transazione'); delBtn.innerHTML = '<i class="fas fa-trash" aria-hidden="true"></i>';
        delForm.appendChild(delBtn);
        btnGroup.appendChild(delForm);
        azTd.appendChild(btnGroup);
        tr.appendChild(descr); tr.appendChild(dataTd); tr.appendChild(catTd); tr.appendChild(tipoTd); tr.appendChild(importoTd); tr.appendChild(azTd);
        return tr;
    }

    function updateBudgetItems(items){
        try{
            (items || []).forEach(function(b){
                var id = b.categoria_id;
                var el = document.querySelector('.spese-effettuate-val[data-categoria-id="'+id+'"]'); if (el) el.textContent = formatEuro(b.spese_effettuate);
                el = document.querySelector('.spese-pianificate-val[data-categoria-id="'+id+'"]'); if (el) el.textContent = formatEuro(b.spese_pianificate);
                el = document.querySelector('.iniziale-val[data-categoria-id="'+id+'"]'); if (el) el.textContent = formatEuro(b.iniziale);
                el = document.querySelector('.residuo-val[data-categoria-id="'+id+'"]'); if (el) { el.textContent = formatEuro(b.residuo); if (Number(b.residuo) < 0) { el.classList.remove('text-success'); el.classList.add('text-danger'); } else { el.classList.remove('text-danger'); el.classList.add('text-success'); } }
            });
        } catch(e){ console && console.error && console.error('updateBudgetItems error', e); }
    }

    function applySummary(summary){
        try{
            if (!summary) return;
            if (summary.entrate !== undefined && document.getElementById('entrate_val')) document.getElementById('entrate_val').textContent = formatEuro(summary.entrate);
            if (summary.uscite !== undefined && document.getElementById('uscite_val')) document.getElementById('uscite_val').textContent = formatEuro(summary.uscite);
            if (summary.bilancio !== undefined && document.getElementById('bilancio_val')) document.getElementById('bilancio_val').textContent = (Number(summary.bilancio) >= 0 ? '+' : '') + formatEuro(Math.abs(summary.bilancio));
            if (summary.saldo_iniziale_mese !== undefined && document.getElementById('saldo_iniziale_val')) document.getElementById('saldo_iniziale_val').textContent = formatEuro(summary.saldo_iniziale_mese);
            if (summary.saldo_attuale_mese !== undefined && document.getElementById('saldo_attuale_val')) document.getElementById('saldo_attuale_val').textContent = formatEuro(summary.saldo_attuale_mese);
            if (summary.saldo_finale_mese !== undefined && document.getElementById('saldo_finale_val')) document.getElementById('saldo_finale_val').textContent = formatEuro(summary.saldo_finale_mese);
            // If template shows combined "saldo finale + residui" element, update it as well
            try{
                var el = document.getElementById('saldo_finale_plus_residui_val');
                if (el) {
                    if (summary && typeof summary.saldo_finale_plus_residui !== 'undefined') {
                        el.textContent = ' / ' + formatEuro(Number(summary.saldo_finale_plus_residui || 0));
                    } else if (summary && summary.budget_items) {
                        var sumResidui = (summary.budget_items || []).reduce(function(acc, b){ return acc + (Number((b && (b.residuo || b.residuo === 0)) ? b.residuo : (b && b.residuo) || 0) || 0); }, 0) || 0;
                        var base = Number(summary.saldo_finale_mese || 0);
                        var total = base + sumResidui;
                        el.textContent = ' / ' + formatEuro(total);
                    }
                }
            }catch(e){ console && console.error && console.error('update saldo_finale_plus_residui error', e); }
            if (summary.budget_items) updateBudgetItems(summary.budget_items);
            // cache latest stats so modal/chart can render on demand
            try {
                if (summary.stats_categorie && Array.isArray(summary.stats_categorie)) {
                    try { window._dettaglio_latest_stats = summary.stats_categorie; } catch(e) {}
                }
            } catch(e) { console && console.error && console.error('cache stats error', e); }
        } catch(e){ console && console.error && console.error('applySummary error', e); }
    }

    function bindInlineAdd(cfg){
        try{
            var inlineForm = document.getElementById('inlineAddTransactionForm');
            if (!inlineForm) return;
            // reset any previous listeners by cloning
            var clone = inlineForm.cloneNode(true);
            inlineForm.parentNode.replaceChild(clone, inlineForm);
            clone.addEventListener('submit', function(evt){
                evt.preventDefault();
                var fd = new FormData(clone);
                var d = fd.get('data');
                if (!d || d < cfg.start_date || d > cfg.end_date) { showToast('La data deve essere compresa nel periodo ' + cfg.start_date + ' - ' + cfg.end_date, 'warning'); return; }
                var url = '/dettaglio/' + encodeURIComponent(cfg.start_date) + '/' + encodeURIComponent(cfg.end_date) + '/aggiungi_transazione';
                fetch(url, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then(function(resp){ if (!resp.ok) throw new Error('Server error'); return resp.json(); })
                .then(function(json){ if (!json || json.status !== 'ok') throw new Error('Errore creazione transazione'); if (json.summary) applySummary(json.summary); if (json.transazione) { var tbody = document.querySelector('#tabella-transazioni table tbody'); if (tbody) { tbody.insertBefore(createTransactionRow(json.transazione, cfg), tbody.firstChild); } } var inlineBox = document.getElementById('inline-add-transaction'); if (inlineBox) inlineBox.style.display='none'; clone.reset(); showToast('Transazione aggiunta', 'success'); })
                .catch(function(e){ console.error(e); showToast('Errore durante l\'inserimento. Riprova.','danger'); });
            });
            var cancel = document.getElementById('inline_add_cancel'); if (cancel) cancel.addEventListener('click', function(){ var inlineBox = document.getElementById('inline-add-transaction'); if (inlineBox) inlineBox.style.display='none'; });
        }catch(e){ console && console.error && console.error('bindInlineAdd error', e); }
    }

    function initPie(cfg){
        try{
            var stats = cfg.stats_categorie || [];
            // render into the modal canvas
            var canvas = document.getElementById('uscitePieChartModal');
            var noDataEl = document.getElementById('uscitePieModalNoData');
            if (!canvas) return;
            if (!stats || stats.length === 0) {
                if (noDataEl) noDataEl.style.display = 'block';
                if (canvas.__chart_instance) { try { canvas.__chart_instance.destroy(); } catch(e){}; canvas.__chart_instance = null; }
                return;
            }
            if (noDataEl) noDataEl.style.display = 'none';
                var labels = stats.map(function(s){ return s.categoria_nome || 'Categoria'; });
                var data = stats.map(function(s){ return Math.abs(Number(s.importo) || 0); });
                // compute percentages for legend/datalabels
                var total = data.reduce(function(acc, v){ return acc + (Number(v)||0); }, 0) || 0;
                var percentages = data.map(function(v){ return total ? (Number(v)/total * 100) : 0; });
                // create legend labels with percentages (e.g. "Spesa (23.4%)")
                var labelsWithPct = labels.map(function(l, i){ return l + ' (' + (percentages[i] ? percentages[i].toFixed(1) : '0.0') + '%)'; });
            var palette = ['#3366CC','#DC3912','#FF9900','#109618','#990099','#0099C6','#DD4477','#66AA00','#B82E2E','#316395'];
            var bg = labels.map(function(_,i){ return palette[i % palette.length]; });
            var ctx = canvas.getContext('2d');
            if (canvas.__chart_instance) { try { canvas.__chart_instance.destroy(); } catch(e){}; canvas.__chart_instance = null; }
                var chart = new Chart(ctx, {
                    type: 'pie',
                    data: { labels: labelsWithPct, datasets: [{ data: data, backgroundColor: bg }] },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: { boxWidth: 12, padding: 8 }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(ctx) {
                                        var v = ctx.parsed || 0;
                                        var pct = total ? (v / total * 100) : 0;
                                        return ctx.label.split(' (')[0] + ': ' + v.toFixed(2) + ' € (' + pct.toFixed(1) + '%)';
                                    }
                                }
                            },
                            datalabels: {
                                color: '#ffffff',
                                formatter: function(value, ctx) {
                                    var pct = total ? (value / total * 100) : 0;
                                    return pct > 0 ? pct.toFixed(1) + '%' : '';
                                },
                                font: { weight: '600', size: 12 },
                                anchor: 'center',
                                clamp: true
                            }
                        }
                    },
                    plugins: (typeof ChartDataLabels !== 'undefined') ? [ChartDataLabels] : []
                });
            canvas.__chart_instance = chart;
        }catch(e){ console && console.error && console.error('initPie error', e); }
    }

    function initNavigation(cfg){
        try{
            const currentYear = Number(cfg.anno || 0);
            const currentMonth = Number(cfg.mese || 0);
            function monthExists(y, m) { return (cfg.availableMonths || []).some(function(x){ return Number(x.year) === Number(y) && Number(x.month) === Number(m); }); }
            window.navigateMonth = function(direction) {
                var y = currentYear; var m = currentMonth + Number(direction);
                if (m < 1) { m = 12; y = y - 1; }
                if (m > 12) { m = 1; y = y + 1; }
                if (!monthExists(y,m)) return; window.location.href = '/dettaglio/' + encodeURIComponent(y) + '/' + encodeURIComponent(m);
            };
            document.addEventListener('DOMContentLoaded', function(){
                try{
                    var prevBtn = document.querySelector('.nav-arrow[data-direction="-1"]');
                    var nextBtn = document.querySelector('.nav-arrow[data-direction="1"]');
                    if (prevBtn) { var py = currentYear; var pm = currentMonth - 1; if (pm < 1) { pm = 12; py -= 1; } if (!monthExists(py, pm)) { prevBtn.disabled = true; prevBtn.setAttribute('aria-disabled','true'); } }
                    if (nextBtn) { var ny = currentYear; var nm = currentMonth + 1; if (nm > 12) { nm = 1; ny += 1; } if (!monthExists(ny, nm)) { nextBtn.disabled = true; nextBtn.setAttribute('aria-disabled','true'); } }
                }catch(e){}
            });
        }catch(e){}
    }

    // sorting removed — UI no longer exposes sort controls for Data/Importo

    function bindDelegatedHandlers(cfg){
        document.addEventListener('submit', function(e){
            var form = e.target; if (!form) return;
            var act = form.getAttribute('action') || form.action || '';
            if (act && act.indexOf('/modifica_transazione/') !== -1) {
                e.preventDefault(); var fd = new FormData(form);
                fetch(act, { method:'POST', body:fd, credentials:'same-origin', headers:{ 'X-Requested-With':'XMLHttpRequest' } }).then(function(resp){ if (!resp.ok) throw new Error('Server error'); return resp.json(); }).then(function(json){ if (json && json.status==='ok') { if (json.summary) applySummary(json.summary); } else { throw new Error('Update error'); } }).catch(function(err){ console.error('Errore modifica inline', err); showToast('Errore nel salvataggio. Riprova.','danger'); });
                return false;
            }
            if (form.getAttribute && form.getAttribute('data-action') === 'confirm-delete') {
                e.preventDefault(); e.stopPropagation();
                var msg = form.getAttribute('data-message') || 'Sei sicuro di voler procedere?';
                var confirmFn = (window.showGlobalConfirm && typeof window.showGlobalConfirm === 'function') ? window.showGlobalConfirm : function(m){ return Promise.resolve(false); };
                confirmFn(msg).then(function(ok){
                    if (!ok) return;
                    var action = form.getAttribute('action') || form.action;
                    fetch(action, { method: 'POST', credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function(resp){ if (!resp.ok) throw new Error('Server error'); return resp.json(); }).then(function(json){ if (!json || json.status !== 'ok') throw new Error('Errore cancellazione'); if (json.summary) applySummary(json.summary); var row = form.closest('tr'); if (row) row.parentNode.removeChild(row); }).catch(function(err){ console.error('Errore cancellazione transazione', err); showToast('Errore durante la cancellazione. Riprova.','danger'); });
                }).catch(function(){ /* ignore */ });
            }
        });
    }

    function initDettaglio(cfg){
        try{
            // expose helpers globally that templates may call
            window.applySummary = applySummary;
            window.createTransactionRow = function(tx){ return createTransactionRow(tx, cfg); };
            // init pieces
            bindDelegatedHandlers(cfg);
            bindInlineAdd(cfg);
            // Do not init the pie chart automatically; render it on user request
            // initPie(cfg);
            initNavigation(cfg);

            // bind toggle button if present
            try{
                var btn = document.getElementById('togglePieBtn');
                if (btn) {
                    btn.addEventListener('click', function(){
                        var modalEl = document.getElementById('uscitePieModal');
                        if (!modalEl) return;

                        // Use Bootstrap's modal if available, otherwise fallback
                        var bsModal = null;
                        if (window.bootstrap && typeof window.bootstrap.Modal === 'function') {
                            bsModal = new window.bootstrap.Modal(modalEl, { keyboard: true });
                        }

                        // update button icon + label to 'closing' state
                        var icon = btn.querySelector('i');
                        var label = btn.querySelector('.toggle-pie-text');
                        if (icon) icon.className = 'fas fa-times me-1';
                        if (label) label.textContent = 'Nascondi grafico';
                        btn.setAttribute('aria-pressed','true');

                        // when modal shown, render chart
                        function onShown(){
                            try{
                                var stats = window._dettaglio_latest_stats || cfg.stats_categorie || [];
                                initPie({ stats_categorie: stats, start_date: cfg.start_date, end_date: cfg.end_date });
                            }catch(e){ console && console.error && console.error('render modal pie error', e); }
                            modalEl.removeEventListener('shown.bs.modal', onShown);
                        }
                        modalEl.addEventListener('shown.bs.modal', onShown);

                        // when modal hidden, destroy chart and reset button
                        function onHidden(){
                            try{
                                var canvas = document.getElementById('uscitePieChartModal');
                                if (canvas && canvas.__chart_instance) { try { canvas.__chart_instance.destroy(); } catch(e){}; canvas.__chart_instance = null; }
                                var icon = btn.querySelector('i');
                                var label = btn.querySelector('.toggle-pie-text');
                                if (icon) icon.className = 'fas fa-chart-pie me-1';
                                if (label) label.textContent = 'Mostra grafico';
                                btn.setAttribute('aria-pressed','false');
                                try { btn.focus(); } catch(e) {}
                                // Defensive cleanup: remove any lingering backdrops and restore body styles
                                try {
                                    var remnants = document.querySelectorAll('.modal-backdrop');
                                    remnants.forEach(function(r){ if (r && r.parentNode) r.parentNode.removeChild(r); });
                                } catch(e) {}
                                try { document.body.classList.remove('modal-open'); } catch(e) {}
                                try { document.body.style.paddingRight = ''; document.body.style.overflow = ''; } catch(e) {}
                            }catch(e){ console && console.error && console.error('cleanup modal pie error', e); }
                            modalEl.removeEventListener('hidden.bs.modal', onHidden);
                        }
                        modalEl.addEventListener('hidden.bs.modal', onHidden);

                        if (bsModal) {
                            bsModal.show();
                        } else {
                            // fallback: toggle classes manually
                            modalEl.classList.add('show');
                            modalEl.style.display = 'block';
                            modalEl.setAttribute('aria-modal','true');
                            modalEl.removeAttribute('aria-hidden');
                            // prevent body scroll like bootstrap would
                            document.body.classList.add('modal-open');
                            // create identifiable backdrop so we can remove it on hide
                            var backdrop = document.createElement('div'); backdrop.className = 'modal-backdrop fade show'; backdrop.id = 'uscitePieModal-backdrop'; document.body.appendChild(backdrop);

                            // function to hide fallback modal and clean up
                            var hideFallback = function(){
                                try{
                                    modalEl.classList.remove('show');
                                    modalEl.style.display = 'none';
                                    modalEl.setAttribute('aria-hidden','true');
                                    modalEl.removeAttribute('aria-modal');
                                    var bd = document.getElementById('uscitePieModal-backdrop'); if (bd && bd.parentNode) bd.parentNode.removeChild(bd);
                                    document.body.classList.remove('modal-open');
                                    // clear any inline body styles set by modal behavior
                                    try { document.body.style.paddingRight = ''; document.body.style.overflow = ''; } catch(e) {}
                                    // trigger hidden event so existing handlers (cleanup) run
                                    var evh = new Event('hidden.bs.modal'); modalEl.dispatchEvent(evh);
                                }catch(e){ console && console.error && console.error('hideFallback error', e); }
                            };

                            // clicking backdrop closes modal
                            backdrop.addEventListener('click', function(){ hideFallback(); });
                            // wire up any close buttons inside modal that use data-bs-dismiss
                            var closeButtons = modalEl.querySelectorAll('[data-bs-dismiss="modal"]');
                            closeButtons.forEach(function(b){ b.addEventListener('click', function(evt){ try{ evt.preventDefault(); hideFallback(); }catch(e){} }); });

                            // trigger shown event
                            var ev = new Event('shown.bs.modal'); modalEl.dispatchEvent(ev);
                        }
                    });
                }
            }catch(e){}
        }catch(e){ console && console.error && console.error('initDettaglio error', e); }
    }

    // export
    window.initDettaglio = initDettaglio;

})(window);
