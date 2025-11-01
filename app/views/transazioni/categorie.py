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


@categorie_bp.route('/lista')
def lista():
	"""Compatibilità: vecchio endpoint 'lista' -> reusa index"""
	return index()


@categorie_bp.route('/aggiungi', methods=['POST'])
def aggiungi():
	"""Aggiunge una nuova categorie (richiesto da template)"""
	try:
		nome = request.form.get('nome', '').strip()
		tipo = request.form.get('tipo', '').strip()
		if not nome or not tipo:
			flash('Nome e tipo sono obbligatori', 'error')
			return redirect(url_for('categorie.index'))

		service = CategorieService()
		ok, msg = service.create_categoria(nome, tipo)
		flash(msg, 'success' if ok else 'error')
	except Exception as e:
		flash(f'Errore durante l\'aggiunta della categorie: {str(e)}', 'error')
	return redirect(url_for('categorie.index'))


@categorie_bp.route('/modifica/<int:categoria_id>', methods=['POST'])
def modifica(categoria_id):
	"""Modifica una categorie esistente"""
	try:
		nome = request.form.get('nome', '').strip()
		tipo = request.form.get('tipo', '').strip()
		service = CategorieService()
		ok, msg = service.update_categoria(categoria_id, nome=nome or None, tipo=tipo or None)
		flash(msg, 'success' if ok else 'error')
	except Exception as e:
		flash(f'Errore nella modifica della categorie: {str(e)}', 'error')
	return redirect(url_for('categorie.index'))


@categorie_bp.route('/elimina/<int:categoria_id>', methods=['POST'])
def elimina(categoria_id):
	"""Elimina una categorie"""
	try:
		service = CategorieService()
		ok, msg = service.delete_categoria(categoria_id)
		flash(msg, 'success' if ok else 'error')
	except Exception as e:
		flash(f'Errore nell\'eliminazione della categorie: {str(e)}', 'error')
	return redirect(url_for('categorie.index'))

