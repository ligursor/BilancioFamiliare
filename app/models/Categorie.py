"""
Modelli base - Categorie e SaldoIniziale
"""
from app import db
from datetime import datetime

class Categorie(db.Model):
    """Modello per le categorie di transazioni"""
    __tablename__ = 'categorie'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'entrata' o 'uscita'
    
    def __repr__(self):
        return f'<Categorie {self.nome} ({self.tipo})>'
# NOTE: The SaldoIniziale model was intentionally removed in favor of using
# the `strumento` table (instrument "Conto Bancoposta") as the canonical
# source for global starting balance. The database table `saldo_iniziale`
# may still exist and should be dropped via a migration once you've
# confirmed there are no remaining runtime references (we've searched and
# reported remaining references separately).
