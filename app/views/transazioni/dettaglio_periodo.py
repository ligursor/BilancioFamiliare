"""Blueprint per il dettaglio periodo"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from app.services.transazioni.dettaglio_periodo_service import DettaglioPeriodoService
from app.models.Transazioni import Transazioni
from app import db
from app.services.categorie.categorie_service import CategorieService
from flask import request, jsonify
from app.models.SaldiMensili import SaldiMensili
from app.models.BudgetMensili import BudgetMensili
from app.models.Categorie import Categorie
from app.services import get_month_boundaries
from datetime import date


def _recompute_summaries_from(start_year=None, start_month=None):
	"""Recompute `saldi_mensili` from a given start (year,month) up to the last month present in DB."""
	try:
		from app.services.transazioni.monthly_summary_service import MonthlySummaryService
		from app.models.SaldiMensili import SaldiMensili
		from dateutil.relativedelta import relativedelta

		# determine start
		if start_year is None or start_month is None:
			today = date.today()
			_, financial_end = get_month_boundaries(today)
			start_year = financial_end.year
			start_month = financial_end.month

		# determine last available month in DB
		last = SaldiMensili.query.order_by(SaldiMensili.year.desc(), SaldiMensili.month.desc()).first()
		if last:
			last_year = last.year
			last_month = last.month
		else:
			# if none exist, we just compute the single start month
			last_year = start_year
			last_month = start_month

		# build inclusive period list from start -> last
		periods = []
		cur = date(start_year, start_month, 1)
		last_date = date(last_year, last_month, 1)
		while cur <= last_date:
			periods.append((cur.year, cur.month))
			cur = cur + relativedelta(months=1)

		if not periods:
			return

		msvc = MonthlySummaryService()
		for (y, m) in periods:
			try:
				msvc.regenerate_month_summary(y, m)
			except Exception:
				# continue best-effort
				pass

		try:
			msvc.chain_saldo_across(periods)
		except Exception:
			pass
	except Exception:
		# swallow to avoid breaking caller
		pass

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

		# Recupera dati per il mese (categorie filtering removed)
		dettaglio = service.get_dettaglio_mese(anno, mese)
		stats_categorie = service.get_statistiche_per_categoria(anno, mese)

		# Prepara categorie per il modal (escludi PayPal) usando il servizio
		service_cat = CategorieService()
		categorie_dict = service_cat.get_categories_dict(exclude_paypal=True)

		# Recupera la lista dei mesi esistenti in monthly_summary per limitare la navigazione client-side
		try:
			summaries = SaldiMensili.query.order_by(SaldiMensili.year.asc(), SaldiMensili.month.asc()).all()
			available_months = [{'year': s.year, 'month': s.month} for s in summaries]
		except Exception:
			available_months = []

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
		# If a SaldiMensili row exists for this year/month, prefer its values for the
		# top summary boxes so the UI reflects persisted monthly summaries.
		try:
			ms = SaldiMensili.query.filter_by(year=anno, month=mese).first()
		except Exception:
			ms = None

		if ms:
			# override dettaglio values with persisted summary
			dettaglio['entrate'] = float(ms.entrate or 0.0)
			dettaglio['uscite'] = float(ms.uscite or 0.0)
			dettaglio['saldo_iniziale_mese'] = float(ms.saldo_iniziale or 0.0)
			dettaglio['saldo_finale_mese'] = float(ms.saldo_finale if ms.saldo_finale is not None else (ms.saldo_iniziale + (ms.entrate - ms.uscite)))
			# ensure the 'saldo_previsto_fine_mese' used by the template for future months
			dettaglio['saldo_previsto_fine_mese'] = float(ms.saldo_finale if ms.saldo_finale is not None else (ms.saldo_iniziale + (ms.entrate - ms.uscite)))

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
			     anno_succ=anno_succ,
			     available_months=available_months)

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

		# Recupera dettaglio del periodo (categorie filtering removed)
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

		# Recupera available_months per limitare la navigazione client-side
		try:
			summaries = SaldiMensili.query.order_by(SaldiMensili.year.asc(), SaldiMensili.month.asc()).all()
			available_months = [{'year': s.year, 'month': s.month} for s in summaries]
		except Exception:
			available_months = []

		# Prefer persisted monthly summary values for the template's top boxes
		try:
			ms = SaldiMensili.query.filter_by(year=anno, month=mese).first()
		except Exception:
			ms = None
		if ms:
			result['entrate'] = float(ms.entrate or 0.0)
			result['uscite'] = float(ms.uscite or 0.0)
			result['saldo_iniziale_mese'] = float(ms.saldo_iniziale or 0.0)
			result['saldo_finale_mese'] = float(ms.saldo_finale if ms.saldo_finale is not None else (ms.saldo_iniziale + (ms.entrate - ms.uscite)))
			result['saldo_previsto_fine_mese'] = float(ms.saldo_finale if ms.saldo_finale is not None else (ms.saldo_iniziale + (ms.entrate - ms.uscite)))

		return render_template('bilancio/dettaglio_mese.html', **result,
					   stats_categorie=stats_categorie,
					   anno=anno, mese=mese,
					   mese_prec=mese_prec, anno_prec=anno_prec,
					   mese_succ=mese_succ, anno_succ=anno_succ,
					   available_months=available_months)
	except ValueError:
		return "Date non valide", 400
	except Exception as e:
		flash(f'Errore nel caricamento dettaglio periodo: {str(e)}', 'error')
		return redirect(url_for('main.index'))


@dettaglio_periodo_bp.route('/<start_date>/<end_date>/elimina_transazione/<int:id>', methods=['POST'])
def elimina_transazione_periodo(start_date, end_date, id):
	"""Elimina la transazioni indicata e ritorna al dettaglio del periodo."""
	try:
		tx = Transazioni.query.get_or_404(id)
		db.session.delete(tx)
		db.session.commit()
		# Recompute monthly summaries starting from the month of the deleted transaction
		try:
			if getattr(tx, 'data', None):
				_recompute_summaries_from(tx.data.year, tx.data.month)
			else:
				_recompute_summaries_from()
		except Exception:
			pass
		flash('Transazioni eliminata con successo', 'success')
	except Exception as e:
		try:
			db.session.rollback()
		except Exception:
			pass
		flash(f'Errore durante l\'eliminazione della transazioni: {str(e)}', 'error')

	# If this was an AJAX request, return updated totals so the client can
	# update the summary boxes without reloading the page.
	if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
		try:
			from datetime import datetime as _dt
			start_dt = _dt.strptime(start_date, '%Y-%m-%d').date()
			end_dt = _dt.strptime(end_date, '%Y-%m-%d').date()
			service = DettaglioPeriodoService()
			summary = service.dettaglio_periodo_interno(start_dt, end_dt)
			# include stats per categoria for client-side chart updates
			try:
				anno = end_dt.year
				mese = end_dt.month
				stats = service.get_statistiche_per_categoria(anno, mese) or []
				# normalize to serializable list
				stats_serial = []
				for s in stats:
					try:
						if isinstance(s, dict):
							nome = s.get('categoria_nome')
							imp = float(s.get('importo') or 0)
						else:
							nome = getattr(s, 'categoria_nome', None)
							imp = float(getattr(s, 'importo', 0) or 0)
						stats_serial.append({'categoria_nome': nome, 'importo': imp})
					except Exception:
						stats_serial.append({'categoria_nome': str(s), 'importo': 0.0})
			except Exception:
				stats_serial = []
			# Keep only serializable summary fields
			# Prefer persisted monthly summary values when available
			try:
				ms_row = SaldiMensili.query.filter_by(year=anno, month=mese).first()
			except Exception:
				ms_row = None
			if ms_row:
				out = {
					'entrate': float(ms_row.entrate or 0.0),
					'uscite': float(ms_row.uscite or 0.0),
					'bilancio': float((ms_row.entrate or 0.0) - (ms_row.uscite or 0.0)),
					'saldo_iniziale_mese': float(ms_row.saldo_iniziale or 0.0),
					'saldo_attuale_mese': float(summary.get('saldo_attuale_mese') or 0.0),
					'saldo_finale_mese': float(ms_row.saldo_finale if ms_row.saldo_finale is not None else (ms_row.saldo_iniziale + ((ms_row.entrate or 0.0) - (ms_row.uscite or 0.0)))),
					'saldo_previsto_fine_mese': float(ms_row.saldo_finale if ms_row.saldo_finale is not None else (ms_row.saldo_iniziale + ((ms_row.entrate or 0.0) - (ms_row.uscite or 0.0)))),
					'budget_items': summary.get('budget_items') or [],
					'stats_categorie': stats_serial
				}
			else:
				out = {
					'entrate': float(summary.get('entrate') or 0.0),
					'uscite': float(summary.get('uscite') or 0.0),
					'bilancio': float(summary.get('bilancio') or 0.0),
					'saldo_iniziale_mese': float(summary.get('saldo_iniziale_mese') or 0.0),
					'saldo_attuale_mese': float(summary.get('saldo_attuale_mese') or 0.0),
					'saldo_finale_mese': float(summary.get('saldo_finale_mese') or 0.0),
					'saldo_previsto_fine_mese': float(ms_row.saldo_finale if ms_row.saldo_finale is not None else (ms_row.saldo_iniziale + ((ms_row.entrate or 0.0) - (ms_row.uscite or 0.0)))),
					'budget_items': summary.get('budget_items') or [],
					'stats_categorie': stats_serial
				}
			return jsonify({'status': 'ok', 'summary': out})
		except Exception:
			return jsonify({'status': 'error'}), 500
	# non-AJAX fallback
	return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))


@dettaglio_periodo_bp.route('/<start_date>/<end_date>/aggiungi_transazione', methods=['POST'])
def aggiungi_transazione_periodo(start_date, end_date):
	"""Aggiunge una nuova transazioni per il periodo specificato e ritorna al dettaglio."""
	try:
		# Parse submitted data
		data_str = request.form.get('data')
		try:
			data_obj = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else None
		except ValueError:
			data_obj = None

		descrizione = request.form.get('descrizione', '')
		tipo = request.form.get('tipo', 'uscita')
		importo = float(request.form.get('importo') or 0.0)
		categoria_id = int(request.form.get('categoria_id')) if request.form.get('categoria_id') else None

		# Determine if this is an AJAX inline add - for inline adds we MUST create non-recurring transactions
		is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
		if is_ajax:
			ricorrente = False
		else:
			ricorrente = True if request.form.get('ricorrente') else False

		# Validate that the provided date falls within the requested period bounds
		from datetime import datetime as _dt
		try:
			start_dt = _dt.strptime(start_date, '%Y-%m-%d').date()
			end_dt = _dt.strptime(end_date, '%Y-%m-%d').date()
		except Exception:
			start_dt = None
			end_dt = None

		if data_obj is None or start_dt is None or end_dt is None:
			# invalid/missing date
			msg = 'Data mancante o non valida.'
			if is_ajax:
				return jsonify({'status': 'error', 'message': msg}), 400
			flash(msg, 'error')
			return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))

		if not (start_dt <= data_obj <= end_dt):
			msg = 'La data della transazioni deve essere compresa nel periodo selezionato.'
			if is_ajax:
				return jsonify({'status': 'error', 'message': msg}), 400
			flash(msg, 'error')
			return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))

		transazioni = Transazioni(
			data=data_obj,
			data_effettiva=data_obj if data_obj and data_obj <= datetime.now().date() else None,
			descrizione=descrizione or '',
			importo=importo,
			categoria_id=categoria_id,
			tipo=tipo,
			ricorrente=ricorrente
		)

		db.session.add(transazioni)
		db.session.commit()
		# After adding a transaction, update monthly summaries starting from the transaction month
		try:
			if data_obj:
				_recompute_summaries_from(data_obj.year, data_obj.month)
			else:
				_recompute_summaries_from()
		except Exception:
			pass
		flash('Transazioni aggiunta con successo', 'success')
		# If this is an AJAX request, return JSON with the created transaction
		if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
			tx = Transazioni.query.get(transazioni.id)
			# Compute updated summary so client can refresh totals
			try:
				from datetime import datetime as _dt
				start_dt = _dt.strptime(start_date, '%Y-%m-%d').date()
				end_dt = _dt.strptime(end_date, '%Y-%m-%d').date()
				service = DettaglioPeriodoService()
				summary = service.dettaglio_periodo_interno(start_dt, end_dt)
				# include stats per categoria for client-side chart updates
				try:
					anno = end_dt.year
					mese = end_dt.month
					stats = service.get_statistiche_per_categoria(anno, mese) or []
					stats_serial = []
					for s in stats:
						try:
							stats_serial.append({'categoria_nome': s.get('categoria_nome') if isinstance(s, dict) else getattr(s, 'categoria_nome', None), 'importo': float(s.get('importo') if isinstance(s, dict) else getattr(s, 'importo', 0) or 0)})
						except Exception:
							stats_serial.append({'categoria_nome': str(s), 'importo': 0.0})
				except Exception:
					stats_serial = []
				out = {
					'entrate': float(summary.get('entrate') or 0.0),
					'uscite': float(summary.get('uscite') or 0.0),
					'bilancio': float(summary.get('bilancio') or 0.0),
					'saldo_iniziale_mese': float(summary.get('saldo_iniziale_mese') or 0.0),
					'saldo_attuale_mese': float(summary.get('saldo_attuale_mese') or 0.0),
					'saldo_finale_mese': float(summary.get('saldo_finale_mese') or 0.0),
					'saldo_previsto_fine_mese': float(summary.get('saldo_previsto_fine_mese') or 0.0),
					'budget_items': summary.get('budget_items') or [],
					'stats_categorie': stats_serial
				}
			except Exception:
				out = None
			return jsonify({'status': 'ok', 'transazione': {
				'id': tx.id,
				'data': tx.data.strftime('%Y-%m-%d') if tx.data else None,
				'descrizione': tx.descrizione,
				'importo': float(tx.importo or 0.0),
				'categoria_id': tx.categoria_id,
				'categoria_nome': tx.categoria.nome if tx.categoria else None,
				'tipo': tx.tipo,
				'ricorrente': bool(tx.ricorrente)
			}, 'summary': out})
	except Exception as e:
		try:
			db.session.rollback()
		except Exception:
			pass
		flash(f'Errore durante l\'aggiunta della transazioni: {str(e)}', 'error')

	return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))


@dettaglio_periodo_bp.route('/<start_date>/<end_date>/modifica_transazione/<int:id>', methods=['POST'])
def modifica_transazione_periodo(start_date, end_date, id):
	"""Modifica una transazioni esistente e ritorna al dettaglio del periodo."""
	tx = Transazioni.query.get_or_404(id)
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
		# After modifying a transaction, update monthly summaries starting from the transaction month
		try:
			if getattr(tx, 'data', None):
				_recompute_summaries_from(tx.data.year, tx.data.month)
			else:
				_recompute_summaries_from()
		except Exception:
			pass
		flash('Transazioni modificata con successo', 'success')
	except Exception as e:
		try:
			db.session.rollback()
		except Exception:
			pass
		flash(f'Errore durante la modifica della transazioni: {str(e)}', 'error')

	# If AJAX request, return updated totals (no full reload)
	if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
		try:
			from datetime import datetime as _dt
			start_dt = _dt.strptime(start_date, '%Y-%m-%d').date()
			end_dt = _dt.strptime(end_date, '%Y-%m-%d').date()
			service = DettaglioPeriodoService()
			summary = service.dettaglio_periodo_interno(start_dt, end_dt)
			# compute stats for chart
			try:
				anno = end_dt.year
				mese = end_dt.month
				stats = service.get_statistiche_per_categoria(anno, mese) or []
				stats_serial = []
				for s in stats:
					try:
						if isinstance(s, dict):
							nome = s.get('categoria_nome')
							imp = float(s.get('importo') or 0)
						else:
							nome = getattr(s, 'categoria_nome', None)
							imp = float(getattr(s, 'importo', 0) or 0)
						stats_serial.append({'categoria_nome': nome, 'importo': imp})
					except Exception:
						stats_serial.append({'categoria_nome': str(s), 'importo': 0.0})
			except Exception:
				stats_serial = []
			# Prefer persisted monthly summary values when available
			try:
				ms_row = SaldiMensili.query.filter_by(year=anno, month=mese).first()
			except Exception:
				ms_row = None
			if ms_row:
				out = {
					'entrate': float(ms_row.entrate or 0.0),
					'uscite': float(ms_row.uscite or 0.0),
					'bilancio': float((ms_row.entrate or 0.0) - (ms_row.uscite or 0.0)),
					'saldo_iniziale_mese': float(ms_row.saldo_iniziale or 0.0),
					'saldo_attuale_mese': float(summary.get('saldo_attuale_mese') or 0.0),
					'saldo_finale_mese': float(ms_row.saldo_finale if ms_row.saldo_finale is not None else (ms_row.saldo_iniziale + ((ms_row.entrate or 0.0) - (ms_row.uscite or 0.0)))),
					'saldo_previsto_fine_mese': float(summary.get('saldo_previsto_fine_mese') or 0.0),
					'budget_items': summary.get('budget_items') or [],
					'stats_categorie': stats_serial
				}
			else:
				out = {
					'entrate': float(summary.get('entrate') or 0.0),
					'uscite': float(summary.get('uscite') or 0.0),
					'bilancio': float(summary.get('bilancio') or 0.0),
					'saldo_iniziale_mese': float(summary.get('saldo_iniziale_mese') or 0.0),
					'saldo_attuale_mese': float(summary.get('saldo_attuale_mese') or 0.0),
					'saldo_finale_mese': float(summary.get('saldo_finale_mese') or 0.0),
					'saldo_previsto_fine_mese': float(summary.get('saldo_previsto_fine_mese') or 0.0),
					'budget_items': summary.get('budget_items') or [],
					'stats_categorie': stats_serial
				}
			return jsonify({'status': 'ok', 'summary': out})
		except Exception:
			return jsonify({'status': 'error'}), 500
	# non-AJAX fallback
	return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))


@dettaglio_periodo_bp.route('/<start_date>/<end_date>/modifica_monthly_budget', methods=['POST'])
def modifica_monthly_budget(start_date, end_date):
	"""Aggiorna (o crea) il BudgetMensili per la categorie/mese indicati e sincronizza"""
	try:
		# parse inputs
		categoria_id = int(request.form.get('categoria_id')) if request.form.get('categoria_id') else None
		importo_raw = request.form.get('importo')
		if categoria_id is None or importo_raw is None:
			return jsonify({'status': 'error', 'message': 'categoria_id o importo mancanti'}), 400

		nuovo_importo = float(importo_raw or 0.0)

		# compute year/month from end_date (the period is e.g. 27/10 - 26/11 and
		# budgets should belong to the month that includes the period end)
		from datetime import datetime
		ed = datetime.strptime(end_date, '%Y-%m-%d').date()
		year = ed.year
		month = ed.month

		# find or create BudgetMensili
		mb = BudgetMensili.query.filter_by(categoria_id=categoria_id, year=year, month=month).first()
		if not mb:
			mb = BudgetMensili(categoria_id=categoria_id, year=year, month=month, importo=nuovo_importo)
			db.session.add(mb)
		else:
			mb.importo = nuovo_importo

		# Try to find an existing 'budget' transazioni for this category/month
		# Use the month derived from end_date (ed) so periods that span month
		# boundaries are attributed to the intended month.
		from app.services import get_month_boundaries
		start_dt, end_dt = get_month_boundaries(ed)

		# Try to find an existing transazioni for this category/month (prefer non-recurring)
		tx = Transazioni.query.filter(
			Transazioni.categoria_id == categoria_id,
			Transazioni.data >= start_dt,
			Transazioni.data <= end_dt
		).order_by(Transazioni.ricorrente.asc(), Transazioni.id.asc()).first()

		categoria = Categorie.query.get(categoria_id)
		nome_cat = categoria.nome if categoria else f'Categoria {categoria_id}'
		descrizione_budget = f"Budget {nome_cat} {str(month).zfill(2)}/{year}"

		# Important: do not overwrite arbitrary existing transactions (e.g. generated recurring
		# transactions) when updating a monthly budget. Only update a transaction if it looks
		# explicitly like a budget transaction (we detect this by description starting with
		# 'Budget '). This avoids accidentally changing amounts of scheduled/recurring entries.
		if tx and isinstance(tx.descrizione, str) and tx.descrizione.startswith('Budget '):
			tx.importo = nuovo_importo
			tx.descrizione = descrizione_budget

		db.session.commit()
		# After budget modification, update monthly summaries starting from the budget month
		try:
			_recompute_summaries_from(year, month)
		except Exception:
			pass
		return jsonify({'status': 'ok'})
	except Exception as e:
		try:
			db.session.rollback()
		except Exception:
			pass
		return jsonify({'status': 'error', 'message': str(e)}), 500
