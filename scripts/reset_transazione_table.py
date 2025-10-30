#!/usr/bin/env python3
"""Backup DB, drop and recreate `transazione` table with the current schema.

Usage:
  python3 scripts/reset_transazione_table.py --db db/bilancio.db

This will create a timestamped backup before changing the DB.
"""
import argparse
import os
import shutil
from datetime import datetime
import sqlite3


SCHEMA_SQL = '''
CREATE TABLE transazione (
    id INTEGER PRIMARY KEY,
    data DATE NOT NULL,
    data_effettiva DATE,
    descrizione TEXT NOT NULL,
    importo REAL NOT NULL,
    categoria_id INTEGER,
    tipo TEXT NOT NULL,
    ricorrente INTEGER DEFAULT 0,
    id_recurring_tx INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
'''


def backup_db(path):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = f"{os.path.splitext(path)[0]}_pre_reset_{ts}.db"
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
    backup = backup_db(db_path)
    print('Backup created at', backup)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        # Make sure foreign_keys PRAGMA is enabled
        cur.execute('PRAGMA foreign_keys = OFF;')

        print('Dropping existing transazione table (if any)...')
        cur.execute('DROP TABLE IF EXISTS transazione;')

        print('Creating transazione table...')
        cur.executescript(SCHEMA_SQL)

        conn.commit()
        print('transazione table recreated successfully')
    except Exception as e:
        conn.rollback()
        print('Error:', e)
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
