#!/usr/bin/env python3
"""Small migration helper: adds `id_recurring_tx` column to `transazione` if missing.

Usage:
  python scripts/apply_migration_add_id_recurring_tx.py --db db/bilancio.db [--drop-generated]

This is intentionally simple (SQLite). It performs ALTER TABLE to add the
nullable INTEGER column. For safety it creates a timestamped backup before
making changes.
"""
import argparse
import shutil
import os
import sqlite3
from datetime import datetime


def backup_db(path):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = f"{os.path.splitext(path)[0]}_backup_{ts}.db"
    shutil.copy2(path, dst)
    return dst


def table_has_column(conn, table, column):
    cur = conn.execute(f"PRAGMA table_info('{table}')")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols


def drop_table_if_exists(conn, table):
    try:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='db/bilancio.db', help='Path to sqlite DB')
    parser.add_argument('--drop-generated', action='store_true', help='Also drop generated_transaction table if present')
    args = parser.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}")
        raise SystemExit(1)

    print(f"Backing up DB {db_path}...")
    b = backup_db(db_path)
    print(f"Backup created: {b}")

    conn = sqlite3.connect(db_path)
    try:
        if table_has_column(conn, 'transazione', 'id_recurring_tx'):
            print('Column id_recurring_tx already exists in transazione — nothing to do')
        else:
            print('Adding column id_recurring_tx to transazione...')
            conn.execute('ALTER TABLE transazione ADD COLUMN id_recurring_tx INTEGER')
            conn.commit()
            print('Column added')

        if args.drop_generated:
            print('Dropping table generated_transaction if exists...')
            if drop_table_if_exists(conn, 'generated_transaction'):
                print('generated_transaction dropped (if existed)')
            else:
                print('Failed to drop generated_transaction (check permissions)')

    finally:
        conn.close()


if __name__ == '__main__':
    main()
