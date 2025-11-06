from app.services import BaseService, get_month_boundaries
from app.models.SaldiMensili import SaldiMensili
from app.models.Transazioni import Transazioni
from app import db
from sqlalchemy import text
from datetime import date


class MonthlySummaryService(BaseService):
	"""Servizio per creare/aggiornare i riepiloghi mensili (monthly_summary)."""

	def regenerate_month_summary(self, year, month):
		"""Ricalcola e salva il monthly_summary per year/month usando la logica delle transazioni."""
		# costruisci una data rappresentativa per il mese
		try:
			data_mese = date(year, month, 1)
		except Exception:
			return False, "Data mese non valida"

		start_date, end_date = get_month_boundaries(data_mese)

		# Try ORM query; if the Transazioni table name in the DB differs (legacy table),
		# fall back to a raw SQL query searching for a table named like 'transazioni%'.
		# Prefer to reuse DettaglioPeriodoService which already computes the
		# adjusted values (including budget residui). This keeps dashboard,
		# dettaglio and monthly_summary consistent.
		try:
			from app.services.transazioni.dettaglio_periodo_service import DettaglioPeriodoService
			# DettaglioPeriodoService expects start/end dates; use its get_dettaglio_mese
			# to obtain entrate/uscite adjusted for this financial month.
			try:
				service = DettaglioPeriodoService()
				# provide the year/month of the target (use end_date)
				res = service.get_dettaglio_mese(end_date.year, end_date.month)
				entrate = float(res.get('entrate', 0.0) or 0.0)
				uscite = float(res.get('uscite', 0.0) or 0.0)
				# bilancio adjusted already computed by dettaglio
				bilancio = float(res.get('bilancio', entrate - uscite) or (entrate - uscite))
			except Exception:
				# fallback to direct transazioni aggregation when dettaglio fails
				transazioni = Transazioni.query.filter(
					Transazioni.data >= start_date,
					Transazioni.data <= end_date,
					Transazioni.categoria_id.isnot(None)
				).all()
				entrate = sum(t.importo for t in transazioni if t.tipo == 'entrata')
				uscite = sum(t.importo for t in transazioni if t.tipo == 'uscita')
				bilancio = entrate - uscite
		except Exception:
			# raw SQL fallback if ORM/dettaglio both fail
			try:
				tables = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'transazioni%';")).fetchall()
				if not tables:
					return False, "No transactions table found"
				tx_table = tables[0][0]
				# Inspect table columns to detect presence of id_periodo. If present,
				# prefer to filter by id_periodo (YYYYMM integer) to leverage the index.
				try:
					cols = [r[1] for r in db.session.execute(text(f"PRAGMA table_info('{tx_table}');")).fetchall()]
				except Exception:
					cols = []
				if 'id_periodo' in cols:
					period_val = int(end_date.year) * 100 + int(end_date.month)
					sql = f"SELECT data, importo, categoria_id, tipo FROM {tx_table} WHERE id_periodo = :period AND categoria_id IS NOT NULL"
					rows = db.session.execute(text(sql), {'period': period_val}).fetchall()
				else:
					sql = (
						f"SELECT data, importo, categoria_id, tipo FROM {tx_table} "
						"WHERE data >= :start AND data <= :end AND categoria_id IS NOT NULL"
					)
					rows = db.session.execute(text(sql), {'start': start_date, 'end': end_date}).fetchall()
				entrate = sum(r[1] for r in rows if r[3] == 'entrata')
				uscite = sum(r[1] for r in rows if r[3] == 'uscita')
				bilancio = entrate - uscite
			except Exception as e:
				return False, str(e)
		bilancio = entrate - uscite

		# Some DBs may have a different monthly_summary schema (legacy). Detect columns
		try:
			cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('saldi_mensili');")).fetchall()]
		except Exception:
			cols = []

		# prepare a default result holder in case we fall back to raw SQL
		ms = None

		# detect if there's a global saldo_iniziale value we should apply to the first month
		has_saldo_iniziale_col = 'saldo_iniziale' in cols
		saldo_init_val = None
		if has_saldo_iniziale_col:
			try:
				row = db.session.execute(text('SELECT importo FROM saldo_iniziale LIMIT 1')).fetchone()
				if row:
					saldo_init_val = float(row[0])
			except Exception:
				saldo_init_val = None

		# helper: determine if there exists any monthly_summary earlier than (year, month)
		def _has_prior_summary(y, m):
			try:
				prior = db.session.execute(
					text('SELECT 1 FROM saldi_mensili WHERE (year < :y) OR (year = :y AND month < :m) LIMIT 1'),
					{'y': y, 'm': m}
				).fetchone()
				return prior is not None
			except Exception:
				return False

		has_saldo_finale_col = 'saldo_finale' in cols
		has_bilancio_col = 'bilancio' in cols

		if has_saldo_finale_col:
			ms = SaldiMensili.query.filter_by(year=year, month=month).first()
			if not ms:
				ms = SaldiMensili(year=year, month=month)
				db.session.add(ms)
				if has_saldo_iniziale_col and (ms.saldo_iniziale is None or ms.saldo_iniziale == 0.0):
					if (saldo_init_val is not None) and (not _has_prior_summary(year, month)):
						ms.saldo_iniziale = saldo_init_val
			else:
				# Ensure saldo_iniziale is at least zero to avoid None math
				if has_saldo_iniziale_col and ms.saldo_iniziale is None:
					ms.saldo_iniziale = 0.0

			ms.entrate = entrate
			ms.uscite = uscite
			base_saldo = float(ms.saldo_iniziale or 0.0) if has_saldo_iniziale_col else 0.0
			# saldo_finale = saldo_iniziale + entrate - uscite
			ms.saldo_finale = base_saldo + entrate - uscite
		else:
			# Schema legacy senza saldo_finale: usa SQL diretto e gestisci eventuale colonna bilancio
			try:
				try:
					db.session.execute(text("PRAGMA busy_timeout=5000"))
				except Exception:
					pass

				existing = db.session.execute(
					text("SELECT id FROM saldi_mensili WHERE year=:y AND month=:m"),
					{'y': year, 'm': month}
				).fetchone()

				if existing:
					if has_bilancio_col:
						db.session.execute(
							text("UPDATE saldi_mensili SET entrate=:entrate, uscite=:uscite, bilancio=:bilancio WHERE id=:id"),
							{'entrate': entrate, 'uscite': uscite, 'bilancio': bilancio, 'id': existing[0]}
						)
					else:
						db.session.execute(
							text("UPDATE saldi_mensili SET entrate=:entrate, uscite=:uscite WHERE id=:id"),
							{'entrate': entrate, 'uscite': uscite, 'id': existing[0]}
						)
				else:
						if has_bilancio_col:
							db.session.execute(
								text("INSERT INTO saldi_mensili (year, month, entrate, uscite, bilancio) VALUES (:y, :m, :entrate, :uscite, :bilancio)"),
								{'y': year, 'm': month, 'entrate': entrate, 'uscite': uscite, 'bilancio': bilancio}
							)
						else:
							db.session.execute(
								text("INSERT INTO saldi_mensili (year, month, entrate, uscite) VALUES (:y, :m, :entrate, :uscite)"),
								{'y': year, 'm': month, 'entrate': entrate, 'uscite': uscite}
							)
			except Exception as e:
				return False, str(e)
			ms = {'year': year, 'month': month, 'entrate': entrate, 'uscite': uscite, 'bilancio': bilancio}

		try:
			db.session.commit()
			return True, ms
		except Exception as e:
			try:
				db.session.rollback()
			except Exception:
				pass
			return False, str(e)

	def chain_saldo_across(self, periods):
		"""Applica chaining saldo_finale -> saldo_iniziale per una lista ordinata di periodi."""
		if not periods or len(periods) < 2:
			return True, 0

		try:
			updated = 0
			# Per ogni coppia consecutiva di periodi, aggiorna il saldo_iniziale del mese successivo
			# = saldo_finale del mese corrente, poi ricalcola saldo_finale del mese successivo
			for i in range(len(periods) - 1):
				y_cur, m_cur = periods[i]
				y_next, m_next = periods[i + 1]
				
				# Recupera il saldo_finale AGGIORNATO del mese corrente
				cur_row = db.session.execute(
					text('SELECT saldo_finale FROM saldi_mensili WHERE year=:y AND month=:m'),
					{'y': y_cur, 'm': m_cur}
				).fetchone()
				if not cur_row:
					continue
				
				cur_saldo_finale = float(cur_row[0] or 0.0)
				
				# Aggiorna saldo_iniziale del mese successivo
				db.session.execute(
					text('UPDATE saldi_mensili SET saldo_iniziale = :s WHERE year = :y AND month = :m'),
					{'s': cur_saldo_finale, 'y': y_next, 'm': m_next}
				)
				
				# Ricalcola saldo_finale del mese successivo = saldo_iniziale + entrate - uscite
				next_row = db.session.execute(
					text('SELECT entrate, uscite FROM saldi_mensili WHERE year = :y AND month = :m'),
					{'y': y_next, 'm': m_next}
				).fetchone()
				if next_row:
					entrate_next = float(next_row[0] or 0.0)
					uscite_next = float(next_row[1] or 0.0)
					new_next_saldo_finale = cur_saldo_finale + entrate_next - uscite_next
					db.session.execute(
						text('UPDATE saldi_mensili SET saldo_finale = :sf WHERE year = :y AND month = :m'),
						{'sf': new_next_saldo_finale, 'y': y_next, 'm': m_next}
					)
				
				updated += 1

			db.session.commit()
			return True, updated
		except Exception as e:
			try:
				db.session.rollback()
			except Exception:
				pass
			return False, str(e)
