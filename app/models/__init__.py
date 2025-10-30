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
