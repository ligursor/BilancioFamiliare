"""Shim package per i servizi conti_personali."""
try:
    from app.services.conti_personali_service import *  # noqa: F401,F403
except Exception:
    pass
