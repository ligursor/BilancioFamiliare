"""Rigenera le generated_transaction a partire dalle recurring_transaction per i prossimi 6 mesi
e ricalcola/aggiorna le righe in monthly_summary.

Regole e assunzioni:
- Orizzonte: 6 mesi a partire dal periodo finanziario corrente (confini 27..26)
- Il saldo iniziale per il periodo corrispondente a novembre 2025 deve essere impostato a 1000.0
- Il calcolo delle entrate/uscite per un periodo include sia le transazioni effettive (tabella transazione*)
  sia le generated_transaction
- I valori numeric vengono arrotondati a 2 decimali prima di essere salvati nel DB
"""
from app import create_app
from app.services import get_month_boundaries
from datetime import date
from dateutil.relativedelta import relativedelta
from app import db
from sqlalchemy import text
import math


def round2(v):
    try:
        return float(round(v + 1e-9, 2))
    except Exception:
        return 0.0


def main(months=6, initial_year=2025, initial_month=11, initial_saldo=1000.0):
    app = create_app()
    with app.app_context():
        oggi = date.today()
        start_date, _ = get_month_boundaries(oggi)

        # 1) elimina eventuali transazioni generate (figlie) nell'orizzonte
        # Le transazioni generate dalle ricorrenze sono memorizzate come figli in `transazione`
        last_period_date = start_date + relativedelta(months=months-1)
        last_start, last_end = get_month_boundaries(last_period_date)
        try:
            from app.models.transazioni import Transazione
            # Elimina le transazioni generate per ricorrenza usando id_recurring_tx
            deleted = db.session.query(Transazione).filter(Transazione.id_recurring_tx.isnot(None), Transazione.data >= start_date, Transazione.data <= last_end).delete(synchronize_session=False)
            db.session.commit()
            print(f"Deleted {deleted} generated child transazioni between {start_date} and {last_end}")
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting generated child transazioni: {e}")

        # 2) popola generated_transaction da recurring_transaction per l'orizzonte
        # First try existing service (may handle modern schema)
        from app.services.generated_transaction_service import GeneratedTransactionService
        svc = GeneratedTransactionService()
        created = svc.populate_horizon_from_recurring(months=months, base_date=start_date)
        print(f"GeneratedTransaction created by service: {created}")

        # Note: legacy compatibility insertion into a separate `generated_transaction` table
        # is no longer needed because the service writes into `transazione` directly.

        # 3) ricalcola monthly_summary sequenzialmente
        saldo_iniziale_map = {}
        period_list = []
        for i in range(months):
            periodo_data = start_date + relativedelta(months=i)
            periodo_start, periodo_end = get_month_boundaries(periodo_data)
            year = periodo_end.year
            month = periodo_end.month
            period_list.append((year, month, periodo_start, periodo_end))

        # find transactions table name
        tables = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'transazione%';")).fetchall()
        tx_table = tables[0][0] if tables else None

        for idx, (year, month, periodo_start, periodo_end) in enumerate(period_list):
            # compute entrate/uscite from transazioni (if table present)
            entrate = 0.0
            uscite = 0.0
            if tx_table:
                sql = text(f"SELECT importo, tipo FROM {tx_table} WHERE data >= :s AND data <= :e AND categoria_id IS NOT NULL")
                rows = db.session.execute(sql, {'s': periodo_start, 'e': periodo_end}).fetchall()
                for r in rows:
                    val = r[0] or 0.0
                    if r[1] == 'entrata':
                        entrate += val
                    else:
                        uscite += val

            # generated (recurring) entries are now stored in `transazione` and
            # are already included by the tx_table query above, so no extra step is needed.

            entrate = round2(entrate)
            uscite = round2(uscite)

            # determine saldo_iniziale
            if year == initial_year and month == initial_month:
                saldo_iniziale = round2(initial_saldo)
            else:
                # if first period is not the initial, and idx==0, try to read existing monthly_summary
                if idx == 0 and not (year == initial_year and month == initial_month):
                    # try to read existing value, else 0
                    row = db.session.execute(text("SELECT saldo_iniziale FROM monthly_summary WHERE year=:y AND month=:m"), {'y': year, 'm': month}).fetchone()
                    saldo_iniziale = round2(row[0]) if row and row[0] is not None else 0.0
                else:
                    # take previous month's saldo_finale
                    prev = period_list[idx-1]
                    prev_row = db.session.execute(text("SELECT saldo_finale FROM monthly_summary WHERE year=:y AND month=:m"), {'y': prev[0], 'm': prev[1]}).fetchone()
                    saldo_iniziale = round2(prev_row[0]) if prev_row and prev_row[0] is not None else 0.0

            saldo_finale = round2(saldo_iniziale + entrate - uscite)

            # upsert into monthly_summary (legacy schema)
            try:
                existing = db.session.execute(text("SELECT id FROM monthly_summary WHERE year=:y AND month=:m"), {'y': year, 'm': month}).fetchone()
                if existing:
                    db.session.execute(text("UPDATE monthly_summary SET saldo_iniziale=:si, entrate=:en, uscite=:us, saldo_finale=:sf WHERE id=:id"),
                                       {'si': saldo_iniziale, 'en': entrate, 'us': uscite, 'sf': saldo_finale, 'id': existing[0]})
                else:
                    db.session.execute(text("INSERT INTO monthly_summary (year, month, saldo_iniziale, entrate, uscite, saldo_finale) VALUES (:y, :m, :si, :en, :us, :sf)"),
                                       {'y': year, 'm': month, 'si': saldo_iniziale, 'en': entrate, 'us': uscite, 'sf': saldo_finale})
                db.session.commit()
                print(f"Upserted monthly_summary {year}-{month}: saldo_iniziale={saldo_iniziale} entrate={entrate} uscite={uscite} saldo_finale={saldo_finale}")
            except Exception as e:
                db.session.rollback()
                print(f"Error upserting monthly_summary for {year}-{month}: {e}")


if __name__ == '__main__':
    # Parameters: months=6, initial_year=2025, initial_month=11, initial_saldo=1000.0
    main(months=6, initial_year=2025, initial_month=11, initial_saldo=1000.0)
