"""Shim package per le view postepay_evolution."""
try:
    from app.views.ppay_evolution import *  # noqa: F401,F403
except Exception:
    pass
