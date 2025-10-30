#!/usr/bin/env python3
"""Migration helper: create `saldo_iniziale` table if missing and insert initial row.

Usage:
  python scripts/apply_migration_create_saldo_iniziale.py --db db/bilancio.db

This will create the table with columns (id, importo, data_aggiornamento) and insert a single
row with importo taken from app config CONTO_MAURIZIO_SALDO_INIZIALE if available, else 1000.0.
"""
import argparse
import os
import shutil
from datetime import datetime
import sqlite3

def backup_db(path):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = f"{os.path.splitext(path)[0]}_backup_{ts}.db"
    shutil.copy2(path, dst)
    return dst

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='db/bilancio.db')
    args = parser.parse_args()
    db_path = args.db
    if not os.path.exists(db_path):
        print('DB not found:', db_path)
        raise SystemExit(1)

    print('Backing up DB...')
    b = backup_db(db_path)
    print('Backup:', b)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='saldo_iniziale';")
        if cur.fetchone():
            print('Table saldo_iniziale already exists')
            return

        print('Creating table saldo_iniziale...')
        conn.execute(
            'CREATE TABLE saldo_iniziale (id INTEGER PRIMARY KEY, importo FLOAT NOT NULL, data_aggiornamento DATETIME NOT NULL)'
        )
        # try to get default initial amount from config if possible
        initial = 1000.0
        try:
            # import app config
            from app import create_app
            app = create_app()
            with app.app_context():
                initial = float(app.config.get('CONTO_MAURIZIO_SALDO_INIZIALE', initial))
        except Exception:
            pass

        now = datetime.utcnow().isoformat()
        conn.execute('INSERT INTO saldo_iniziale (importo, data_aggiornamento) VALUES (?, ?)', (initial, now))
        conn.commit()
        print('Inserted initial saldo_iniziale =', initial)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
