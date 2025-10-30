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
    # Nota: il campo `frequenza_giorni` e `transazione_madre_id` sono stati rimossi
    # in favore di un riferimento diretto alla ricorrenza (se presente) tramite
    # `id_recurring_tx` che punta alla tabella `recurring_transaction`.
    id_recurring_tx = db.Column(db.Integer, nullable=True)
    
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
