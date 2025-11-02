from app import db
from datetime import date, datetime


class TransazioniRicorrenti(db.Model):
	"""Rappresenta una transazioni ricorrente (configurazione di spesa/entrata)."""
	__tablename__ = 'transazioni_ricorrenti'

	id = db.Column(db.Integer, primary_key=True)
	descrizione = db.Column(db.String(200), nullable=False)
	tipo = db.Column(db.String(20), nullable=False)  # 'entrata' o 'uscita'
	importo = db.Column(db.Float, nullable=False)
	# giorno del mese (1..31) usato per mappare la ricorrenza sul mese di riferimento
	giorno = db.Column(db.Integer, nullable=True)
	prossima_data = db.Column(db.Date, nullable=True)
	cadenza = db.Column(db.String(20), nullable=True, default='mensile')
	categoria_id = db.Column(db.Integer, db.ForeignKey('categorie.id'), nullable=True)
	# se True: per questo recurring mensile NON generare la riga nel mese se
	# esiste un recurring annuale equivalente (es. stipendio mensile vs stipendio dicembre)
	skip_month_if_annual = db.Column(db.Integer, nullable=False, default=0)

	# Relationship
	categoria = db.relationship('Categorie', backref='transazioni_ricorrenti')

	def __repr__(self):
		return f"<TransazioniRicorrenti {self.descrizione} {self.importo} giorno={self.giorno} cadenza={self.cadenza}>"

