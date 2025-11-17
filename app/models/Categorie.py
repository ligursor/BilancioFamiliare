"""Modelli base - Categorie e SaldoIniziale"""
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
# The SaldoIniziale model was replaced in favor of using the `strumento`
# table (instrument "Conto Bancoposta") as the canonical source for the
# global starting balance. If the legacy `saldo_iniziale` table exists,
# consider dropping it via a migration after confirming there are no
# runtime references.
