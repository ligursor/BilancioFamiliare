"""Shim package per i servizi legati al bilancio."""
try:
    # re-export key services implemented in this package
    from .generated_transaction_service import *  # noqa: F401,F403
    from .monthly_summary_service import *  # noqa: F401,F403
    from .dettaglio_periodo_service import *  # noqa: F401,F403
    from .transazioni_service import *  # noqa: F401,F403
except Exception:
    # In fase di deploy/aggiornamento, evitare di rompere import per errori temporanei
    pass
