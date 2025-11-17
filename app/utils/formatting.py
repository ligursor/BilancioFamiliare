from flask import current_app


def format_currency(value, fmt=None):
    """Formatta un valore numerico usando il formato definito in `FORMATO_VALUTA`."""
    try:
        if fmt is None:
            fmt = current_app.config.get('FORMATO_VALUTA', '€ {:.2f}') if current_app else '€ {:.2f}'
    except Exception:
        fmt = '€ {:.2f}'

    # normalize value
    try:
        if value is None:
            val = 0.0
        else:
            # Allow Decimal, ints, floats, strings
            val = float(value)
    except Exception:
        try:
            val = float(str(value))
        except Exception:
            val = 0.0

    try:
        return fmt.format(val)
    except Exception:
        # last-resort formatting
        return f'€ {val:.2f}'


def format_decimal(value, decimals=2):
    """Format a numeric value as a plain decimal string with fixed decimals.

    This is useful for data-attributes or JS code that expects a plain numeric
    string (e.g. "123.45") rather than a localized currency string.
    """
    try:
        d = int(decimals)
    except Exception:
        d = 2
    try:
        if value is None:
            v = 0.0
        else:
            v = float(value)
    except Exception:
        try:
            v = float(str(value))
        except Exception:
            v = 0.0
    try:
        fmt = f"{{:.{d}f}}"
        return fmt.format(v)
    except Exception:
        return f"{v:.{d}f}"


def format_number(value):
    """Formatta un valore numerico come intero con separatore delle migliaia

    Usa il punto come separatore delle migliaia (es. 1.234.567). Questa funzione
    è pensata per la visualizzazione di valori come chilometraggi.
    """
    try:
        if value is None:
            v = 0
        else:
            # preferiamo intero per chilometraggi; se è float lo convertiamo
            v = int(value)
    except Exception:
        try:
            v = int(float(str(value)))
        except Exception:
            v = 0
    try:
        return "{:,}".format(v).replace(',', '.')
    except Exception:
        return str(v)
