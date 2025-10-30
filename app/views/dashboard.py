dashboard_bp = Blueprint('dashboard', __name__)
"""
Top-level shim for dashboard view. Keeps compatibility while the real
implementation lives under app.views.bilancio.dashboard.
"""
from app.views.bilancio.dashboard import *  # re-export
