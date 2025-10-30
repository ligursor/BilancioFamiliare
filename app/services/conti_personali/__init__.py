"""Shim package per i servizi conti_personali."""
try:
    # re-export the implementation from the local module
    from .conti_personali_service import *  # noqa: F401,F403
except Exception:
    pass
