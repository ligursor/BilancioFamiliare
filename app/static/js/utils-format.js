/* Centralized formatting utilities (numbers/dates) - expose as globals for templates/scripts */
(function(window){
    'use strict';

    // Format number as Euro currency (locale-aware, it-IT)
    // Returns a string like "€ 1.234,56" using the browser locale formatting
    window.formatEuro = function(v){
        try {
            var n = Number(v || 0);
            // Use toLocaleString to respect Italian formatting (comma decimal, dot thousands)
            return n.toLocaleString('it-IT', { style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 2 });
        } catch(e) {
            return '€ 0,00';
        }
    };

    // ISO date (YYYY-MM-DD) from Date or date-parsable value
    window.formatISO = function(d){
        try {
            if (!d) return '';
            var dt = (d instanceof Date) ? d : new Date(d);
            if (isNaN(dt)) return '';
            return dt.getFullYear() + '-' + String(dt.getMonth() + 1).padStart(2,'0') + '-' + String(dt.getDate()).padStart(2,'0');
        } catch(e) { return ''; }
    };

    // Display date localized to it-IT
    window.formatDisplayDate = function(d){
        try {
            if (!d) return '';
            var dt = (d instanceof Date) ? d : new Date(d);
            if (isNaN(dt)) return '';
            return dt.toLocaleDateString('it-IT');
        } catch(e) { return ''; }
    };

    // Pretty short date (e.g. 12 mar 2025)
    window.formatPrettyDate = function(d){
        try {
            if (!d) return '';
            var dt = (d instanceof Date) ? d : new Date(d);
            if (isNaN(dt)) return '';
            var opts = { day: '2-digit', month: 'short', year: 'numeric' };
            return dt.toLocaleDateString('it-IT', opts);
        } catch(e) { return ''; }
    };

    // Convert ISO-ish string to DD/MM/YYYY (tolerant)
    window.formatDateISOtoDDMM = function(dateStr){
        try {
            if (!dateStr) return '';
            var dt = new Date(dateStr);
            if (isNaN(dt)) {
                var parts = String(dateStr).split('-');
                if (parts.length >= 3) {
                    return parts[2].padStart(2,'0') + '/' + parts[1].padStart(2,'0') + '/' + parts[0];
                }
                return '';
            }
            return String(dt.getDate()).padStart(2,'0') + '/' + String(dt.getMonth() + 1).padStart(2,'0') + '/' + dt.getFullYear();
        } catch(e) { return ''; }
    };

        // Generic number formatter - returns fixed decimal string (no currency symbol)
        window.formatNumber = function(v, decimals){
            try { var d = typeof decimals === 'number' ? decimals : 2; return Number(v || 0).toFixed(d); } catch(e) { return (Number(0)).toFixed(decimals || 2); }
        };

        // Parse a formatted Euro string (e.g. "€ 1.234,56", "1.234,56", or "2076.00") into a Number
        // Handles both comma-decimal (it-IT) and dot-decimal formats without mangling the decimal part.
        window.parseEuro = function(s){
            try {
                if (s === null || s === undefined) return 0;
                if (typeof s === 'number') return Number(s);
                var str = String(s).trim();
                // remove currency symbol and whitespace
                str = str.replace(/[€\s]/g, '');

                var hasComma = str.indexOf(',') !== -1;
                var hasDot = str.indexOf('.') !== -1;

                if (hasComma && hasDot) {
                    // common case: dot as thousands, comma as decimal -> remove dots, convert comma to dot
                    str = str.replace(/\./g, '').replace(/,/g, '.');
                } else if (hasComma && !hasDot) {
                    // only comma -> decimal separator
                    str = str.replace(/,/g, '.');
                } else {
                    // only dot or neither -> assume dot is decimal (leave it), but remove any non-numeric chars
                    // (do not strip the dot here because it may be the decimal separator)
                }

                // remove any remaining characters except digits, dot and minus
                str = str.replace(/[^0-9.\-]/g, '');

                var n = Number(str);
                return isNaN(n) ? 0 : n;
            } catch(e) { return 0; }
        };

})(window);
