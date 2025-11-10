"""Modello per i depositi Supersmart"""
from app import db
from datetime import datetime


class Supersmart(db.Model):
    """Modello per i depositi Supersmart del Libretto"""
    __tablename__ = 'supersmart'
    
    id = db.Column(db.Integer, primary_key=True)
    libretto_id = db.Column(db.Integer, db.ForeignKey('libretto.id'), nullable=False)
    descrizione = db.Column(db.String(200), nullable=False)
    data_attivazione = db.Column(db.Date, nullable=False)
    data_scadenza = db.Column(db.Date, nullable=False)
    tasso = db.Column(db.Float, nullable=False)  # Tasso di interesse percentuale
    deposito = db.Column(db.Float, nullable=False)  # Importo depositato
    netto = db.Column(db.Float, nullable=False)  # Guadagno netto
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Supersmart {self.descrizione}>'
    
    @property
    def totale_a_scadenza(self):
        """Calcola il totale che si riceverà a scadenza (deposito + netto)"""
        return self.deposito + self.netto
    
    @property
    def giorni_rimanenti(self):
        """Calcola i giorni rimanenti alla scadenza"""
        if not self.data_scadenza:
            return 0
        oggi = datetime.now().date()
        if self.data_scadenza < oggi:
            return 0
        return (self.data_scadenza - oggi).days
    
    @property
    def is_scaduto(self):
        """Verifica se il deposito è scaduto"""
        if not self.data_scadenza:
            return True
        return self.data_scadenza < datetime.now().date()
