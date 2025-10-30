"""Shim package per le view dei conti personali."""
try:
    from app.views.conti_personali import *  # noqa: F401,F403
except Exception:
    pass
