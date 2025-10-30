"""Compatibility shim kept during migration.

The real implementation lives in the `app.views.postepay_evolution` package.
This file re-exports the package symbols to preserve the previous import path.
"""

from app.views.postepay_evolution import *  # re-export for backward compatibility
