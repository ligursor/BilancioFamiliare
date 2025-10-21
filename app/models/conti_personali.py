"""
Modelli per i conti personali
"""
from app import db
from datetime import datetime, date

class ContoPersonale(db.Model):
    """Modello per i conti personali di Maurizio e Antonietta"""
    __tablename__ = 'conto_personale'
    
    id = db.Column(db.Integer, primary_key=True)
    nome_conto = db.Column(db.String(50), nullable=False)  # 'Maurizio' o 'Antonietta'
    saldo_iniziale = db.Column(db.Float, nullable=False)
    saldo_corrente = db.Column(db.Float, nullable=False)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ContoPersonale {self.nome_conto}: {self.saldo_corrente}>'

class VersamentoPersonale(db.Model):
    """Modello per i versamenti sui conti personali"""
    __tablename__ = 'versamento_personale'
    
    id = db.Column(db.Integer, primary_key=True)
    conto_id = db.Column(db.Integer, db.ForeignKey('conto_personale.id'), nullable=False)
    conto = db.relationship('ContoPersonale', backref=db.backref('versamenti', lazy=True, cascade='all, delete-orphan'))
    data = db.Column(db.Date, nullable=False, default=datetime.now().date)
    descrizione = db.Column(db.String(200), nullable=False)
    importo = db.Column(db.Float, nullable=False)
    saldo_dopo_versamento = db.Column(db.Float, nullable=False)
    data_inserimento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<VersamentoPersonale {self.conto.nome_conto}: {self.importo}>'
