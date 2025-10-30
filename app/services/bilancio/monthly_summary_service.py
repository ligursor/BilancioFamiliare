from app.services import BaseService, get_month_boundaries
from app.models.monthly_summary import MonthlySummary
from app.models.transazioni import Transazione
from app import db
from sqlalchemy import text
from datetime import date


class MonthlySummaryService(BaseService):
	"""Servizio per creare/aggiornare i riepiloghi mensili (monthly_summary)."""

	def regenerate_month_summary(self, year, month):
		"""Ricalcola e salva il monthly_summary per year/month usando la logica delle transazioni.

		Il range considera i confini finanziari (27..26) usando la data del mese (prendiamo il 1 del mese richiesto).
		"""
		# costruisci una data rappresentativa per il mese
		try:
			data_mese = date(year, month, 1)
		except Exception:
			return False, "Data mese non valida"

		start_date, end_date = get_month_boundaries(data_mese)

		# Try ORM query; if the Transazione table name in the DB differs (legacy table),
		# fall back to a raw SQL query searching for a table named like 'transazione%'.
		# Prefer to reuse DettaglioPeriodoService which already computes the
		# adjusted values (including budget residui). This keeps dashboard,
		# dettaglio and monthly_summary consistent.
		try:
			from app.services.bilancio.dettaglio_periodo_service import DettaglioPeriodoService
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
				# fallback to direct transazione aggregation when dettaglio fails
				transazioni = Transazione.query.filter(
					Transazione.data >= start_date,
					Transazione.data <= end_date,
					Transazione.categoria_id.isnot(None)
				).all()
				entrate = sum(t.importo for t in transazioni if t.tipo == 'entrata')
				uscite = sum(t.importo for t in transazioni if t.tipo == 'uscita')
				bilancio = entrate - uscite
		except Exception:
			# raw SQL fallback if ORM/dettaglio both fail
			try:
				tables = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'transazione%';")).fetchall()
				if not tables:
					return False, "No transactions table found"
				tx_table = tables[0][0]
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
			cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('monthly_summary');")).fetchall()]
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
					text('SELECT 1 FROM monthly_summary WHERE (year < :y) OR (year = :y AND month < :m) LIMIT 1'),
					{'y': y, 'm': m}
				).fetchone()
				return prior is not None
			except Exception:
				return False

		if 'bilancio' in cols:
			# Safe to use ORM model which includes bilancio
			ms = MonthlySummary.query.filter_by(year=year, month=month).first()
			if not ms:
				ms = MonthlySummary(year=year, month=month, entrate=entrate, uscite=uscite, bilancio=bilancio)
				db.session.add(ms)
				# if the DB schema includes saldo_iniziale and there is a global value,
				# apply it to the first monthly_summary (no prior summaries exist)
				if has_saldo_iniziale_col and (saldo_init_val is not None) and (not _has_prior_summary(year, month)):
					try:
						db.session.execute(
							text("UPDATE monthly_summary SET saldo_iniziale = :s WHERE year = :y AND month = :m"),
							{'s': saldo_init_val, 'y': year, 'm': month}
						)
					except Exception:
						# best-effort: ignore if update fails
						pass
			else:
				ms.entrate = entrate
				ms.uscite = uscite
				ms.bilancio = bilancio
		else:
			# Fallback raw SQL upsert into legacy schema (use saldo_finale for bilancio)
			try:
				# ensure sqlite waits briefly if DB is locked by another connection
				try:
					db.session.execute(text("PRAGMA busy_timeout=5000"))
				except Exception:
					pass

				existing = db.session.execute(text("SELECT id FROM monthly_summary WHERE year=:y AND month=:m"), {'y': year, 'm': month}).fetchone()
				if existing:
					# compute saldo_finale as saldo_iniziale + bilancio (where bilancio = entrate - uscite)
					# use COALESCE to handle possible NULL saldo_iniziale values.
					db.session.execute(
						text("UPDATE monthly_summary SET entrate=:entrate, uscite=:uscite, saldo_finale=(COALESCE(saldo_iniziale,0.0) + :bilancio) WHERE id=:id"),
						{'entrate': entrate, 'uscite': uscite, 'bilancio': bilancio, 'id': existing[0]}
					)
				else:
					# Build insert with available columns. Some legacy schemas require saldo_iniziale NOT NULL,
					# include it with a safe default when present to avoid IntegrityError.
					has_saldo_iniziale = 'saldo_iniziale' in cols
					if has_saldo_iniziale:
						# if this is the first monthly_summary for the dataset and we have a global
						# saldo_iniziale value, use it; otherwise default to 0.0
						use_saldo = saldo_init_val if (saldo_init_val is not None and not _has_prior_summary(year, month)) else 0.0
						# compute saldo_finale = saldo_iniziale + bilancio
						saldo_finale_val = (use_saldo or 0.0) + bilancio
						db.session.execute(
							text("INSERT INTO monthly_summary (year, month, entrate, uscite, saldo_finale, saldo_iniziale) VALUES (:y, :m, :entrate, :uscite, :saldo, :saldo_iniziale)"),
							{'y': year, 'm': month, 'entrate': entrate, 'uscite': uscite, 'saldo': saldo_finale_val, 'saldo_iniziale': use_saldo}
						)
					else:
						# legacy schema with no saldo_iniziale column: continue storing bilancio
						# in saldo_finale (best-effort for older schemas)
						db.session.execute(
							text("INSERT INTO monthly_summary (year, month, entrate, uscite, saldo_finale) VALUES (:y, :m, :entrate, :uscite, :saldo)"),
							{'y': year, 'm': month, 'entrate': entrate, 'uscite': uscite, 'saldo': bilancio}
						)
			except Exception as e:
				return False, str(e)
			# For legacy schema, return a lightweight dict as result
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
		"""Applica chaining saldo_finale -> saldo_iniziale per una lista ordinata di periodi.

		`periods` deve essere una lista ordinata di tuple (year, month).
		Per ogni mese i in periods, imposta il `saldo_iniziale` del mese i+1 al `saldo_finale` del mese i.
		Restituisce (True, count) o (False, error_message).
		"""
		if not periods or len(periods) < 2:
			return True, 0

		try:
			rows = []
			for (y, m) in periods:
				r = db.session.execute(
					text('SELECT id, saldo_iniziale, saldo_finale FROM monthly_summary WHERE year=:y AND month=:m'),
					{'y': y, 'm': m}
				).fetchone()
				if r:
					rows.append(r)

			# esegui aggiornamenti
			updated = 0
			for i in range(len(rows) - 1):
				cur_saldo_finale = rows[i][2] if rows[i][2] is not None else 0.0
				next_id = rows[i + 1][0]
				db.session.execute(text('UPDATE monthly_summary SET saldo_iniziale = :s WHERE id = :id'), {'s': cur_saldo_finale, 'id': next_id})
				updated += 1

			db.session.commit()
			return True, updated
		except Exception as e:
			try:
				db.session.rollback()
			except Exception:
				pass
			return False, str(e)
