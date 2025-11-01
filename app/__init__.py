"""
Applicazione Flask per gestione bilancio familiare
Architettura modulare e object-oriented

Struttura:
- models/: Modelli del database
- views/: Blueprint per le route
- services/: Logica di business
- utils/: Utilità e helper
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from sqlalchemy import text
from app.config import config

# Istanze globali
db = SQLAlchemy()

def create_app(config_name='default'):
    """Factory pattern per creare l'applicazione Flask"""
    # Calcola i path corretti per template e static
    import os
    
    # Le directory templates e static sono ora dentro il modulo app
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))
    
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir)
    
    # Carica la configurazione di default (app gira in locale con DEBUG disabilitato)
    app.config.from_object(config[config_name])
    
    # Inizializza le estensioni
    db.init_app(app)
    
    # Registra i context processor
    @app.context_processor
    def inject_datetime():
        return {'datetime': datetime}
    
    # Importa e registra i blueprint
    from app.views.main import main_bp
    from app.views.transazioni.categorie import categorie_bp
    from app.views.transazioni.dettaglio_periodo import dettaglio_periodo_bp
    from app.views.transazioni.dashboard import dashboard_bp
    from app.views.paypal import paypal_bp
    from app.views.conto_personale import conti_bp
    from app.views.veicoli.auto import auto_bp
    from app.views.ppay_evolution import ppay_bp
    from app.views.appunti import appunti_bp
    
    app.register_blueprint(main_bp)
    # transazioni blueprint removed: /transazioni route deprecated
    app.register_blueprint(categorie_bp, url_prefix='/categorie')
    app.register_blueprint(dettaglio_periodo_bp, url_prefix='/dettaglio')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(paypal_bp, url_prefix='/paypal')
    app.register_blueprint(conti_bp, url_prefix='/conti')
    app.register_blueprint(auto_bp, url_prefix='/auto')
    app.register_blueprint(ppay_bp, url_prefix='/ppay_evolution')
    app.register_blueprint(appunti_bp, url_prefix='/appunti')
    # database import/export blueprint removed (archived in _backup/obsolete)

    # Run monthly rollover once per financial-month when the app is first accessed
    @app.before_request
    def maybe_run_monthly_rollover():
        try:
            from datetime import date
            from app.services import get_month_boundaries
            today = date.today()
            # Only consider running on/after day 27
            if today.day < 27:
                return

            start_date, end_date = get_month_boundaries(today)
            # Use the financial-month identifier based on the period end (e.g. 27/10..26/11 -> 'YYYY-11')
            marker = end_date.strftime('%Y-%m')

            # Persist marker in DB (table `rollover_state`). Create table if missing.
            try:
                # Ensure table exists (best-effort SQL)
                db.session.execute(text('CREATE TABLE IF NOT EXISTS rollover_state (id INTEGER PRIMARY KEY, marker TEXT UNIQUE, updated_at DATETIME)'))
                db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass

            # Read current marker from DB
            prev = None
            try:
                from app.models.RolloverState import RolloverState
                r = db.session.query(RolloverState).order_by(RolloverState.id.asc()).first()
                if r:
                    prev = (r.marker or '').strip()
            except Exception:
                prev = None

            if prev == marker:
                return

            # Not yet run for this financial period — run the rollover (non-destructive default)
            try:
                from app.services.transazioni.monthly_rollover_service import do_monthly_rollover
                res = do_monthly_rollover(force=False, months=1, base_date=today)
                app.logger.info('Monthly rollover auto-run result: %s', res)
            except Exception as e:
                app.logger.exception('Error running monthly rollover on startup: %s', e)

            # record marker in DB so we don't run again until next financial period
            try:
                from app.models.RolloverState import RolloverState
                r = db.session.query(RolloverState).order_by(RolloverState.id.asc()).first()
                if not r:
                    r = RolloverState(marker=marker)
                    db.session.add(r)
                else:
                    r.marker = marker
                db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
        except Exception:
            # be silent on any error to avoid breaking requests
            try:
                app.logger.exception('maybe_run_monthly_rollover failed')
            except Exception:
                pass
    
    return app
