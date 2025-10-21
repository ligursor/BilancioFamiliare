"""
Blueprint per il garage auto
"""
from flask import Blueprint

garage_bp = Blueprint('garage', __name__)

@garage_bp.route('/')
def dashboard():
    """Dashboard garage"""
    return "Garage - in sviluppo"
