"""
Top-level shim for transazioni view. Keeps compatibility while the real
implementation lives under app.views.bilancio.transazioni.
"""
from app.views.bilancio.transazioni import *  # re-export
