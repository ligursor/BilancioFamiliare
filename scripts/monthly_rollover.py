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
        from app.services.bilancio.monthly_rollover_service import do_monthly_rollover

        # call the service: force -> args.force, months -> args.months
        res = do_monthly_rollover(force=args.force, months=args.months)
        print('Monthly rollover result:', res)


if __name__ == '__main__':
    main()
