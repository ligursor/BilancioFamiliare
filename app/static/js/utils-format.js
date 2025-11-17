/* Centralized formatting utilities (numbers/dates) - expose as globals for templates/scripts */
(function(window){
    'use strict';

    // Format number as Euro currency (simple, consistent across app)
    window.formatEuro = function(v){
        try { return '€ ' + Number(v || 0).toFixed(2); } catch(e) { return '€ 0.00'; }
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

})(window);
