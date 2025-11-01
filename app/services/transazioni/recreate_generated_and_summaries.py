"""Reusable logic to recreate generated transactions from recurring definitions
(`transazioni_ricorrenti`) and regenerate monthly summaries (`saldi_mensili`).

This module extracts the logic previously present in scripts/recreate_generated_and_summaries.py
and exposes a function `recreate_generated_and_summaries` that can be called from both the
CLI script and from the ResetService (UI).
"""
from app.services import get_month_boundaries
from datetime import date
from dateutil.relativedelta import relativedelta
from app import db
from sqlalchemy import text


def round2(v):
    try:
        return float(round(v + 1e-9, 2))
    except Exception:
        return 0.0


def recreate_generated_and_summaries(months=6, base_date=None, initial_year=None, initial_month=None, initial_saldo=None, full_wipe=False):
    """Recreate generated transactions and regenerate monthly_summary entries.

    Parameters:
      - months: number of months from current financial period to process
      - base_date: optional date to anchor the financial period (default: today)
      - initial_year, initial_month, initial_saldo: optional override for initial saldo seeding
      - full_wipe: if True, DELETE all rows from `transazioni` and `monthly_summary` before repopulating.

    Returns: dict with counts and summary information.
    """
    if base_date is None:
        base_date = date.today()

    # Enforce global maximum horizon of 6 months
    try:
        months = int(months)
    except Exception:
        months = 6
    if months > 6:
        months = 6

    start_date, _ = get_month_boundaries(base_date)

    result = {
        'deleted_transazioni': None,
    'deleted_monthly_summary': None,
        'created_generated_transactions': 0,
        'monthly_summary_regenerated': 0,
    }

    # 1) delete according to full_wipe flag
    if full_wipe:
        try:
            tx_count = db.session.execute(text('SELECT COUNT(*) FROM transazioni')).fetchone()[0]
        except Exception:
            tx_count = None
        try:
            ms_count = db.session.execute(text('SELECT COUNT(*) FROM saldi_mensili')).fetchone()[0]
        except Exception:
            ms_count = None
        try:
            db.session.execute(text('DELETE FROM transazioni'))
            db.session.commit()
            result['deleted_transazioni'] = int(tx_count) if tx_count is not None else None
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

        try:
            db.session.execute(text('DELETE FROM saldi_mensili'))
            db.session.commit()
            result['deleted_monthly_summary'] = int(ms_count) if ms_count is not None else None
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
    else:
        # delete only generated child transazioni in the horizon
        last_period_date = start_date + relativedelta(months=months-1)
        _, last_end = get_month_boundaries(last_period_date)
        try:
            from app.models.Transazioni import Transazioni
            deleted = db.session.query(Transazioni).filter(Transazioni.id_recurring_tx.isnot(None), Transazioni.data >= start_date, Transazioni.data <= last_end).delete(synchronize_session=False)
            db.session.commit()
            result['deleted_transazioni'] = int(deleted)
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

    # 2) repopulate generated transactions from recurring
    try:
        # Prefer to reuse the existing GeneratedTransactionService implementation
        # which encapsulates insertion logic and corner cases.
        from app.services.transazioni.generated_transaction_service import GeneratedTransactionService
        svc = GeneratedTransactionService()
        created = svc.populate_horizon_from_recurring(months=months, base_date=start_date)
        result['created_generated_transactions'] = int(created or 0)
    except Exception:
        result['created_generated_transactions'] = 0

    # 3) regenerate monthly_summary sequentially for the period list
    period_list = []
    for i in range(months):
        periodo_data = start_date + relativedelta(months=i)
        periodo_start, periodo_end = get_month_boundaries(periodo_data)
        year = periodo_end.year
        month = periodo_end.month
        period_list.append((year, month, periodo_start, periodo_end))

    from app.services.transazioni.monthly_summary_service import MonthlySummaryService
    msvc = MonthlySummaryService()

    for (year, month, periodo_start, periodo_end) in period_list:
        ok, res = msvc.regenerate_month_summary(year, month)
        if ok:
            result['monthly_summary_regenerated'] += 1

    return result
