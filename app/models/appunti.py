"""
Modello per gli appunti/promemoria
"""
from app import db
from datetime import datetime

class Appunto(db.Model):
    """Modello per gli appunti/promemoria di spese future"""
    __tablename__ = 'appunto'
    
    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default='uscita')  # 'uscita', 'entrata'
    importo_stimato = db.Column(db.Float, nullable=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)
    categoria = db.relationship('Categoria', backref=db.backref('appunti', lazy=True))
    note = db.Column(db.Text, nullable=True)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Appunto {self.titolo}: {self.importo_stimato or "N/A"}>'
