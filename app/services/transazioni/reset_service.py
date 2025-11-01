from app.services import BaseService, get_month_boundaries
from app.services.conti_finanziari.strumenti_service import StrumentiService
from app.models.Transazioni import Transazioni as Transazione
from app import db
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import text
import os
import shutil
from flask import current_app


class ResetService(BaseService):
    """Servizio per resettare il sistema: imposta saldo iniziale, rigenera transazioni e riepiloghi mensili."""

    def reset_horizon(self, importo, months=6, base_date=None, full_wipe=False):
        """Esegue il reset:
        - registra/aggiorna `SaldoIniziale` con `importo`
        - elimina le transazioni generate dalle ricorrenze nell'orizzonte e le ricrea
        - elimina i `monthly_summary` nell'orizzonte e li rigenera

        Restituisce (True, info_dict) o (False, error_message)
        """
        if base_date is None:
            base_date = date.today()

        # Determine the financial month using the shared get_month_boundaries logic
        # and set the reset start to the first day of the financial month's end_date.
        # This makes the reset align with the "end_date month" semantics (27..26 window).
        _, financial_end = get_month_boundaries(base_date)
        start_date = date(financial_end.year, financial_end.month, 1)

        try:
            # Automatic DB backup (best-effort)
            backup_path = None
            try:
                # Try to infer sqlite DB path from SQLALCHEMY_DATABASE_URI
                db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '') if current_app else ''
            except Exception:
                db_uri = ''

            db_path = None
            if db_uri and db_uri.startswith('sqlite'):
                # handle sqlite:///absolute/path and sqlite://relative
                if db_uri.startswith('sqlite:///'):
                    db_path = db_uri[len('sqlite:///'):]
                else:
                    db_path = db_uri.replace('sqlite://', '')
                if db_path == ':memory:':
                    db_path = None
            # fallback to repository db path
            if not db_path:
                repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
                candidate = os.path.join(repo_root, 'db', 'bilancio.db')
                if os.path.exists(candidate):
                    db_path = candidate

            if db_path and os.path.exists(db_path):
                try:
                    # Save backup in the same directory as the DB file
                    backup_dir = os.path.dirname(db_path) or os.getcwd()
                    os.makedirs(backup_dir, exist_ok=True)
                    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    base_name = os.path.splitext(os.path.basename(db_path))[0]
                    ext = os.path.splitext(db_path)[1] or '.db'
                    backup_name = f"{base_name}_backup_{ts}{ext}"
                    backup_path = os.path.join(backup_dir, backup_name)
                    shutil.copy2(db_path, backup_path)
                except Exception:
                    backup_path = None

            # 1) Update the 'Conto Bancoposta' strumento saldo_iniziale (and saldo_corrente)
            try:
                ss = StrumentiService()
                s = ss.get_by_descrizione('Conto Bancoposta')
                if s:
                    ss.update_saldo_iniziale_by_id(s.id_conto, float(importo))
                    # also set current balance to the new starting amount
                    ss.update_saldo_by_id(s.id_conto, float(importo))
                else:
                    ss.ensure_strumento('Conto Bancoposta', 'conto_bancario', float(importo))
            except Exception:
                # best-effort: ignore failures here and proceed with reset
                pass

            # Enforce global maximum horizon of 6 months
            try:
                months = int(months)
            except Exception:
                months = 6
            if months > 6:
                months = 6

            # 2) Compute last day of horizon
            last_period = start_date + relativedelta(months=months-1)
            _, last_end = get_month_boundaries(last_period)

            # Deletion of existing generated data is delegated to the centralized
            # `recreate_generated_and_summaries` helper via the `full_wipe` flag.
            # Initialize counters; the helper will populate them when appropriate.
            deleted_transactions = None
            deleted_summaries = None

            # 4-5) Use the centralized recreate logic (script logic) to repopulate transactions and summaries
            try:
                from app.services.transazioni.recreate_generated_and_summaries import recreate_generated_and_summaries
                # Delegate deletion/repopulation to the centralized helper and
                # perform real changes (no preview) for Reset.
                rr = recreate_generated_and_summaries(months=months, base_date=start_date, full_wipe=full_wipe)
                created = rr.get('created_generated_transactions', 0)
                ms_created = rr.get('monthly_summary_regenerated', 0)
                deleted_transactions = rr.get('deleted_transazioni', deleted_transactions)
                deleted_summaries = rr.get('deleted_monthly_summary', deleted_summaries)
            except Exception:
                created = 0
                ms_created = 0

            info = {
                'saldo_importo': float(importo),
                'deleted_transactions_total': int(deleted_transactions) if (deleted_transactions is not None) else None,
                'deleted_monthly_summary_total': int(deleted_summaries) if (deleted_summaries is not None) else None,
                'created_generated_transactions': int(created or 0),
                'monthly_summary_regenerated': ms_created,
                'backup_path': backup_path,
            }

            return True, info
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            return False, str(e)
