/* Centralized fetch helpers
   Exposes:
     - window.postForm(action, formData, opts)
         opts.expect: 'json' (default) | 'text' | 'raw'
   This helper sets credentials and X-Requested-With header and provides
   unified error handling. It intentionally delegates to window.showToast
   for user-facing errors when available.
*/
(function(window){
    'use strict';

    function defaultHeaders(isJson) {
        var h = { 'X-Requested-With': 'XMLHttpRequest' };
        if (isJson) h['Content-Type'] = 'application/json';
        return h;
    }

    function postForm(action, formData, opts) {
        opts = opts || {};
        var expect = opts.expect || 'json';
        var headers = opts.headers || {};

        // merge default headers
        var merged = Object.assign({}, defaultHeaders(expect === 'json'), headers);

        var fetchOpts = {
            method: opts.method || 'POST',
            credentials: 'same-origin',
            headers: merged
        };

        if (formData instanceof FormData) fetchOpts.body = formData;
        else if (formData && typeof formData === 'object' && !(formData instanceof String)) {
            // JSON body
            fetchOpts.body = JSON.stringify(formData);
            // ensure content-type
            fetchOpts.headers['Content-Type'] = 'application/json';
        }

        return fetch(action, fetchOpts).then(function(resp){
            if (expect === 'raw') return resp;
            if (!resp.ok) {
                var err = new Error('Server error: ' + resp.status);
                err.response = resp;
                throw err;
            }
            if (expect === 'text') return resp.text();
            return resp.json();
        }).catch(function(err){
            try { if (window.showToast) window.showToast('Errore di comunicazione: ' + (err && err.message ? err.message : 'unknown'), 'danger'); } catch(e) {}
            throw err;
        });
    }

    // Expose
    try { window.postForm = postForm; } catch(e) {}

})(window);
