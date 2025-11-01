"""
Blueprint per le transazioni
Gestisce la lista delle transazioni, filtri e paginazione
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.services.transazioni.transazioni_service import TransazioneService

transazioni_bp = Blueprint('transazioni', __name__)


@transazioni_bp.route('/')
def index():
	"""Mostra le transazioni con filtri e paginazione"""
	try:
		page = int(request.args.get('page', 1))
		per_page = int(request.args.get('per_page', 20))
		tipo_filtro = request.args.get('tipo')
		ordine = request.args.get('ordine', 'data_desc')

		service = TransazioneService()
		pag = service.get_transazioni_with_pagination(page=page, per_page=per_page, tipo_filtro=tipo_filtro, ordine=ordine)

		return render_template('bilancio/transazioni.html', transazioni=pag.items, pagination=pag, tipo_filtro=tipo_filtro, ordine=ordine)
	except Exception as e:
		flash(f'Errore nel caricamento delle transazioni: {str(e)}', 'error')
		return redirect(url_for('main.index'))

