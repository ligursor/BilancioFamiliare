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
