"""
Modelli base - Categoria e SaldoIniziale
"""
from app import db
from datetime import datetime

class Categoria(db.Model):
    """Modello per le categorie di transazioni"""
    __tablename__ = 'categoria'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'entrata' o 'uscita'
    
    def __repr__(self):
        return f'<Categoria {self.nome} ({self.tipo})>'

class SaldoIniziale(db.Model):
    """Modello per il saldo iniziale del conto"""
    __tablename__ = 'saldo_iniziale'
    
    id = db.Column(db.Integer, primary_key=True)
    importo = db.Column(db.Float, nullable=False, default=0.0)
    data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SaldoIniziale {self.importo}>'
