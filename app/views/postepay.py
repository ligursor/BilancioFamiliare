"""
Blueprint per PostePay Evolution
"""
from flask import Blueprint

postepay_bp = Blueprint('postepay', __name__)

@postepay_bp.route('/')
def dashboard():
    """Dashboard PostePay"""
    return "PostePay - in sviluppo"
