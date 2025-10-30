"""Script per eseguire il rollover mensile:
- genera le transazioni ricorrenti per il nuovo mese (le scrive in `transazione`)
- crea/aggiorna il `monthly_summary` per il mese aggiunto

Uso: eseguire nello stesso ambiente dell'app Flask (usa create_app()).
Opzioni:
  --force    : forza la ricreazione delle transazioni generate per il mese (eliminerà le voci esistenti con id_recurring_tx nel periodo)
  --months N : quanti mesi generare (default 1)
"""
import argparse
from app import create_app


def main(argv=None):
    parser = argparse.ArgumentParser(description='Monthly rollover — genera transazioni ricorrenti e aggiorna monthly_summary')
    parser.add_argument('--force', action='store_true', help='Forza la rigenerazione: elimina le transazioni generate per il periodo prima di ricrearle')
    parser.add_argument('--months', type=int, default=1, help='Numero di mesi da generare (default 1)')
    args = parser.parse_args(argv)

    app = create_app()
    with app.app_context():
        from app.services.bilancio.generated_transaction_service import GeneratedTransactionService
        from app.services.bilancio.monthly_summary_service import MonthlySummaryService
        from app.services import get_month_boundaries
        from datetime import date
        from dateutil.relativedelta import relativedelta
        from app.models.transazioni import Transazione
        from app import db
        from sqlalchemy import text

        svc_gt = GeneratedTransactionService()
        svc_ms = MonthlySummaryService()

        oggi = date.today()
        start_date, end_date = get_month_boundaries(oggi)

        # target representative date: start from the current financial month start
        # so that the generated horizon begins with the next calendar month inside
        # the financial month (e.g. start_date=27/10 -> first generated month = Nov).
        target_date = start_date

        # Se --force è attivo, eliminiamo le transazioni generate (id_recurring_tx non NULL)
        if args.force:
            # calcola confini per l'intervallo da eliminare (copre tutti i mesi che andremo a generare)
            first_start, _ = get_month_boundaries(target_date)
            # fine dell'ultimo mese dell'orizzonte
            last_period = target_date + relativedelta(months=args.months - 1)
            _, last_end = get_month_boundaries(last_period)
            try:
                deleted = db.session.query(Transazione).filter(
                    Transazione.id_recurring_tx.isnot(None),
                    Transazione.data >= first_start,
                    Transazione.data <= last_end
                ).delete(synchronize_session=False)
                db.session.commit()
                print(f"Deleted {deleted} generated transazioni for period {first_start} - {last_end}")
            except Exception as e:
                db.session.rollback()
                print(f"Error deleting generated transazioni: {e}")

        # 1) popola le transazioni ricorrenti per i mesi richiesti
        created = svc_gt.populate_horizon_from_recurring(months=args.months, base_date=target_date)
        print(f"Generated transazioni created for next {args.months} month(s): {created}")

        # 2) per ciascun mese dell'orizzonte, rigenera/aggiorna il monthly_summary
        from dateutil.relativedelta import relativedelta
        regenerated_periods = []
        for i in range(args.months):
            period = target_date + relativedelta(months=i)
            _, period_end = get_month_boundaries(period)
            y = period_end.year
            m = period_end.month
            ok, result = svc_ms.regenerate_month_summary(y, m)
            if ok:
                print(f"MonthlySummary updated: {result}")
                regenerated_periods.append((y, m))
            else:
                print(f"MonthlySummary error for {y}-{m}: {result}")

        # 3) se abbiamo rigenerato più mesi, applichiamo il chaining saldo_finale -> saldo_iniziale
        #    delegando al servizio MonthlySummaryService per avere la logica centralizzata
        if regenerated_periods:
            regenerated_periods_sorted = sorted(regenerated_periods)
            ok_chain, info = svc_ms.chain_saldo_across(regenerated_periods_sorted)
            if ok_chain:
                print(f'Chaining applied for {info} gap(s) across regenerated horizon')
            else:
                print('Chaining error:', info)


if __name__ == '__main__':
    main()
