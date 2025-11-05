"""Reusable logic to recreate generated transactions from recurring definitions"""
from app.services import get_month_boundaries
from datetime import date
from dateutil.relativedelta import relativedelta
from app import db
from sqlalchemy import text


def recreate_generated_and_summaries(months=6, base_date=None, _initial_year=None, _initial_month=None, initial_saldo=None, full_wipe=False):
    """Recreate generated transactions and regenerate monthly_summary entries."""
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

    # If an explicit initial_saldo was provided, seed the first period's
    # `saldi_mensili.saldo_iniziale` so that regenerate_month_summary will
    # use it as starting balance for the first month.
    if initial_saldo is not None and len(period_list) > 0:
        try:
            from app.models.SaldiMensili import SaldiMensili
            first_year, first_month, _, _ = period_list[0]
            existing = SaldiMensili.query.filter_by(year=first_year, month=first_month).first()
            if existing:
                existing.saldo_iniziale = float(initial_saldo)
                db.session.add(existing)
            else:
                # create a minimal record with the provided saldo_iniziale; other fields
                # will be updated by regenerate_month_summary
                new_ms = SaldiMensili(year=first_year, month=first_month, saldo_iniziale=float(initial_saldo))
                db.session.add(new_ms)
            db.session.commit()
            result['initial_saldo_seeded'] = True
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            result['initial_saldo_seeded'] = False

    for (year, month, periodo_start, periodo_end) in period_list:
        ok, res = msvc.regenerate_month_summary(year, month)
        if ok:
            result['monthly_summary_regenerated'] += 1

    # 4) Apply chaining: propagate saldo_finale -> saldo_iniziale across periods
    if period_list:
        try:
            periods_for_chain = [(y, m) for (y, m, _, _) in period_list]
            ok_chain, chain_count = msvc.chain_saldo_across(sorted(periods_for_chain))
            if ok_chain:
                result['chained_periods'] = chain_count
        except Exception:
            # best-effort: if chaining fails, continue
            pass

    return result
