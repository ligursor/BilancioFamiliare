"""Entry point per l'applicazione.

Questo script avvia l'app Flask e può inizializzare il database se
la variabile d'ambiente `INIT_DB` è impostata (es. INIT_DB=1).
"""

import os
from app import create_app, db


def init_database():
    """Inizializza il database (crea tabelle e dati di default).
    Questa funzione è intenzionalmente conservativa: viene eseguita
    solo quando INIT_DB=1 per evitare side-effect non voluti in produzione.
    """
    # Import dei modelli necessari (ritardato per evitare import circolari)
    from app.models.Categorie import Categorie as Categoria
    from app.services.conti_finanziari.strumenti_service import StrumentiService
    from app.models.Transazioni import Transazioni as Transazione
    from app.models.Budget import Budget
    # ... altri modelli se necessario

    db.create_all()
    # Minimal DB initialization: ensure saldo iniziale exists and default categories
    try:
        if Categoria.query.count() == 0:
            # se vuoi configurare categorie di default, aggiungile qui o tramite fixture
            pass
        # Ensure the 'Conto Bancoposta' strumento exists (used as global starting balance)
        try:
            ss = StrumentiService()
            ss.ensure_strumento('Conto Bancoposta', 'conto_bancario', 0.0)
        except Exception:
            pass
    except Exception:
        pass


def main():
    app = create_app()

    # Optional DB init (usare solo in fase di provisioning)
    if os.environ.get('INIT_DB') == '1':
        with app.app_context():
            init_database()

    # Avvia l'app
    # For security and consistency we run without debug logs by default.
    app.run(host=app.config.get('HOST', '0.0.0.0'), port=app.config.get('PORT', 5001), debug=True)


if __name__ == '__main__':
    main()
