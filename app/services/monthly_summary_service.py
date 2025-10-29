from app import db
from app.models.monthly_summary import MonthlySummary
from app.models.transazioni import Transazione
from app.services import get_month_boundaries
from datetime import date


class MonthlySummaryService:
    """Service per costruire e mantenere la tabella `monthly_summary`.

    Funzionalità principali:
    - rebuild_all(): ricostruisce tutti i summary a partire dalle transazioni
    - update_for_transaction(transazione): aggiorna il summary del mese della transazione
    """

    def __init__(self):
        pass

    def rebuild_all(self):
        """Ricostruisce tutti i monthly summary dal DB delle transazioni.
        Strategia:
        - trova la prima transazione
        - itera mese per mese generando entrate/uscite e saldo accumulato
        """
        # trova prima e ultima transazione
        first = Transazione.query.order_by(Transazione.data.asc()).first()
        last = Transazione.query.order_by(Transazione.data.desc()).first()
        if not first or not last:
            return 0

        # usa get_month_boundaries per normalizzare
        start_m, _ = get_month_boundaries(first.data)
        _, end_m = get_month_boundaries(last.data)

        current = start_m
        accumulated = 0.0
        count = 0
        while current <= end_m:
            start_date, end_date = get_month_boundaries(current)

            transazioni = Transazione.query.filter(
                Transazione.data >= start_date,
                Transazione.data <= end_date,
                Transazione.categoria_id.isnot(None)
            ).all()

            entrate = sum(t.importo for t in transazioni if t.tipo == 'entrata')
            uscite = sum(t.importo for t in transazioni if t.tipo == 'uscita')

            saldo_iniziale = accumulated
            saldo_finale = saldo_iniziale + (entrate - uscite)

            # upsert
            ms = MonthlySummary.query.filter_by(year=start_date.year, month=start_date.month).first()
            if not ms:
                ms = MonthlySummary(year=start_date.year, month=start_date.month,
                                    saldo_iniziale=saldo_iniziale, entrate=entrate,
                                    uscite=uscite, saldo_finale=saldo_finale)
                db.session.add(ms)
            else:
                ms.saldo_iniziale = saldo_iniziale
                ms.entrate = entrate
                ms.uscite = uscite
                ms.saldo_finale = saldo_finale

            accumulated = saldo_finale
            count += 1

            # advance one month
            from dateutil.relativedelta import relativedelta
            current = current + relativedelta(months=1)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return count

    def update_for_transaction(self, transazione):
        """Aggiorna (ricalcola) il monthly summary per il mese della transazione.
        Nota: per semplicità ricalcoliamo quel mese e tutti i mesi successivi per mantenere l'accumulo.
        """
        if not transazione or not getattr(transazione, 'data', None):
            return False

        target_date = transazione.data
        start_target, _ = get_month_boundaries(target_date)

        # trova l'ultimo monthly summary precedente a start_target (per avere saldo iniziale)
        prev = MonthlySummary.query.filter(
            (MonthlySummary.year < start_target.year) | 
            ((MonthlySummary.year == start_target.year) & (MonthlySummary.month < start_target.month))
        ).order_by(MonthlySummary.year.desc(), MonthlySummary.month.desc()).first()

        # se non esiste, cerchiamo la prima transazione precedente per ricostruire da li
        if prev:
            accumulated = prev.saldo_finale
            current = start_target
        else:
            # ricostruiamo a partire dalla prima transazione
            first = Transazione.query.order_by(Transazione.data.asc()).first()
            if first:
                current, _ = get_month_boundaries(first.data)
            else:
                return False
            accumulated = 0.0

        # ricalcola da `current` fino all'ultimo mese presente oppure a qualche mese avanti
        # determine last month to recalc: at least the month of the transazione and the following month
        from dateutil.relativedelta import relativedelta
        last = Transazione.query.order_by(Transazione.data.desc()).first()
        if not last:
            return False
        _, end_last = get_month_boundaries(last.data)

        while current <= end_last:
            start_date, end_date = get_month_boundaries(current)
            transazioni = Transazione.query.filter(
                Transazione.data >= start_date,
                Transazione.data <= end_date,
                Transazione.categoria_id.isnot(None)
            ).all()

            entrate = sum(t.importo for t in transazioni if t.tipo == 'entrata')
            uscite = sum(t.importo for t in transazioni if t.tipo == 'uscita')

            saldo_iniziale = accumulated
            saldo_finale = saldo_iniziale + (entrate - uscite)

            ms = MonthlySummary.query.filter_by(year=start_date.year, month=start_date.month).first()
            if not ms:
                ms = MonthlySummary(year=start_date.year, month=start_date.month,
                                    saldo_iniziale=saldo_iniziale, entrate=entrate,
                                    uscite=uscite, saldo_finale=saldo_finale)
                db.session.add(ms)
            else:
                ms.saldo_iniziale = saldo_iniziale
                ms.entrate = entrate
                ms.uscite = uscite
                ms.saldo_finale = saldo_finale

            accumulated = saldo_finale
            current = current + relativedelta(months=1)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return True
