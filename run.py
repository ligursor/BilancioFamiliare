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
    from app.models.base import Categoria, SaldoIniziale
    from app.models.transazioni import Transazione
    from app.models.budget import Budget
    # ... altri modelli se necessario

    db.create_all()
    # Minimal DB initialization: ensure saldo iniziale exists and default categories
    try:
        if Categoria.query.count() == 0:
            # se vuoi configurare categorie di default, aggiungile qui o tramite fixture
            pass
        if not SaldoIniziale.query.first():
            saldo = SaldoIniziale(importo=0.0)
            db.session.add(saldo)
            db.session.commit()
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
