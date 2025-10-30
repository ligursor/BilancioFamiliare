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
    from app.views.bilancio.categorie import categorie_bp
    from app.views.bilancio.dettaglio_periodo import dettaglio_periodo_bp
    from app.views.bilancio.dashboard import dashboard_bp
    from app.views.paypal import paypal_bp
    from app.views.conti_personali import conti_bp
    from app.views.garage.auto import auto_bp
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
    
    return app
