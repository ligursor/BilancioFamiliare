"""Modello per le transazioni"""
from app import db
from datetime import datetime, date

class Transazioni(db.Model):
    """Modello per le transazioni finanziarie"""
    __tablename__ = 'transazioni'
    
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    data_effettiva = db.Column(db.Date, nullable=True)  # NULL = transazioni programmata
    descrizione = db.Column(db.String(200), nullable=False)
    importo = db.Column(db.Float, nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorie.id'), nullable=True)
    categoria = db.relationship('Categorie', backref=db.backref('transazioni', lazy=True))
    # id_periodo: integer in format YYYYMM representing the financial month (end_date year/month)
    id_periodo = db.Column(db.Integer, nullable=True, index=True)
    tipo = db.Column(db.String(20), nullable=False)  # 'entrata' o 'uscita'
    ricorrente = db.Column(db.Boolean, default=False)
    # Nota: il campo `frequenza_giorni` e `transazione_madre_id` sono stati rimossi
    # in favore di un riferimento diretto alla ricorrenza (se presente) tramite
    # `id_recurring_tx` che punta alla tabella `transazioni_ricorrenti`.
    id_recurring_tx = db.Column(db.Integer, nullable=True)
    
    def __repr__(self):
        return f'<Transazioni {self.descrizione}: {self.importo} ({self.tipo})>'
