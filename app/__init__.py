"""Applicazione Flask per gestione bilancio familiare"""

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

    @app.context_processor
    def inject_conti_personali():
        """Inietta nei template la lista dei conti personali presenti nel DB.

        Restituisce `conti_personali` come lista di dizionari con chiavi `id` e `nome`.
        """
        try:
            from app.models.ContoPersonale import ContoPersonale
            conti = ContoPersonale.query.order_by(ContoPersonale.nome_conto.asc()).all()
            conti_list = [{'id': c.id, 'nome': c.nome_conto} for c in conti]
            return {'conti_personali': conti_list}
        except Exception:
            return {'conti_personali': []}

    @app.context_processor
    def inject_active_section():
        """Inietta nei template la sezione attiva corrente basandosi sull'endpoint"""
        from flask import request
        
        # Mappatura degli endpoint alle sezioni con icone e nomi
        section_map = {
            'main.index': {'name': 'Dashboard', 'icon': 'fas fa-home'},
            'dashboard.view': {'name': 'Dashboard', 'icon': 'fas fa-home'},
            'dettaglio_periodo.index': {'name': 'Dettaglio Mese', 'icon': 'fas fa-calendar-alt'},
            'dettaglio_periodo.mese': {'name': 'Dettaglio Mese', 'icon': 'fas fa-calendar-alt'},
            'dettaglio_periodo.dettaglio': {'name': 'Dettaglio Periodo', 'icon': 'fas fa-calendar-alt'},
            'categorie.lista': {'name': 'Categorie', 'icon': 'fas fa-tags'},
            'ricorrenti.lista': {'name': 'Ricorrenti', 'icon': 'fas fa-sync-alt'},
            'paypal.dashboard': {'name': 'PayPal', 'icon': 'fab fa-paypal'},
            'ppay.evolution': {'name': 'PPay Evolution', 'icon': 'fas fa-credit-card'},
            'libretto.dashboard': {'name': 'Libretto Smart', 'icon': 'fas fa-book'},
            'veicoli.garage': {'name': 'Garage', 'icon': 'fas fa-car'},
            'passwd.index': {'name': 'Password Manager', 'icon': 'fas fa-key'},
            'main.reset': {'name': 'Reset', 'icon': 'fas fa-undo'},
        }
        
        # Gestione speciale per i conti personali e veicoli
        endpoint = request.endpoint or ''
        active_section = {'name': 'Dashboard', 'icon': 'fas fa-home'}
        
        if endpoint.startswith('conti.'):
            # Per i conti personali, prova a recuperare il nome dal percorso
            try:
                from app.models.ContoPersonale import ContoPersonale
                conto_id = request.view_args.get('conto_id')
                if conto_id:
                    conto = ContoPersonale.query.get(conto_id)
                    if conto:
                        active_section = {'name': f'Conto {conto.nome_conto}', 'icon': 'fas fa-user-circle'}
                    else:
                        active_section = {'name': 'Conto Personale', 'icon': 'fas fa-user-circle'}
                else:
                    active_section = {'name': 'Conto Personale', 'icon': 'fas fa-user-circle'}
            except Exception:
                active_section = {'name': 'Conto Personale', 'icon': 'fas fa-user-circle'}
        elif endpoint.startswith('veicoli.'):
            # Per i veicoli, prova a recuperare il nome/marca/modello dal percorso
            if endpoint == 'veicoli.garage':
                active_section = {'name': 'Garage', 'icon': 'fas fa-car'}
            else:
                try:
                    from app.models.Veicoli import Veicoli
                    veicolo_id = request.view_args.get('veicolo_id')
                    if veicolo_id:
                        veicolo = Veicoli.query.get(veicolo_id)
                        if veicolo:
                            # Determina l'icona in base al tipo di veicolo
                            icon_map = {
                                'auto': 'fas fa-car',
                                'moto': 'fas fa-motorcycle',
                                'bici': 'fas fa-bicycle'
                            }
                            icona = icon_map.get(veicolo.tipo, 'fas fa-car')
                            nome_veicolo = veicolo.modello if hasattr(veicolo, 'modello') else 'Veicolo'
                            active_section = {'name': nome_veicolo, 'icon': icona}
                        else:
                            active_section = {'name': 'Dettaglio Veicolo', 'icon': 'fas fa-car'}
                    else:
                        active_section = {'name': 'Garage', 'icon': 'fas fa-car'}
                except Exception:
                    active_section = {'name': 'Garage', 'icon': 'fas fa-car'}
        elif endpoint in section_map:
            active_section = section_map[endpoint]
        
        return {'active_section': active_section}

    # Jinja filter: format_currency (re-uses helper in app.utils.formatting)
    try:
        from app.utils.formatting import format_currency as format_currency_helper
        app.jinja_env.filters['format_currency'] = format_currency_helper
    except Exception:
        # Fallback: register a minimal local formatter if the helper cannot be imported
        def _fc(value):
            try:
                v = float(value) if value is not None else 0.0
            except Exception:
                try:
                    v = float(str(value))
                except Exception:
                    v = 0.0
            fmt = app.config.get('FORMATO_VALUTA', '€ {:.2f}')
            try:
                return fmt.format(v)
            except Exception:
                return f'€ {v:.2f}'

        app.jinja_env.filters['format_currency'] = _fc
    
    # Importa e registra i blueprint
    from app.views.main import main_bp
    from app.views.transazioni.categorie import categorie_bp
    from app.views.transazioni.dettaglio_periodo import dettaglio_periodo_bp
    from app.views.transazioni.dashboard import dashboard_bp
    from app.views.transazioni.ricorrenti import ricorrenti_bp
    from app.views.paypal import paypal_bp
    from app.views.conto_personale import conti_bp
    from app.views.veicoli.veicoli import veicoli_bp
    from app.views.ppay_evolution import ppay_bp
    from app.views.libretto import libretto_bp
    # Password manager blueprint (integrated)
    try:
        from app.views.passwd_manager.passwd_manager import bp as passwd_bp
    except Exception:
        passwd_bp = None
    
    app.register_blueprint(main_bp)
    # transazioni blueprint removed: /transazioni route deprecated
    app.register_blueprint(categorie_bp, url_prefix='/categorie')
    app.register_blueprint(dettaglio_periodo_bp, url_prefix='/dettaglio')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(ricorrenti_bp, url_prefix='/ricorrenti')
    app.register_blueprint(paypal_bp, url_prefix='/paypal')
    app.register_blueprint(conti_bp, url_prefix='/conti')
    app.register_blueprint(veicoli_bp, url_prefix='/veicoli')
    app.register_blueprint(ppay_bp, url_prefix='/ppay_evolution')
    app.register_blueprint(libretto_bp, url_prefix='/libretto')
    if passwd_bp:
        # mount the passwd manager under /passwd
        app.register_blueprint(passwd_bp, url_prefix='/passwd')

    # Protezione globale: richiede che l'utente sia autenticato tramite il
    # password-manager per accedere alle pagine dell'app principale.
    # Esclude le rotte statice e il blueprint del passwd manager.
    from flask import request, redirect, url_for, session, render_template

    # Alias comodo: serve direttamente il template di login su /login
    @app.route('/login')
    def login_alias():
        # Render the shared login template directly (POST continues to be
        # handled by the passwd manager blueprint at /passwd/login)
        return render_template('login.html')

    @app.before_request
    def require_passwd_auth():
        try:
            path = request.path or ''
            # Allow access to passwd manager itself and static assets
            if path.startswith('/passwd') or path.startswith('/static') or path.startswith('/favicon.ico'):
                return
            # If session indicates authenticated, allow
            if session.get('authenticated') and session.get('user_password'):
                return
            # Allow health endpoints or probes if present
            if path.startswith('/_health') or path.startswith('/health'):
                return
            # Otherwise redirect to passwd login
            return redirect(url_for('passwd.login'))
        except Exception:
            # In case of any error, allow request to proceed to avoid blocking
            return
    # appunti blueprint removed
    # database import/export blueprint removed (archived in _backup/obsolete)

    # Ensure budget_mensili table has residuo_mensile column (migration)
    @app.before_request
    def ensure_budget_mensili_migration():
        """Run once to add residuo_mensile column to budget_mensili if missing"""
        try:
            from app.services.budget.migrate_add_residuo_mensile import add_residuo_mensile_column
            # This will only add the column if it doesn't exist
            add_residuo_mensile_column()
        except Exception:
            # Silent fail - column might already exist or table not ready yet
            pass

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
    
    # If the configured SQLite file doesn't exist, create tables on app startup
    # to make tests and local runs smoother. This is best-effort and non-destructive.
    try:
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri.startswith('sqlite:///'):
            # Ensure SQLAlchemy metadata is populated by importing model modules
            with app.app_context():
                try:
                    import importlib
                    models_dir = os.path.join(os.path.dirname(__file__), 'models')
                    if os.path.isdir(models_dir):
                        for fn in os.listdir(models_dir):
                            if fn.endswith('.py') and not fn.startswith('__'):
                                mod_name = f"app.models.{fn[:-3]}"
                                try:
                                    importlib.import_module(mod_name)
                                except Exception:
                                    # ignore individual model import errors; best-effort
                                    pass
                except Exception:
                    pass
                try:
                    db.create_all()
                except Exception:
                    # swallow errors; migrations or manual setup may be used instead
                    pass
    except Exception:
        pass

    return app
