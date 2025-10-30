"""Piccola migrazione sqlite: aggiunge la colonna `skip_month_if_annual` a `recurring_transaction`.

Uso: eseguire dentro il container dove risiede l'app (PYTHONPATH=/app python3 scripts/apply_migration_add_skip_month_if_annual.py)

Nota: sqlite permette ALTER TABLE ADD COLUMN semplici; lo script aggiunge la colonna con default 0
e imposta il flag per lo stipendio mensile (descrizione LIKE 'stipendio' e cadenza mensile) per comodità.
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        # add column if not exists (sqlite will error if exists) -- we guard with PRAGMA table_info
        cols = [r[1] for r in db.session.execute(text("PRAGMA table_info(recurring_transaction);")).fetchall()]
        if 'skip_month_if_annual' not in cols:
            db.session.execute(text('ALTER TABLE recurring_transaction ADD COLUMN skip_month_if_annual INTEGER DEFAULT 0'))
            db.session.commit()
            print('Added column skip_month_if_annual to recurring_transaction')
        else:
            print('Column skip_month_if_annual already present')

        # set the flag for stipendio mensile entries (heuristic)
        try:
            updated = db.session.execute(text("UPDATE recurring_transaction SET skip_month_if_annual = 1 WHERE lower(descrizione) LIKE '%stipendio%' AND lower(cadenza) LIKE '%men%';")).rowcount
            db.session.commit()
            print('Set skip_month_if_annual for stipendio-like monthly recurrences (rows updated):', updated)
        except Exception as e:
            db.session.rollback()
            print('Could not set flag for stipendio entries:', e)
    except Exception as e:
        print('Migration failed:', e)
