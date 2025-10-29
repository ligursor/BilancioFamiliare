"""
Modelli base del database
"""
from datetime import datetime, date

class BaseModel:
    """Modello base con funzionalità comuni"""
    __abstract__ = True
    
    def init_base_columns(self, db):
        """Inizializza le colonne base - chiamato dai modelli concreti"""
        self.id = db.Column(db.Integer, primary_key=True)
        self.data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
        self.data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

# I modelli concreti saranno definiti nei singoli file
# per evitare import circolari

# Import esplicito dei modelli per assicurare che siano registrati quando l'app importa
try:
    # noqa: F401 - imported for side-effects (model registration)
    from app.models.recurring_transaction import RecurringTransaction
except Exception:
    # Import non critico durante alcune operazioni (es. strumenti leggeri)
    pass
try:
    # register generated transactions model
    from app.models.generated_transaction import GeneratedTransaction
except Exception:
    pass
