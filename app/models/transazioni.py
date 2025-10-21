"""
Modello per le transazioni
"""
from app import db
from datetime import datetime, date

class Transazione(db.Model):
    """Modello per le transazioni finanziarie"""
    __tablename__ = 'transazione'
    
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    data_effettiva = db.Column(db.Date, nullable=True)  # NULL = transazione programmata
    descrizione = db.Column(db.String(200), nullable=False)
    importo = db.Column(db.Float, nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)
    categoria = db.relationship('Categoria', backref=db.backref('transazioni', lazy=True))
    tipo = db.Column(db.String(20), nullable=False)  # 'entrata' o 'uscita'
    ricorrente = db.Column(db.Boolean, default=False)
    frequenza_giorni = db.Column(db.Integer, default=0)  # 30=mensile, 365=annuale
    transazione_madre_id = db.Column(db.Integer, db.ForeignKey('transazione.id'), nullable=True)
    figli = db.relationship('Transazione', backref=db.backref('madre', remote_side=[id]), lazy='dynamic')
    
    @property
    def e_programmata(self):
        """Restituisce True se la transazione è programmata (data futura e non ancora effettuata)"""
        return self.data_effettiva is None and self.data > datetime.now().date()
    
    @property
    def e_effettuata(self):
        """Restituisce True se la transazione è stata effettuata"""
        return self.data_effettiva is not None or self.data <= datetime.now().date()
    
    @property
    def e_in_attesa(self):
        """Restituisce True se la transazione è in attesa"""
        return self.data_effettiva is None and self.data > datetime.now().date()
    
    def __repr__(self):
        return f'<Transazione {self.descrizione}: {self.importo} ({self.tipo})>'
