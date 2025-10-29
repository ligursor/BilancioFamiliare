#!/usr/bin/env python3
from datetime import date
import sqlite3
import os


def get_month_boundaries(date_obj, giorno_inizio=27):
    import calendar
    if date_obj.day >= giorno_inizio:
        start_date = date_obj.replace(day=giorno_inizio)
        if date_obj.month == 12:
            end_date = date(date_obj.year + 1, 1, giorno_inizio - 1)
        else:
            try:
                end_date = date_obj.replace(month=date_obj.month + 1, day=giorno_inizio - 1)
            except ValueError:
                giorni_nel_mese = calendar.monthrange(date_obj.year, date_obj.month + 1)[1]
                end_date = date(date_obj.year, date_obj.month + 1, min(giorno_inizio - 1, giorni_nel_mese))
    else:
        if date_obj.month == 1:
            start_date = date(date_obj.year - 1, 12, giorno_inizio)
        else:
            start_date = date_obj.replace(month=date_obj.month - 1, day=giorno_inizio)
        end_date = date_obj.replace(day=giorno_inizio - 1)
    return start_date, end_date


def run_check_sqlite(db_path='db/bilancio.db', months=(-1, 0, 1)):
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Read base saldo
    row = cur.execute('SELECT importo FROM saldo_iniziale LIMIT 1').fetchone()
    saldo_base_importo = float(row['importo']) if row else 0.0

    oggi = date.today()
    print(f"Saldo base importo: {saldo_base_importo:.2f}")

    # try to import relativedelta, fallback to simple month shift if not available
    try:
        from dateutil.relativedelta import relativedelta
    except Exception:
        def relativedelta(months=0):
            class R:
                def __init__(self, months):
                    self.months = months
            return R(months)

    for offset in months:
        # compute the target date using relativedelta if available
        try:
            data_mese = oggi + relativedelta(months=offset)
        except Exception:
            # naive fallback: shift month by offset (may be inaccurate around month-ends)
            new_month = (oggi.month - 1 + offset) % 12 + 1
            year_shift = (oggi.month - 1 + offset) // 12
            data_mese = date(oggi.year + year_shift, new_month, min(28, oggi.day))

        start_date, end_date = get_month_boundaries(data_mese)

        # Totali effettuati
        q_effettuate = """
        SELECT tipo, SUM(importo) as tot
        FROM transazione
        WHERE categoria_id IS NOT NULL
          AND date(data) >= ? AND date(data) <= ?
          AND (data_effettiva IS NOT NULL OR date(data) <= ?)
        GROUP BY tipo
        """
        params = (start_date.isoformat(), end_date.isoformat(), oggi.isoformat())
        sums = {r['tipo']: r['tot'] for r in cur.execute(q_effettuate, params).fetchall()}
        entrate_eff = float(sums.get('entrata') or 0.0)
        uscite_eff = float(sums.get('uscita') or 0.0)

        # Totali in attesa
        q_attesa = """
        SELECT tipo, SUM(importo) as tot
        FROM transazione
        WHERE categoria_id IS NOT NULL
          AND date(data) >= ? AND date(data) <= ?
          AND (data_effettiva IS NULL AND date(data) > ?)
        GROUP BY tipo
        """
        sums2 = {r['tipo']: r['tot'] for r in cur.execute(q_attesa, params).fetchall()}
        entrate_att = float(sums2.get('entrata') or 0.0)
        uscite_att = float(sums2.get('uscita') or 0.0)

        entrate_tot = entrate_eff + entrate_att
        uscite_tot = uscite_eff + uscite_att

        # naive final: saldo_base + (entrate_tot - uscite_tot)
        saldo_finale_calc = saldo_base_importo + (entrate_tot - uscite_tot)

        print('-' * 60)
        print(f"Month: {start_date} -> {end_date}")
        print(f"entrate_eff: {entrate_eff:.2f} entrate_att: {entrate_att:.2f} entrate_tot: {entrate_tot:.2f}")
        print(f"uscite_eff: {uscite_eff:.2f} uscite_att: {uscite_att:.2f} uscite_tot: {uscite_tot:.2f}")
        print(f"saldo_base: {saldo_base_importo:.2f}")
        print(f"saldo_finale (naive calc): {saldo_finale_calc:.2f}")

    conn.close()


if __name__ == '__main__':
    # run the naive check
    run_check_sqlite()

    # Now compute accumulated saldo_iniziale for current month using anchor logic approximation
    def compute_accumulated_saldo(db_path='db/bilancio.db', target_date=None):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # base saldo
        row = cur.execute('SELECT importo, data_aggiornamento FROM saldo_iniziale LIMIT 1').fetchone()
        saldo_base = float(row['importo']) if row else 0.0
        data_agg = row['data_aggiornamento'] if row and 'data_aggiornamento' in row.keys() else None

        if data_agg:
            try:
                from datetime import datetime
                anchor_date = datetime.fromisoformat(data_agg).date()
            except Exception:
                anchor_date = None
        else:
            anchor_date = None

        if not anchor_date:
            r = cur.execute('SELECT data FROM transazione ORDER BY date(data) ASC LIMIT 1').fetchone()
            anchor_date = date.fromisoformat(r['data']) if r else (target_date or date.today())

        if not target_date:
            target_date = date.today()

        # iterate month by month from anchor_date until target_start (exclusive)
        current = anchor_date
        accumulated = saldo_base

        # helper to advance month
        try:
            from dateutil.relativedelta import relativedelta
        except Exception:
            def relativedelta(months=0):
                class R:
                    def __init__(self, months):
                        self.months = months
                return R(months)

        while True:
            start_m, end_m = get_month_boundaries(current)
            target_start, _ = get_month_boundaries(target_date)
            if start_m >= target_start:
                break

            # compute totals for this month (use same queries as above)
            params = (start_m.isoformat(), end_m.isoformat(), date.today().isoformat())
            q_effettuate_local = """
            SELECT tipo, SUM(importo) as tot
            FROM transazione
            WHERE categoria_id IS NOT NULL
              AND date(data) >= ? AND date(data) <= ?
              AND (data_effettiva IS NOT NULL OR date(data) <= ?)
            GROUP BY tipo
            """
            q_attesa_local = """
            SELECT tipo, SUM(importo) as tot
            FROM transazione
            WHERE categoria_id IS NOT NULL
              AND date(data) >= ? AND date(data) <= ?
              AND (data_effettiva IS NULL AND date(data) > ?)
            GROUP BY tipo
            """
            sums = {r['tipo']: r['tot'] for r in cur.execute(q_effettuate_local, params).fetchall()}
            sums2 = {r['tipo']: r['tot'] for r in cur.execute(q_attesa_local, params).fetchall()}

            entrate_tot = float(sums.get('entrata') or 0.0) + float(sums2.get('entrata') or 0.0)
            uscite_tot = float(sums.get('uscita') or 0.0) + float(sums2.get('uscita') or 0.0)

            bilancio_mese = entrate_tot - uscite_tot
            accumulated += bilancio_mese

            # next month
            try:
                current = current + relativedelta(months=1)
            except Exception:
                # simple fallback
                y = current.year + (current.month // 12)
                m = (current.month % 12) + 1
                current = date(y, m, min(current.day, 28))

        conn.close()
        return accumulated

    # compute for current month start
    try:
        from dateutil.relativedelta import relativedelta
        today = date.today()
        start_curr, end_curr = get_month_boundaries(today)
        acc = compute_accumulated_saldo(target_date=today)
        print('\nAccumulated saldo_iniziale (approx) for current month start:', f"{acc:.2f}")
    except Exception:
        pass
