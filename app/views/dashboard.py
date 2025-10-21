"""
Blueprint per la dashboard
"""
from flask import Blueprint

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    """Dashboard dettagliata"""
    return "Dashboard - in sviluppo"
