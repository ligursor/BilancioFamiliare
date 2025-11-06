from app.services import BaseService, get_month_boundaries
from app.models.Transazioni import Transazioni
from app import db
from sqlalchemy import text
from sqlalchemy import or_
from datetime import date
import calendar
from dateutil.relativedelta import relativedelta



class GeneratedTransactionService(BaseService):
    """Servizio che popola la tabella `transazioni` a partire dalle ricorrenze."""

    def populate_horizon_from_recurring(self, months=6, base_date=None, create_only_future=False, mark_generated_tx_modificata=False):
        if base_date is None:
            base_date = date.today()
        start_date, _ = get_month_boundaries(base_date)
        created = 0
        # recupera tutte le ricorrenze attive (usiamo raw SQL per compatibilità)
        try:
            # select a minimal set of columns that are expected across legacy schemas
            # include `cadenza` and `prossima_data` so we can respect annual vs monthly recurrences
            rows = db.session.execute(
                text("SELECT id, descrizione, importo, categoria_id, tipo, giorno, attivo, cadenza, prossima_data, skip_month_if_annual FROM transazioni_ricorrenti WHERE attivo=1")
            ).fetchall()
            from types import SimpleNamespace
            # rows: id, descrizione, importo, categoria_id, tipo, giorno, attivo, cadenza, prossima_data, skip_month_if_annual
            recs = [SimpleNamespace(id=r[0], descrizione=r[1], importo=r[2], categoria_id=r[3], tipo=r[4], giorno=r[5], attivo=r[6], cadenza=r[7], prossima_data=r[8], skip_month_if_annual=r[9]) for r in rows]
        except Exception:
            recs = []

        # Build a quick lookup of annual recurrences by month -> set of (categoria_id, tipo)
        # and by month -> set of lowercased descriptions for fuzzy matching.
        annual_map = {}
        annual_desc_map = {}
        for rr in recs:
            try:
                rc = getattr(rr, 'cadenza', None) or 'mensile'
                if isinstance(rc, bytes):
                    rc = rc.decode('utf-8')
                if rc.lower().startswith('ann'):
                    pd = getattr(rr, 'prossima_data', None)
                    pd_month = None
                    if pd:
                        try:
                            if isinstance(pd, str):
                                pd_month = int(pd.split('-')[1])
                            else:
                                pd_month = pd.month
                        except Exception:
                            pd_month = None
                    if pd_month:
                        key = pd_month
                        annual_map.setdefault(key, set()).add((getattr(rr, 'categoria_id', None), getattr(rr, 'tipo', None)))
                        # store description for fuzzy matching (e.g., 'Stipendio' vs 'Stipendio Dicembre')
                        d = (getattr(rr, 'descrizione', '') or '').lower()
                        if d:
                            annual_desc_map.setdefault(key, set()).add(d)
            except Exception:
                continue

        for r in recs:
            # Non creiamo più una "transazioni madre" — le istanze generate
            # sono scritte direttamente nella tabella `transazioni` con
            # `id_recurring_tx` che punta alla r.id (transazioni_ricorrenti.id).

            for i in range(months):
                periodo_data = start_date + relativedelta(months=i)
                periodo_start, periodo_end = get_month_boundaries(periodo_data)
                # Determine the candidate date by trying both the periodo_start and periodo_end
                # month/year: a given giorno (day-of-month) may fall in either month depending
                # on whether it is < giorno_inizio (e.g. 27). We try both and pick the one that
                # falls inside the financial window [periodo_start, periodo_end].
                giorno = int(getattr(r, 'giorno', 1) or 1)
                cand = None

                # try periodo_start
                try:
                    last_day_start = calendar.monthrange(periodo_start.year, periodo_start.month)[1]
                    giorno_use_start = max(1, min(giorno, last_day_start))
                    c1 = date(periodo_start.year, periodo_start.month, giorno_use_start)
                    if periodo_start <= c1 <= periodo_end:
                        cand = c1
                except Exception:
                    cand = None

                # if not found, try periodo_end's month
                if cand is None:
                    try:
                        last_day_end = calendar.monthrange(periodo_end.year, periodo_end.month)[1]
                        giorno_use_end = max(1, min(giorno, last_day_end))
                        c2 = date(periodo_end.year, periodo_end.month, giorno_use_end)
                        if periodo_start <= c2 <= periodo_end:
                            cand = c2
                    except Exception:
                        cand = None

                if cand is None:
                    # no valid candidate inside this financial period
                    continue

                candidate_date = cand

                # If requested, only create transactions scheduled in the future
                # (strictly after today). This ensures that non-full wipes do not
                # recreate past recurring transactions.
                if create_only_future:
                    from datetime import date as _date
                    if candidate_date <= _date.today():
                        continue

                if not (periodo_start <= candidate_date <= periodo_end):
                    continue

                # Respect recurrence frequency: for annual items only generate when the
                # candidate month matches the configured `prossima_data` month (if available).
                cadenza = getattr(r, 'cadenza', None) or 'mensile'
                if isinstance(cadenza, bytes):
                    cadenza = cadenza.decode('utf-8')
                if cadenza.lower().startswith('ann'):
                    # try to parse prossima_data if present (format YYYY-MM-DD or similar)
                    pd = getattr(r, 'prossima_data', None)
                    pd_month = None
                    if pd:
                        try:
                            if isinstance(pd, str):
                                pd_month = int(pd.split('-')[1])
                            else:
                                # some legacy schemas might store a date object
                                pd_month = pd.month
                        except Exception:
                            pd_month = None

                    if pd_month is not None and candidate_date.month != pd_month:
                        # skip this month for annual recurrence
                        continue

                # If this is a monthly recurrence, decide whether to skip it in this month
                # when an annual recurrence exists. Prefer the explicit `skip_month_if_annual`
                # flag on the recurring row; if set, perform matching by (categoria_id,tipo)
                # or by fuzzy description. If the flag is not set, do not skip (maintain
                # backwards compatibility with previous behaviour).
                if cadenza.lower().startswith('men'):
                    mm = candidate_date.month
                    keyset = annual_map.get(mm, set())
                    desc_set = annual_desc_map.get(mm, set())
                    skip_flag = getattr(r, 'skip_month_if_annual', None)
                    if skip_flag:
                        cat = getattr(r, 'categoria_id', None)
                        t = getattr(r, 'tipo', None)
                        if (cat, t) in keyset:
                            continue
                        desc = (getattr(r, 'descrizione', '') or '').lower()
                        if desc and any((desc in ad) or (ad in desc) for ad in desc_set):
                            continue

                # controllo esistenza: cerchiamo transazioni già create per la stessa recurring id
                exists = Transazioni.query.filter_by(id_recurring_tx=getattr(r, 'id', None), data=candidate_date).first()
                if exists:
                    continue

                # Se esiste una transazione protetta (importo_modificato==1) per la stessa data
                # e che sia riferita a questa ricorrenza (id_recurring_tx) oppure abbia la stessa descrizione,
                # saltiamo la creazione per evitare di sovrascrivere/interferire con modifiche manuali.
                try:
                    prot = Transazioni.query.filter(
                        Transazioni.data == candidate_date,
                        Transazioni.tx_modificata == True,
                        or_(Transazioni.id_recurring_tx == getattr(r, 'id', None), Transazioni.descrizione == getattr(r, 'descrizione', None))
                    ).first()
                    if prot:
                        continue
                except Exception:
                    # In case the DB schema doesn't have the column yet or other issues, proceed with default behaviour
                    pass

                # crea la transazioni programmata (data_effettiva None -> in attesa)
                tx = Transazioni(
                    data=candidate_date,
                    data_effettiva=None,
                    descrizione=r.descrizione,
                    importo=round(float(getattr(r, 'importo', 0.0)), 2),
                    categoria_id=getattr(r, 'categoria_id', None),
                    tipo=getattr(r, 'tipo', 'uscita'),
                    tx_ricorrente=True,
                    tx_modificata=bool(mark_generated_tx_modificata),
                    id_recurring_tx=getattr(r, 'id', None),
                    id_periodo=(get_month_boundaries(candidate_date)[1].year * 100 + get_month_boundaries(candidate_date)[1].month)
                )
                db.session.add(tx)
                created += 1

        if created:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                created = 0

        return created
