#!/usr/bin/env python3
"""Smoke test script that uses the application's services under app context
to create/update/delete transactions and verify monthly summary changes.

This runs inside the repository and uses the same DB the app uses.
"""
from app import create_app
from app.services.bilancio.transazioni_service import TransazioneService
from app.services.bilancio.monthly_summary_service import MonthlySummaryService
from datetime import date


def main():
    app = create_app()
    with app.app_context():
        svc = TransazioneService()
        svc_ms = MonthlySummaryService()

        today = date.today()
        descr = 'SMOKE_TEST_TRANS_' + today.isoformat()
        # create a non-recurring transaction
        success, message, tx = svc.create_transazione(
            data=today,
            descrizione=descr,
            importo=11.11,
            categoria_id=None,  # create without category to simplify
            tipo='uscita',
            ricorrente=False,
            # Transazione model no longer accepts frequenza_giorni at construction;
            # it's handled by the service when needed. Do not pass it here.
            data_effettiva=today
        )
        print('Create non-recurring:', success, message, getattr(tx, 'id', None))

        # If created, update it
        if success and tx and tx.id:
            success_u, msg_u = svc.update(tx, descrizione=descr + '_UPDATED', importo=22.22)
            print('Update:', success_u, msg_u)

            # regenerate monthly summary for current month
            ym = (today.year, today.month)
            ok, res = svc_ms.regenerate_month_summary(ym[0], ym[1])
            print('Regenerate monthly summary:', ok, type(res), res)

            # delete the test transaction
            success_d, msg_d = svc.delete(tx)
            print('Delete:', success_d, msg_d)

        # Now test creating a recurring transaction via service (not via HTTP/form)
        descr2 = 'SMOKE_TEST_RECURRING_' + today.isoformat()
        success2, message2, tx2 = svc.create_transazione(
            data=today,
            descrizione=descr2,
            importo=5.0,
            categoria_id=None,
            tipo='uscita',
            ricorrente=True,
            frequenza_giorni=30,
            data_effettiva=None
        )
        print('Create recurring:', success2, message2, getattr(tx2, 'id', None))

        if success2 and tx2 and tx2.id:
            # count created children
                from app import db
                from sqlalchemy import text
                rows = db.session.execute(text("SELECT COUNT(*) FROM transazione WHERE id_recurring_tx = :mid"), {'mid': tx2.id}).fetchone()
                print('Recurring children count:', rows[0] if rows else 'unknown')


if __name__ == '__main__':
    main()
