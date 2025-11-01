"""Service implementing the monthly rollover logic (extracted from scripts/monthly_rollover.py).

This service can be invoked from CLI or from the app on first access after the 27th.
"""
from app.services import get_month_boundaries
from datetime import date
from dateutil.relativedelta import relativedelta
from app import db
from sqlalchemy import text


def do_monthly_rollover(force=False, months=1, base_date=None):
    """Perform monthly rollover:
    - generate transactions from recurring for `months` starting at the current financial period
    - regenerate monthly_summary for the generated months

    If `force` is True, generated transactions in the horizon are deleted before creating them.

    Returns dict with result info.
    """
    if base_date is None:
        base_date = date.today()

    start_date, _ = get_month_boundaries(base_date)

    result = {
        'force': bool(force),
        'months': int(months),
        'created_generated_transactions': 0,
        'monthly_summary_regenerated': 0,
        'chained': 0,
    }

    # Use the reusable recreate logic (non full wipe) which will delete generated children
    try:
        from app.services.transazioni.recreate_generated_and_summaries import recreate_generated_and_summaries
        # rollover should perform real changes by default
        res = recreate_generated_and_summaries(months=months, base_date=start_date, full_wipe=False)
        result.update(res)
    except Exception as e:
        # best-effort: return error info
        return {'error': str(e)}

    # Apply chaining across regenerated months
    try:
        period_list = []
        for i in range(months):
            periodo = start_date + relativedelta(months=i)
            _, period_end = get_month_boundaries(periodo)
            period_list.append((period_end.year, period_end.month))

        from app.services.transazioni.monthly_summary_service import MonthlySummaryService
        msvc = MonthlySummaryService()
        ok, info = msvc.chain_saldo_across(period_list)
        if ok:
            result['chained'] = info
        else:
            result['chain_error'] = info
    except Exception as e:
        result['chain_error'] = str(e)

    return result
