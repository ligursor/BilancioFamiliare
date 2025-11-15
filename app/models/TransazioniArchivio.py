"""Modello per l'archivio delle transazioni eliminate durante il rollover"""
from app import db
from datetime import datetime

class TransazioniArchivio(db.Model):
    """Modello per archiviare le transazioni eliminate durante il rollover mensile"""
    __tablename__ = 'transazioni_archivio'
    
    id = db.Column(db.Integer, primary_key=True)
    # Campi originali della transazione
    transazione_id = db.Column(db.Integer, nullable=False)  # ID originale della transazione
    data = db.Column(db.Date, nullable=False)
    data_effettiva = db.Column(db.Date, nullable=True)
    descrizione = db.Column(db.String(200), nullable=False)
    importo = db.Column(db.Float, nullable=False)
    categoria_id = db.Column(db.Integer, nullable=True)
    categoria_nome = db.Column(db.String(100), nullable=True)  # Denormalizzato per preservare il nome
    id_periodo = db.Column(db.Integer, nullable=False, index=True)  # Periodo di appartenenza
    tipo = db.Column(db.String(20), nullable=False)  # 'entrata' o 'uscita'
    tx_ricorrente = db.Column(db.Boolean, default=False)
    id_recurring_tx = db.Column(db.Integer, nullable=True)
    tx_modificata = db.Column(db.Boolean, default=False, nullable=False)
    
    # Metadati archiviazione
    data_archiviazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TransazioniArchivio id={self.id} tx_id={self.transazione_id} periodo={self.id_periodo} {self.descrizione}>'
