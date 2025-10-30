"""
Blueprint per le categorie
Gestisce la visualizzazione e le operazioni sulle categorie
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.services.categorie.categorie_service import CategorieService

categorie_bp = Blueprint('categorie', __name__)


@categorie_bp.route('/')
def index():
	"""Mostra la lista delle categorie"""
	try:
		service = CategorieService()
		categorie = service.get_all_categories(exclude_paypal=True)
		stats = service.get_categories_stats()
		return render_template('bilancio/categorie.html', categorie=categorie, stats=stats)
	except Exception as e:
		flash(f'Errore nel caricamento delle categorie: {str(e)}', 'error')
		return redirect(url_for('main.index'))

