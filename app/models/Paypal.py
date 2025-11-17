"""Modelli per la gestione PayPal"""
from app import db
from datetime import datetime, date

class PaypalAbbonamenti(db.Model):
    """Modello per i piani di pagamento PayPal a 3 rate"""
    __tablename__ = 'paypal_abbonamenti'
    
    id = db.Column(db.Integer, primary_key=True)
    descrizione = db.Column(db.String(200), nullable=False)
    importo_totale = db.Column(db.Float, nullable=False)
    importo_rata = db.Column(db.Float, nullable=False)
    data_prima_rata = db.Column(db.Date, nullable=False)
    data_seconda_rata = db.Column(db.Date, nullable=False)
    data_terza_rata = db.Column(db.Date, nullable=False)
    importo_rimanente = db.Column(db.Float, nullable=True, default=0.0)
    stato = db.Column(db.String(20), nullable=False, default='attivo')  # 'attivo', 'completato', 'sospeso'
    note = db.Column(db.Text, nullable=True)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<PaypalAbbonamenti {self.descrizione}: {self.importo_totale}>'

class PaypalMovimenti(db.Model):
    """Modello per le singole rate dei piani PayPal"""
    __tablename__ = 'paypal_movimenti'
    
    id = db.Column(db.Integer, primary_key=True)
    piano_id = db.Column(db.Integer, db.ForeignKey('paypal_abbonamenti.id'), nullable=False)
    piano = db.relationship('PaypalAbbonamenti', backref=db.backref('rate', lazy=True, cascade='all, delete-orphan'))
    numero_rata = db.Column(db.Integer, nullable=False)  # 1, 2, 3
    importo = db.Column(db.Float, nullable=False)
    data_scadenza = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.Date, nullable=True)
    stato = db.Column(db.String(20), nullable=False, default='in_attesa')  # 'in_attesa', 'pagata', 'scaduta'
    # Note: PaypalMovimenti intentionally does not link to Transazioni and
    # remains independent from the application's `transazioni` table.
    
    def __repr__(self):
        return f'<PaypalMovimenti {self.piano.descrizione} - Rata {self.numero_rata}: {self.importo}>'
    
