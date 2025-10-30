"""Shim package per i servizi PayPal."""
try:
    from app.services.transazioni_service import *  # noqa: F401,F403
except Exception:
    pass
