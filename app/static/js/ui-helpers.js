// Centralized UI helpers: showToast (modal-based), showGlobalConfirm, auto-dismiss alerts, and global confirm handlers
// This file replaces inline definitions previously present in base.html

(function(window, document) {
    'use strict';

    // Helper per mostrare messaggi prominenti mediante modal (sostituisce i toast)
    window.showToast = function(message, type) {
        try {
            var modalEl = document.getElementById('globalMessageModal');
            var titleEl = document.getElementById('globalMessageTitle');
            var headerEl = document.getElementById('globalMessageHeader');
            var bodyEl = document.getElementById('globalMessageBody');
            if (!modalEl || !titleEl || !bodyEl) return;

            // Determine style and title based on type
            var title = 'Messaggio';
            var headerClass = '';
            var iconClass = '';
            if (type === 'success') { title = 'Successo'; headerClass = 'bg-success text-white'; iconClass = 'fa-check-circle'; }
            else if (type === 'warning') { title = 'Attenzione'; headerClass = 'bg-warning text-dark'; iconClass = 'fa-exclamation-circle'; }
            else if (type === 'info') { title = 'Informazione'; headerClass = 'bg-info text-white'; iconClass = 'fa-info-circle'; }
            else { title = 'Errore'; headerClass = 'bg-danger text-white'; iconClass = 'fa-exclamation-triangle'; }

            // Apply header class
            headerEl.className = 'modal-header ' + headerClass;
            titleEl.textContent = title;

            // Insert icon + message
            bodyEl.innerHTML = '<div class="d-flex align-items-start"><i class="fas ' + iconClass + ' fa-2x me-3" aria-hidden="true"></i><div>' + message + '</div></div>';

            // Show modal (modal will be dismissed via OK button or auto-closed for success/info)
            var bsModal = new (window.bootstrap && window.bootstrap.Modal ? window.bootstrap.Modal : window.Modal)(modalEl, { backdrop: 'static' });
            if (bsModal && typeof bsModal.show === 'function') bsModal.show();
            // Auto-close for non-critical messages
            if (type === 'success' || type === 'info') {
                setTimeout(function() { try { if (bsModal && typeof bsModal.hide === 'function') bsModal.hide(); } catch (e) {} }, 3000);
            }
        } catch (e) { console && console.error && console.error('showToast(modal) error', e); }
    };

    // Helper that shows the Bootstrap modal and returns a Promise<boolean>
    function _showConfirmModal(message) {
        return new Promise(function(resolve) {
            try {
                var modalEl = document.getElementById('globalConfirmModal');
                var msgEl = document.getElementById('globalConfirmMessage');
                var okBtn = document.getElementById('globalConfirmOk');
                var cancelBtn = document.getElementById('globalConfirmCancel');
                if (!modalEl || !msgEl || !okBtn || !cancelBtn) {
                    // Modal not present: treat as non-confirmed to avoid native browser confirm dialogs
                    resolve(false);
                    return;
                }
                msgEl.textContent = message || _DEFAULT_CONFIRM_MSG;
                var bsModal = new (window.bootstrap && window.bootstrap.Modal ? window.bootstrap.Modal : window.Modal)(modalEl, { backdrop: 'static' });

                function cleanup() {
                    okBtn.removeEventListener('click', onOk);
                    cancelBtn.removeEventListener('click', onCancel);
                    modalEl.removeEventListener('hidden.bs.modal', onHidden);
                }
                function onOk(e) { cleanup(); try { if (bsModal && typeof bsModal.hide === 'function') bsModal.hide(); } catch(e){} resolve(true); }
                function onCancel(e) { cleanup(); try { if (bsModal && typeof bsModal.hide === 'function') bsModal.hide(); } catch(e){} resolve(false); }
                function onHidden(e) { cleanup(); resolve(false); }

                okBtn.addEventListener('click', onOk);
                cancelBtn.addEventListener('click', onCancel);
                modalEl.addEventListener('hidden.bs.modal', onHidden, { once: true });
                if (bsModal && typeof bsModal.show === 'function') bsModal.show();
            } catch (e) { resolve(false); }
        });
    }

    // Expose a global helper so other scripts can use the same modal-based confirm
    try { window.showGlobalConfirm = _showConfirmModal; } catch(e) { /* ignore */ }

    var _DEFAULT_CONFIRM_MSG = "Sei sicuro di voler procedere con l'eliminazione? Questa operazione non può essere annullata.";

    // Document ready handlers for auto-dismiss and binding confirm behavior
    document.addEventListener('DOMContentLoaded', function() {
        try {
            // Auto-dismiss degli alert dopo 5 secondi
            try {
                const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
                alerts.forEach(function(alert) {
                    setTimeout(function() {
                        try {
                            const bsAlert = window.bootstrap && window.bootstrap.Alert ? new window.bootstrap.Alert(alert) : null;
                            if (bsAlert && typeof bsAlert.close === 'function') bsAlert.close();
                        } catch (e) {}
                    }, 5000); // 5 secondi
                });
            } catch (e) { /* ignore */ }

            // Click handler for elements with data-action="confirm-delete"
            document.body.addEventListener('click', function(evt) {
                try {
                    var btn = evt.target.closest && evt.target.closest('[data-action="confirm-delete"]');
                    if (!btn) return;
                    if (btn.getAttribute('data-skip-confirm') !== null) return;
                    var msg = btn.getAttribute('data-message') || _DEFAULT_CONFIRM_MSG;
                    // Prevent default action and show modal
                    evt.preventDefault(); evt.stopPropagation();
                    var form = btn.closest('form');
                    _showConfirmModal(msg).then(function(confirmed) {
                        if (!confirmed) return;
                        try {
                            if (form) {
                                // ensure we don't re-trigger the confirm handler when submitting programmatically
                                form.setAttribute('data-skip-confirm', '1');
                                if (!form.querySelector('input[name="confirm"]')) {
                                    var hidden = document.createElement('input'); hidden.type='hidden'; hidden.name='confirm'; hidden.value='1'; form.appendChild(hidden);
                                }
                                form.submit();
                            } else {
                                // If it's a plain link/button, try to trigger default behavior
                                var href = btn.getAttribute('href');
                                if (href) window.location.href = href;
                            }
                        } catch (e) { /* ignore */ }
                    }).catch(function(){ /* ignore */ });
                } catch (e) { /* silent */ }
            }, true);

            // Submit handler for forms that look like delete forms
            document.body.addEventListener('submit', function(evt) {
                try {
                    var form = evt.target;
                    if (!form || form.getAttribute === undefined) return;
                    if (form.getAttribute('data-skip-confirm') !== null) return;
                    if (form.getAttribute('onsubmit')) return; // assume page-level handler

                    var dataAction = form.getAttribute('data-action') || '';
                    var cls = (form.className || '').toLowerCase();
                    var action = (form.getAttribute('action') || '').toLowerCase();
                    var shouldConfirm = false;
                    if (dataAction.indexOf('confirm-delete') !== -1) shouldConfirm = true;
                    if (!shouldConfirm && (cls.indexOf('form-delete') !== -1 || cls.indexOf('form-elimina') !== -1)) shouldConfirm = true;
                    if (!shouldConfirm && (action.indexOf('/elimina') !== -1 || action.indexOf('/delete') !== -1)) shouldConfirm = true;
                    if (!shouldConfirm) return;

                    var msg = form.getAttribute('data-message') || _DEFAULT_CONFIRM_MSG;
                    evt.preventDefault(); evt.stopPropagation();
                    _showConfirmModal(msg).then(function(confirmed) {
                        if (!confirmed) return;
                        try {
                            form.setAttribute('data-skip-confirm', '1');
                            if (!form.querySelector('input[name="confirm"]')) { var hidden=document.createElement('input'); hidden.type='hidden'; hidden.name='confirm'; hidden.value='1'; form.appendChild(hidden); }
                            form.submit();
                        } catch (e) { /* ignore */ }
                    }).catch(function(){ /* ignore */ });
                } catch (e) { /* ignore */ }
            }, true);

        } catch (e) { /* ignore */ }
    });

})(window, document);
