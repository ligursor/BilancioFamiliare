"""
Modello per transazioni generate automaticamente a partire dalle ricorrenze

Questa tabella conserva le transazioni create dal meccanismo di rollover
per permettere una gestione separata rispetto alle transazioni manuali storiche.
"""
from datetime import datetime, date
from app import db


class GeneratedTransaction(db.Model):
    """Transazioni generate o importate: questa tabella diventa la sorgente principale
    per le transazioni dopo la re-inizializzazione dell'applicativo.
    """
    __tablename__ = 'generated_transaction'

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    descrizione = db.Column(db.String(200), nullable=False)
    importo = db.Column(db.Float, nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)
    tipo = db.Column(db.String(20), nullable=False)  # 'entrata' o 'uscita'
    recurring_id = db.Column(db.Integer, db.ForeignKey('recurring_transaction.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # relationship to categoria if needed
    categoria = db.relationship('Categoria', backref=db.backref('generated_transactions', lazy=True))

    def __repr__(self):
        return f"<GeneratedTransaction {self.data} {self.descrizione} {self.importo} ({self.tipo})>"
