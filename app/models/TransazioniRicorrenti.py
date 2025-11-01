from app import db
from datetime import date, datetime


class TransazioniRicorrenti(db.Model):
	"""Rappresenta una transazioni ricorrente (configurazione di spesa/entrata)."""
	__tablename__ = 'transazioni_ricorrenti'

	id = db.Column(db.Integer, primary_key=True)
	descrizione = db.Column(db.String(200), nullable=False)
	importo = db.Column(db.Float, nullable=False)
	categoria_id = db.Column(db.Integer, db.ForeignKey('categorie.id'), nullable=True)
	tipo = db.Column(db.String(20), nullable=False)  # 'entrata' o 'uscita'
	# giorno del mese (1..31) usato per mappare la ricorrenza sul mese di riferimento
	giorno = db.Column(db.Integer, nullable=False, default=1)
	# frequenza: per ora supportiamo 'monthly', possibile estendere
	frequenza = db.Column(db.String(20), nullable=False, default='monthly')
	data_inizio = db.Column(db.Date, nullable=True)
	data_fine = db.Column(db.Date, nullable=True)
	attivo = db.Column(db.Boolean, default=True)
	note = db.Column(db.String(500), nullable=True)
	created_at = db.Column(db.DateTime, default=datetime.utcnow)
	# se True: per questo recurring mensile NON generare la riga nel mese se
	# esiste un recurring annuale equivalente (es. stipendio mensile vs stipendio dicembre)
	skip_month_if_annual = db.Column(db.Integer, nullable=False, default=0)

	def __repr__(self):
		return f"<TransazioniRicorrenti {self.descrizione} {self.importo} giorno={self.giorno} freq={self.frequenza}>"

