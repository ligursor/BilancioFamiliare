"""
Modello per le transazioni ricorrenti (entrate/uscite)

Contiene le informazioni necessarie per pianificare addebiti / accrediti ricorrenti:
- descrizione
- tipo: 'entrata' o 'uscita'
- importo
- giorno: giorno del mese in cui avviene l'addebito/accredito (1-31)
- prossima_data: data opzionale della prossima occorrenza (date)
- attivo: flag per abilitare/disabilitare la ricorrenza
"""
from datetime import date
from app import db


class RecurringTransaction(db.Model):
    __tablename__ = 'recurring_transaction'

    id = db.Column(db.Integer, primary_key=True)
    descrizione = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'entrata' o 'uscita'
    importo = db.Column(db.Float, nullable=False)
    giorno = db.Column(db.Integer, nullable=True)  # giorno del mese (1-31)
    prossima_data = db.Column(db.Date, nullable=True)  # data della prossima occorrenza
    attivo = db.Column(db.Boolean, default=True)
    cadenza = db.Column(db.String(20), nullable=False, default='mensile')  # 'mensile' o 'annuale'
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)

    categoria = db.relationship('Categoria', backref=db.backref('recurring_transactions', lazy=True))

    def __repr__(self):
        return f"<RecurringTransaction {self.descrizione} ({self.tipo}) {self.importo}>"
