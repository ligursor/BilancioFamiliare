"""Blueprint per il dettaglio periodo"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from app.services.transazioni.dettaglio_periodo_service import DettaglioPeriodoService
from app.models.Transazioni import Transazioni
from app import db
from app.services.categorie.categorie_service import CategorieService
from app.services import get_month_boundaries
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

		# determine last available month in DB (excluding seed)
		try:
			cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('saldi_mensili');")).fetchall()]
		except Exception:
			cols = []
		
		if 'is_seed' in cols:
			last = SaldiMensili.query.filter(
				(SaldiMensili.is_seed == False) | (SaldiMensili.is_seed == None)
			).order_by(SaldiMensili.year.desc(), SaldiMensili.month.desc()).first()
		else:
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

	# Recupera dati per il mese
		dettaglio = service.get_dettaglio_mese(anno, mese)
		stats_categorie = service.get_statistiche_per_categoria(anno, mese)

		# Prepara categorie per il modal (escludi PayPal) usando il servizio
		service_cat = CategorieService()
		categorie_dict = service_cat.get_categories_dict(exclude_paypal=True)

		# Recupera la lista dei mesi esistenti in monthly_summary per limitare la navigazione client-side
		try:
			# Prefer to exclude rows explicitly marked as seed. If the DB
			# doesn't have the is_seed column yet, fall back to using the
			# current financial month as the lower bound.
			try:
				cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('saldi_mensili');")).fetchall()]
			except Exception:
				cols = []

			if 'is_seed' in cols:
				summaries = SaldiMensili.query.filter((SaldiMensili.is_seed == False) | (SaldiMensili.is_seed == None)).order_by(SaldiMensili.year.asc(), SaldiMensili.month.asc()).all()
				available_months = [{'year': s.year, 'month': s.month} for s in summaries]
			else:
				summaries = SaldiMensili.query.order_by(SaldiMensili.year.asc(), SaldiMensili.month.asc()).all()
				try:
					from datetime import date as _date
					_, current_financial_end = get_month_boundaries(_date.today())
					min_year = current_financial_end.year
					min_month = current_financial_end.month
					available_months = [
						{'year': s.year, 'month': s.month}
						for s in summaries
						if (s.year > min_year) or (s.year == min_year and s.month >= min_month)
					]
				except Exception:
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

			# Align 'saldo_attuale_mese' with persisted summary for consistency with dashboard.
			# For the current month, compute the actual performed transactions up to today
			try:
				from datetime import datetime as _dt
				oggi = _dt.now().date()
				# compute performed transactions for this month (data <= oggi)
				transazioni_mese = Transazioni.query.filter(
					Transazioni.data >= dettaglio.get('start_date'),
					Transazioni.data <= dettaglio.get('end_date'),
					Transazioni.categoria_id.isnot(None)
				).all()
				entrate_eff = 0.0
				uscite_eff = 0.0
				for t in transazioni_mese:
					if t.data <= oggi:
						if t.tipo == 'entrata':
							entrate_eff += t.importo
						else:
							uscite_eff += t.importo
				# Use saldo_iniziale from the persisted summary as anchor
				base_ini = float(ms.saldo_iniziale or 0.0)
				# If viewing the current financial month, compute actual available balance
				if (dettaglio.get('start_date') and dettaglio.get('end_date')):
					_dtt = _dt.now().date()
					# if today is inside the period, compute saldo_attuale as base + executed
					if dettaglio.get('start_date') <= _dtt <= dettaglio.get('end_date'):
						dettaglio['saldo_attuale_mese'] = base_ini + entrate_eff - uscite_eff
					else:
						dettaglio['saldo_attuale_mese'] = float(dettaglio.get('saldo_finale_mese', base_ini))
				else:
					dettaglio['saldo_attuale_mese'] = float(dettaglio.get('saldo_finale_mese', base_ini))
			except Exception:
				# fallback: keep whatever the service computed originally
				pass

		return render_template('bilancio/dettaglio_mese.html',
			     # Spacchetta il dizionario dettaglio per compatibilità template
			     **dettaglio,
			     stats_categorie=stats_categorie,
			     categorie=categorie_dict,
			     anno=anno,
			     mese=mese,
			     mese_corrente=(anno == datetime.now().year and mese == datetime.now().month),
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

	# Recupera dettaglio del periodo
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
			try:
				cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('saldi_mensili');")).fetchall()]
			except Exception:
				cols = []

			if 'is_seed' in cols:
				summaries = SaldiMensili.query.filter((SaldiMensili.is_seed == False) | (SaldiMensili.is_seed == None)).order_by(SaldiMensili.year.asc(), SaldiMensili.month.asc()).all()
				available_months = [{'year': s.year, 'month': s.month} for s in summaries]
			else:
				summaries = SaldiMensili.query.order_by(SaldiMensili.year.asc(), SaldiMensili.month.asc()).all()
				try:
					from datetime import date as _date
					_, current_financial_end = get_month_boundaries(_date.today())
					min_year = current_financial_end.year
					min_month = current_financial_end.month
					available_months = [
						{'year': s.year, 'month': s.month}
						for s in summaries
						if (s.year > min_year) or (s.year == min_year and s.month >= min_month)
					]
				except Exception:
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
				   anno=anno, mese=mese, mese_corrente=(anno == datetime.now().year and mese == datetime.now().month),
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
	is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
	success = False
	
	try:
		tx = Transazioni.query.get_or_404(id)
		
		# Se la transazione è categoria 10 (Ricarica PPay), cerca e cancella il movimento correlato
		if tx.categoria_id == 10:
			try:
				from app.models.PostePayEvolution import MovimentoPostePay
				from app.services.conti_finanziari.strumenti_service import StrumentiService
				from flask import current_app
				
				# Cerca movimento correlato con stessa data e importo, tipo Ricarica
				mov_correlato = MovimentoPostePay.query.filter(
					MovimentoPostePay.tipo == 'Ricarica',
					MovimentoPostePay.data == tx.data,
					MovimentoPostePay.importo == tx.importo
				).first()
				
				if mov_correlato:
					current_app.logger.info(f"Trovato movimento PostePay correlato id={mov_correlato.id}, lo elimino")
					# Calcola l'effetto del movimento sul saldo (da invertire)
					signed_value = -abs(mov_correlato.importo) if mov_correlato.tipo_movimento == 'uscita' else abs(mov_correlato.importo)
					
					db.session.delete(mov_correlato)
					
					# Aggiorna saldo dello Strumento PostePay invertendo l'effetto
					try:
						ss = StrumentiService()
						strum = ss.get_by_descrizione('Postepay Evolution')
						if strum:
							new_bal = (strum.saldo_corrente or 0.0) - signed_value
							ss.update_saldo_by_id(strum.id_conto, new_bal)
							current_app.logger.info(f"Saldo PostePay aggiornato: {new_bal}")
					except Exception as e:
						current_app.logger.error(f"Errore aggiornamento saldo PostePay: {e}")
			except Exception as e:
				from flask import current_app
				current_app.logger.error(f"Errore ricerca/cancellazione movimento PostePay correlato: {e}")
		
		db.session.delete(tx)
		db.session.commit()
		success = True
		
		# Recompute monthly summaries starting from the month of the deleted transaction
		try:
			if getattr(tx, 'data', None):
				_recompute_summaries_from(tx.data.year, tx.data.month)
			else:
				_recompute_summaries_from()
		except Exception:
			pass
		
		if not is_ajax:
			flash('Transazioni eliminata con successo', 'success')
	except Exception as e:
		try:
			db.session.rollback()
		except Exception:
			pass
		if not is_ajax:
			flash(f'Errore durante l\'eliminazione della transazioni: {str(e)}', 'error')
		elif is_ajax:
			# Return error JSON for AJAX
			return jsonify({'status': 'error', 'message': str(e)}), 400

	# If this was an AJAX request, return updated totals so the client can
	# update the summary boxes without reloading the page.
	if is_ajax:
		if not success:
			return jsonify({'status': 'error', 'message': 'Errore durante l\'eliminazione'}), 400
			
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

				# compute saldo_finale + sum of residui (defensive)
				try:
					b_items = summary.get('budget_items') or []
					sum_residui = sum([float(b.get('residuo') or 0) if isinstance(b, dict) else float(getattr(b, 'residuo', 0) or 0) for b in b_items])
					base_finale = float(ms_row.saldo_finale if ms_row.saldo_finale is not None else (ms_row.saldo_iniziale + ((ms_row.entrate or 0.0) - (ms_row.uscite or 0.0))))
					out['saldo_finale_plus_residui'] = float(base_finale + sum_residui)
				except Exception:
					out['saldo_finale_plus_residui'] = float(out.get('saldo_finale_mese') or 0.0)
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

				# compute saldo_finale + residui defensively
				try:
					b_items = summary.get('budget_items') or []
					sum_residui = sum([float(b.get('residuo') or 0) if isinstance(b, dict) else float(getattr(b, 'residuo', 0) or 0) for b in b_items])
					base_finale = float(summary.get('saldo_finale_mese') or 0.0)
					out['saldo_finale_plus_residui'] = float(base_finale + sum_residui)
				except Exception:
					out['saldo_finale_plus_residui'] = float(out.get('saldo_finale_mese') or 0.0)
			return jsonify({'status': 'ok', 'summary': out})
		except Exception as ex:
			return jsonify({'status': 'error', 'message': str(ex)}), 500
	
	# non-AJAX fallback
	return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))


@dettaglio_periodo_bp.route('/<start_date>/<end_date>/aggiungi_transazione', methods=['POST'])
def aggiungi_transazione_periodo(start_date, end_date):
	"""Aggiunge una nuova transazioni per il periodo specificato e ritorna al dettaglio."""
	# Use a single outer try/except to manage DB operations and return behavior
	is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
	transazioni = None
	summary_out = None
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

		# Recurrence is managed separately via transazioni_ricorrenti UI; do not accept tx_ricorrente from this form
		tx_ricorrente = False

		# Validate date bounds
		from datetime import datetime as _dt
		try:
			start_dt = _dt.strptime(start_date, '%Y-%m-%d').date()
			end_dt = _dt.strptime(end_date, '%Y-%m-%d').date()
		except Exception:
			start_dt = None
			end_dt = None

		if data_obj is None or start_dt is None or end_dt is None:
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

		# create transaction
		transazioni = Transazioni(
			data=data_obj,
			data_effettiva=data_obj if data_obj and data_obj <= datetime.now().date() else None,
			descrizione=descrizione or '',
			importo=importo,
			categoria_id=categoria_id,
			tipo=tipo,
			tx_ricorrente=tx_ricorrente
		)

		# populate id_periodo according to financial month ending month
		try:
			period_end = get_month_boundaries(transazioni.data_effettiva or transazioni.data)[1]
			transazioni.id_periodo = int(period_end.year) * 100 + int(period_end.month)
		except Exception:
			# best-effort: leave id_periodo None on failure
			pass


		# If category indicates PPay recharge (id 10): uscita dal conto principale = entrata su PostePay
		try:
			# Add transaction to session and commit it so it has an id
			db.session.add(transazioni)
			db.session.commit()

			if categoria_id == 10:
				# Use the PostePayEvolution service so the instrument balance is updated
				# Transazione uscita dal conto principale = ricarica (entrata) su PostePay Evolution
				try:
					from app.services.ppay_evolution.ppay_evolution_service import PostePayEvolutionService
					from flask import current_app

					ppay_svc = PostePayEvolutionService()
					current_app.logger.info(f"Creazione movimento PPay per transazione {transazioni.id}, importo {importo}")
					# create_movimento con tipo_movimento='entrata' incrementa saldo dello Strumento
					movimento = ppay_svc.create_movimento(
						data=data_obj,
						importo=importo,
						tipo='Ricarica',
						descrizione='Ricarica PPay Evolution',
						abbonamento_id=None,
						tipo_movimento='entrata'
					)
					current_app.logger.info(f"Movimento PPay creato: {movimento.id if movimento else 'None'}")
				except Exception as e:
					current_app.logger.error(f"Errore creazione movimento PPay: {str(e)}")
					# Non bloccare l'intera operazione ma loggare
					raise
		except Exception as ex:
			db.session.rollback()
			current_app.logger.error(f"Errore aggiunta transazione: {str(ex)}")
			raise

		# update summaries
		try:
			if data_obj:
				_recompute_summaries_from(data_obj.year, data_obj.month)
			else:
				_recompute_summaries_from()
		except Exception:
			pass
		flash('Transazioni aggiunta con successo', 'success')
		# prepare AJAX summary if requested
		if is_ajax and transazioni:
			# Build a robust summary_out: attempt to recompute the detailed summary
			# and fall back to a minimal summary if anything fails. This ensures
			# the client receives budget_items and updated totals immediately.
			try:
				from datetime import datetime as _dt
				start_dt = _dt.strptime(start_date, '%Y-%m-%d').date()
				end_dt = _dt.strptime(end_date, '%Y-%m-%d').date()
				service = DettaglioPeriodoService()
				summary = service.dettaglio_periodo_interno(start_dt, end_dt)
				# include stats per categoria
				try:
					anno = end_dt.year
					mese = end_dt.month
					stats = service.get_statistiche_per_categoria(anno, mese) or []
					stats_serial = []
					for s in stats:
						try:
							if isinstance(s, dict):
								stats_serial.append({'categoria_nome': s.get('categoria_nome'), 'importo': float(s.get('importo') or 0)})
							else:
								stats_serial.append({'categoria_nome': getattr(s, 'categoria_nome', None), 'importo': float(getattr(s, 'importo', 0) or 0)})
						except Exception:
							stats_serial.append({'categoria_nome': str(s), 'importo': 0.0})
				except Exception:
					stats_serial = []
				summary_out = {
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

				# compute saldo_finale + residui for client convenience
				try:
					b_items = summary.get('budget_items') or []
					sum_residui = sum([float(b.get('residuo') or 0) if isinstance(b, dict) else float(getattr(b, 'residuo', 0) or 0) for b in b_items])
					base_finale = float(summary.get('saldo_finale_mese') or 0.0)
					summary_out['saldo_finale_plus_residui'] = float(base_finale + sum_residui)
				except Exception:
					summary_out['saldo_finale_plus_residui'] = float(summary_out.get('saldo_finale_mese') or 0.0)
			except Exception as e:
				# If computing the full summary failed, try a minimal safe summary so the client
				# still receives updated totals. Do not raise further.
				try:
					from datetime import datetime as _dt
					start_dt = _dt.strptime(start_date, '%Y-%m-%d').date()
					end_dt = _dt.strptime(end_date, '%Y-%m-%d').date()
					# best-effort minimal aggregation
					service = DettaglioPeriodoService()
					summary = service.dettaglio_periodo_interno(start_dt, end_dt)
					summary_out = {
						'entrate': float(summary.get('entrate') or 0.0),
						'uscite': float(summary.get('uscite') or 0.0),
						'bilancio': float(summary.get('bilancio') or 0.0),
						'saldo_iniziale_mese': float(summary.get('saldo_iniziale_mese') or 0.0),
						'saldo_attuale_mese': float(summary.get('saldo_attuale_mese') or 0.0),
						'saldo_finale_mese': float(summary.get('saldo_finale_mese') or 0.0),
						'saldo_previsto_fine_mese': float(summary.get('saldo_previsto_fine_mese') or 0.0),
						'budget_items': summary.get('budget_items') or [],
						'stats_categorie': []
					}

					try:
						b_items = summary.get('budget_items') or []
						sum_residui = sum([float(b.get('residuo') or 0) if isinstance(b, dict) else float(getattr(b, 'residuo', 0) or 0) for b in b_items])
						base_finale = float(summary.get('saldo_finale_mese') or 0.0)
						summary_out['saldo_finale_plus_residui'] = float(base_finale + sum_residui)
					except Exception:
						summary_out['saldo_finale_plus_residui'] = float(summary_out.get('saldo_finale_mese') or 0.0)
				except Exception:
					summary_out = {'entrate':0.0,'uscite':0.0,'bilancio':0.0,'saldo_iniziale_mese':0.0,'saldo_attuale_mese':0.0,'saldo_finale_mese':0.0,'saldo_previsto_fine_mese':0.0,'budget_items':[],'stats_categorie':[]}

	except Exception as e:
		try:
			db.session.rollback()
		except Exception:
			pass
		flash(f'Errore durante l\'aggiunta della transazioni: {str(e)}', 'error')

	# Return AJAX response if requested, otherwise redirect back to the period view
	if is_ajax and transazioni:
		tx = Transazioni.query.get(transazioni.id)
		return jsonify({'status': 'ok', 'transazione': {
			'id': tx.id,
			'data': tx.data.strftime('%Y-%m-%d') if tx.data else None,
			'descrizione': tx.descrizione,
			'importo': float(tx.importo or 0.0),
			'categoria_id': tx.categoria_id,
			'categoria_nome': tx.categoria.nome if tx.categoria else None,
			'tipo': tx.tipo,
			'tx_ricorrente': bool(getattr(tx, 'tx_ricorrente', False))
		}, 'summary': summary_out})

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
		# Ricorrenza gestita separatamente: non modificare il flag tx_ricorrente qui

		# Segna la transazione come modificata manualmente dall'utente.
		# Questo impedisce che operazioni di soft-reset cancellino o ricreino
		# automaticamente questa occorrenza.
		try:
			tx.tx_modificata = True
		except Exception:
			# se per qualche motivo la colonna non esiste (vecchio schema), prosegui
			pass

		# Update id_periodo if date changed (recompute financial month)
		try:
			from app.services import get_month_boundaries as _gmb
			period_end = _gmb(tx.data_effettiva or tx.data)[1]
			tx.id_periodo = int(period_end.year) * 100 + int(period_end.month)
		except Exception as ex:
			print(f"Error updating id_periodo: {ex}")

		db.session.commit()
		print(f"Transaction {id} modified: data={tx.data}, importo={tx.importo}")
		
		# After modifying a transaction, update monthly summaries starting from the transaction month
		try:
			if getattr(tx, 'data', None):
				_recompute_summaries_from(tx.data.year, tx.data.month)
			else:
				_recompute_summaries_from()
		except Exception as ex:
			print(f"Error recomputing summaries: {ex}")
		flash('Transazioni modificata con successo', 'success')
	except Exception as e:
		print(f"Error modifying transaction {id}: {e}")
		import traceback
		traceback.print_exc()
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
		# Prefer to use id_periodo for month-scoped lookup (faster when indexed)
		try:
			period_val = int(get_month_boundaries(ed)[1].year) * 100 + int(get_month_boundaries(ed)[1].month)
			tx = Transazioni.query.filter(
				Transazioni.categoria_id == categoria_id,
				Transazioni.id_periodo == period_val
			).order_by(Transazioni.tx_ricorrente.asc(), Transazioni.id.asc()).first()
		except Exception:
			tx = Transazioni.query.filter(
				Transazioni.categoria_id == categoria_id,
				Transazioni.data >= start_dt,
				Transazioni.data <= end_dt
			).order_by(Transazioni.tx_ricorrente.asc(), Transazioni.id.asc()).first()

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


@dettaglio_periodo_bp.route('/<start_date>/<end_date>/correggi_saldo', methods=['POST'])
def correggi_saldo(start_date, end_date):
	"""
	Crea una transazione di correzione per allineare il saldo attuale con quello reale.
	Calcola la differenza tra il saldo reale fornito e il saldo attuale registrato,
	poi crea una transazione in uscita con categoria 'Spese Mensili'.
	"""
	is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
	try:
		# Parse dates
		from datetime import datetime as _dt
		try:
			start_dt = _dt.strptime(start_date, '%Y-%m-%d').date()
			end_dt = _dt.strptime(end_date, '%Y-%m-%d').date()
		except Exception:
			msg = 'Date non valide.'
			if is_ajax:
				return jsonify({'status': 'error', 'message': msg}), 400
			flash(msg, 'error')
			return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))

		# Get real balance from form
		try:
			saldo_reale = float(request.form.get('saldo_reale', 0))
		except (ValueError, TypeError):
			msg = 'Saldo reale non valido.'
			if is_ajax:
				return jsonify({'status': 'error', 'message': msg}), 400
			flash(msg, 'error')
			return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))

		# Calculate current balance from DB
		service = DettaglioPeriodoService()
		stats = service.dettaglio_periodo_interno(start_dt, end_dt)
		saldo_attuale = stats.get('saldo_attuale_mese', 0)

		# Calculate difference
		differenza = saldo_reale - saldo_attuale

		# If difference is zero or very small, no correction needed
		if abs(differenza) < 0.01:
			msg = 'Il saldo è già allineato, nessuna correzione necessaria.'
			if is_ajax:
				return jsonify({'status': 'info', 'message': msg})
			flash(msg, 'info')
			return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))

		# Create correction transaction
		# If differenza is positive, we need to add money (entrata) with category "Extra"
		# If differenza is negative, we need to remove money (uscita) with category "Correzione Saldo"
		descrizione = 'Correzione saldo'
		
		if differenza > 0:
			tipo = 'entrata'
			importo = differenza
			# Find "Extra" category for income
			categoria = Categorie.query.filter_by(nome='Extra').first()
			if not categoria:
				# If not found, try to find any "entrata" category as fallback
				categoria = Categorie.query.filter_by(tipo='entrata').first()
			categoria_nome = 'Extra'
		else:
			tipo = 'uscita'
			importo = abs(differenza)
			# Find "Spese Mensili" category for expenses
			categoria = Categorie.query.filter_by(nome='Spese Mensili').first()
			if not categoria:
				# If not found, try to find any "uscita" category as fallback
				categoria = Categorie.query.filter_by(tipo='uscita').first()
			categoria_nome = 'Spese Mensili'
		
		if not categoria:
			msg = f'Categoria "{categoria_nome}" non trovata. Impossibile creare la transazione di correzione.'
			if is_ajax:
				return jsonify({'status': 'error', 'message': msg}), 404
			flash(msg, 'error')
			return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))

		# Use today's date as transaction date
		data_transazione = date.today()

		transazione = Transazioni(
			data=data_transazione,
			data_effettiva=data_transazione,
			descrizione=descrizione,
			importo=importo,
			categoria_id=categoria.id,
			tipo=tipo,
			tx_ricorrente=False
		)

		# Set id_periodo
		try:
			period_end = get_month_boundaries(transazione.data_effettiva or transazione.data)[1]
			transazione.id_periodo = int(period_end.year) * 100 + int(period_end.month)
		except Exception:
			pass


		# Add the transaction and, if applicable, the PostePay movement in the same DB transaction
		try:
			db.session.add(transazione)
			db.session.commit()
			if getattr(transazione, 'categoria_id', None) == 10:
				# Transazione categoria 10: uscita dal conto principale = entrata su PostePay Evolution
				from app.services.ppay_evolution.ppay_evolution_service import PostePayEvolutionService

				ppay_svc = PostePayEvolutionService()
				# create_movimento con tipo_movimento='entrata' incrementa saldo dello Strumento
				ppay_svc.create_movimento(
					data=data_transazione,
					importo=importo,
					tipo='Ricarica',
					descrizione='Ricarica PPay Evolution',
					abbonamento_id=None,
					tipo_movimento='entrata'
				)
		except Exception:
			db.session.rollback()
			raise

		# If this is an expense correction, decrement the monthly budget for the category
		# and update persisted monthly summary so Saldo Attuale reflects the change immediately.
		if tipo == 'uscita':
			try:
				# Do NOT change BudgetMensili.importo: the monthly budget total must remain unchanged.
				# The correction transaction itself (categoria 'Spese Mensili') will be
				# counted among spese_effettuate, so the budget residual will decrease automatically.

				# Update persisted monthly summary (SaldiMensili) so UI top boxes use updated values
				try:
					ms = SaldiMensili.query.filter_by(year=data_transazione.year, month=data_transazione.month).first()
					if ms:
						ms.uscite = float(ms.uscite or 0.0) + float(importo or 0.0)
						ms.saldo_finale = float(ms.saldo_iniziale or 0.0) + float(ms.entrate or 0.0) - float(ms.uscite or 0.0)
						db.session.commit()
				except Exception:
					try:
						db.session.rollback()
					except Exception:
						pass
			except Exception:
				# Non-critical: continue
				pass

		# Update summaries
		try:
			_recompute_summaries_from(data_transazione.year, data_transazione.month)
		except Exception:
			pass

		msg = f'Transazione di correzione creata: {descrizione}'
		if is_ajax:
			# Recalculate stats and return updated summary
			stats = service.dettaglio_periodo_interno(start_dt, end_dt)
			# compute saldo_finale_plus_residui defensively
			try:
				b_items = stats.get('budget_items') or []
				sum_residui = sum([float(b.get('residuo') or 0) if isinstance(b, dict) else float(getattr(b, 'residuo', 0) or 0) for b in b_items])
				base_finale = float(stats.get('saldo_finale_mese') or 0.0)
				saldo_plus = float(base_finale + sum_residui)
			except Exception:
				saldo_plus = float(stats.get('saldo_finale_mese') or 0.0)
			return jsonify({
				'status': 'ok',
				'message': msg,
				'summary': {
					'saldo_iniziale_mese': float(stats.get('saldo_iniziale_mese') or 0),
					'entrate': float(stats.get('entrate') or 0),
					'uscite': float(stats.get('uscite') or 0),
					'bilancio': float(stats.get('bilancio') or 0),
					'saldo_attuale_mese': float(stats.get('saldo_attuale_mese') or 0),
					'saldo_finale_mese': float(stats.get('saldo_finale_mese') or 0),
					'saldo_finale_plus_residui': saldo_plus,
					'budget_items': stats.get('budget_items') or []
				}
			})
		flash(msg, 'success')
		return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))

	except Exception as e:
		try:
			db.session.rollback()
		except Exception:
			pass
		msg = f'Errore durante la correzione del saldo: {str(e)}'
		if is_ajax:
			return jsonify({'status': 'error', 'message': msg}), 500
		flash(msg, 'error')
		return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))
