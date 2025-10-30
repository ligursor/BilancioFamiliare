"""Shim package per i servizi PayPal."""
try:
    # Re-export the transazioni service from the bilancio package
    from app.services.bilancio.transazioni_service import *  # noqa: F401,F403
except Exception:
    pass
