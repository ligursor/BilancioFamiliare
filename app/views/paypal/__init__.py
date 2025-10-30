"""Shim package per le view PayPal."""
try:
    from app.views.paypal import *  # noqa: F401,F403
except Exception:
    pass
