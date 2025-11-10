"""Modello per il Libretto Smart"""
from app import db
from datetime import datetime


class Libretto(db.Model):
    """Modello per il Libretto Smart Poste Italiane"""
    __tablename__ = 'libretto'
    
    id = db.Column(db.Integer, primary_key=True)
    identificativo = db.Column(db.String(100), nullable=False, unique=True)
    intestatari = db.Column(db.String(200), nullable=False)
    saldo_disponibile = db.Column(db.Float, nullable=False, default=0.0)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relazione con i depositi Supersmart
    depositi = db.relationship('Supersmart', backref='libretto', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Libretto {self.identificativo}>'
    
    @property
    def totale_depositi_attivi(self):
        """Calcola il totale dei depositi attivi (non scaduti)"""
        oggi = datetime.now().date()
        return sum(d.deposito for d in self.depositi if d.data_scadenza and d.data_scadenza >= oggi)
    
    @property
    def numero_depositi_attivi(self):
        """Conta il numero di depositi attivi"""
        oggi = datetime.now().date()
        return len([d for d in self.depositi if d.data_scadenza and d.data_scadenza >= oggi])
