"""Shim package per il servizio categorie"""
try:
    from .categorie_service import *  # noqa: F401,F403
except Exception:
    pass
