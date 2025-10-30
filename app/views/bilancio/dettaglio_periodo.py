"""
Blueprint per il dettaglio periodo
Gestisce le visualizzazioni dettagliate per mese/periodo
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from app.services.bilancio.dettaglio_periodo_service import DettaglioPeriodoService
from app.models.transazioni import Transazione
from app import db
from app.services.categorie.categorie_service import CategorieService
from flask import request, jsonify

dettaglio_periodo_bp = Blueprint('dettaglio_periodo', __name__)

@dettaglio_periodo_bp.route('/')
def index():
	"""Pagina principale dettaglio periodo - mostra mese corrente"""
	oggi = datetime.now()
	return redirect(url_for('dettaglio_periodo.mese', 
						  anno=oggi.year, 
						  mese=oggi.month))

@dettaglio_periodo_bp.route('/<int:anno>/<int:mese>')
def mese(anno, mese):
	"""Visualizza il dettaglio di un mese specifico - implementazione originale"""
	try:
		# Validazione dei parametri
		if mese < 1 or mese > 12:
			flash('Mese non valido', 'error')
			return redirect(url_for('dettaglio_periodo.index'))

		# Servizi
		service = DettaglioPeriodoService()

		# Recupera dati per il mese (categoria filtering removed)
		dettaglio = service.get_dettaglio_mese(anno, mese)
		stats_categorie = service.get_statistiche_per_categoria(anno, mese)

		# Prepara categorie per il modal (escludi PayPal) usando il servizio
		service_cat = CategorieService()
		categorie_dict = service_cat.get_categories_dict(exclude_paypal=True)

		# Calcola mese precedente e successivo
		if mese == 1:
			mese_prec, anno_prec = 12, anno - 1
		else:
			mese_prec, anno_prec = mese - 1, anno

		if mese == 12:
			mese_succ, anno_succ = 1, anno + 1
		else:
			mese_succ, anno_succ = mese + 1, anno

		# Usa il template originale (già corretto l'endpoint)
		return render_template('bilancio/dettaglio_mese.html',
					 # Spacchetta il dizionario dettaglio per compatibilità template
					 **dettaglio,
					 stats_categorie=stats_categorie,
					 categorie=categorie_dict,
					 anno=anno,
					 mese=mese,
					 mese_prec=mese_prec,
					 anno_prec=anno_prec,
					 mese_succ=mese_succ,
					 anno_succ=anno_succ)

	except Exception as e:
		flash(f'Errore nel caricamento dettaglio periodo: {str(e)}', 'error')
		return redirect(url_for('main.index'))

@dettaglio_periodo_bp.route('/<start_date>/<end_date>')
def dettaglio_periodo(start_date, end_date):
	"""Mostra il dettaglio delle transazioni per un periodo specifico con date"""
	try:
		from datetime import datetime
		start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
		end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()

		service = DettaglioPeriodoService()

		# Recupera dettaglio del periodo (categoria filtering removed)
		result = service.dettaglio_periodo_interno(start_date_obj, end_date_obj)

		# Prepara categorie per il modal (escludi PayPal) usando il servizio
		service_cat = CategorieService()
		categorie_dict = service_cat.get_categories_dict(exclude_paypal=True)

		# Aggiungi le categorie al risultato
		result['categorie'] = categorie_dict

		# Calcola anno/mese derivati dall'end_date (usati dal template per dataset e navigazione)
		anno = end_date_obj.year
		mese = end_date_obj.month

		if mese == 1:
			mese_prec, anno_prec = 12, anno - 1
		else:
			mese_prec, anno_prec = mese - 1, anno

		if mese == 12:
			mese_succ, anno_succ = 1, anno + 1
		else:
			mese_succ, anno_succ = mese + 1, anno

		# Statistiche per categorie per il mese (necessarie al grafico)
		try:
			stats_categorie = service.get_statistiche_per_categoria(anno, mese)
		except Exception:
			stats_categorie = []
		return render_template('bilancio/dettaglio_mese.html', **result,
					   stats_categorie=stats_categorie,
					   anno=anno, mese=mese,
					   mese_prec=mese_prec, anno_prec=anno_prec,
					   mese_succ=mese_succ, anno_succ=anno_succ)
	except ValueError:
		return "Date non valide", 400
	except Exception as e:
		flash(f'Errore nel caricamento dettaglio periodo: {str(e)}', 'error')
		return redirect(url_for('main.index'))


@dettaglio_periodo_bp.route('/<start_date>/<end_date>/elimina_transazione/<int:id>', methods=['POST'])
def elimina_transazione_periodo(start_date, end_date, id):
	"""Elimina la transazione indicata e ritorna al dettaglio del periodo."""
	try:
		tx = Transazione.query.get_or_404(id)
		db.session.delete(tx)
		db.session.commit()
		flash('Transazione eliminata con successo', 'success')
	except Exception as e:
		try:
			db.session.rollback()
		except Exception:
			pass
		flash(f'Errore durante l\'eliminazione della transazione: {str(e)}', 'error')

	return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))


@dettaglio_periodo_bp.route('/<start_date>/<end_date>/aggiungi_transazione', methods=['POST'])
def aggiungi_transazione_periodo(start_date, end_date):
	"""Aggiunge una nuova transazione per il periodo specificato e ritorna al dettaglio."""
	try:
		data_str = request.form.get('data')
		data_obj = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else None

		descrizione = request.form.get('descrizione', '')
		tipo = request.form.get('tipo', 'uscita')
		importo = float(request.form.get('importo') or 0.0)
		categoria_id = int(request.form.get('categoria_id')) if request.form.get('categoria_id') else None
		ricorrente = True if request.form.get('ricorrente') else False

		transazione = Transazione(
			data=data_obj,
			data_effettiva=data_obj if data_obj and data_obj <= datetime.now().date() else None,
			descrizione=descrizione or '',
			importo=importo,
			categoria_id=categoria_id,
			tipo=tipo,
			ricorrente=ricorrente
		)

		db.session.add(transazione)
		db.session.commit()
		flash('Transazione aggiunta con successo', 'success')
	except Exception as e:
		try:
			db.session.rollback()
		except Exception:
			pass
		flash(f'Errore durante l\'aggiunta della transazione: {str(e)}', 'error')

	return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))


@dettaglio_periodo_bp.route('/<start_date>/<end_date>/modifica_transazione/<int:id>', methods=['POST'])
def modifica_transazione_periodo(start_date, end_date, id):
	"""Modifica una transazione esistente e ritorna al dettaglio del periodo."""
	tx = Transazione.query.get_or_404(id)
	try:
		data_str = request.form.get('data')
		if data_str:
			tx.data = datetime.strptime(data_str, '%Y-%m-%d').date()
			tx.data_effettiva = tx.data if tx.data <= datetime.now().date() else None

		if 'descrizione' in request.form:
			tx.descrizione = request.form.get('descrizione') or tx.descrizione
		if 'importo' in request.form:
			tx.importo = float(request.form.get('importo') or tx.importo)
		if 'categoria_id' in request.form:
			tx.categoria_id = int(request.form.get('categoria_id')) if request.form.get('categoria_id') else None
		if 'tipo' in request.form:
			tx.tipo = request.form.get('tipo') or tx.tipo
		# Ricorrente checkbox
		tx.ricorrente = True if request.form.get('ricorrente') else False

		db.session.commit()
		flash('Transazione modificata con successo', 'success')
	except Exception as e:
		try:
			db.session.rollback()
		except Exception:
			pass
		flash(f'Errore durante la modifica della transazione: {str(e)}', 'error')

	return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))
