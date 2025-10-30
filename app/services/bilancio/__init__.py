"""Shim package per i servizi legati al bilancio."""
try:
    # re-export key services
    from app.services.generated_transaction_service import *  # noqa: F401,F403
    from app.services.monthly_summary_service import *  # noqa: F401,F403
    from app.services.dettaglio_periodo_service import *  # noqa: F401,F403
except Exception:
    pass
