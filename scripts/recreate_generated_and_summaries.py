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


def _cli_main(months=6, initial_year=2025, initial_month=11, initial_saldo=1000.0):
    """CLI wrapper that calls the reusable function inside an app_context."""
    app = create_app()
    with app.app_context():
        # Import here to avoid circular imports at module import time
        from app.services.bilancio.recreate_generated_and_summaries import recreate_generated_and_summaries
    # CLI should perform the real changes by default
    res = recreate_generated_and_summaries(months=months, base_date=None, initial_year=initial_year, initial_month=initial_month, initial_saldo=initial_saldo, full_wipe=False)
    print('Recreate result:', res)


if __name__ == '__main__':
    _cli_main(months=6, initial_year=2025, initial_month=11, initial_saldo=1000.0)
