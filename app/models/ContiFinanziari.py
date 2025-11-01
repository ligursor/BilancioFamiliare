"""Modello Strumento

Contiene gli strumenti/conti usati dall'app (es. Conto Bancoposta, Postepay Evolution,
conti personali, ecc.).
"""
from app import db


class Strumento(db.Model):
    """Modello per la tabella `strumento`"""
    # Renamed DB table to 'conti_finanziari'
    __tablename__ = 'conti_finanziari'

    id_conto = db.Column(db.Integer, primary_key=True)
    descrizione = db.Column(db.String(200), nullable=False, unique=True)
    tipologia = db.Column(db.String(50), nullable=False)
    saldo_iniziale = db.Column(db.Float, nullable=False, default=0.0)
    saldo_corrente = db.Column(db.Float, nullable=False, default=0.0)

    def __repr__(self):
        return f"<Strumento {self.descrizione} ({self.tipologia}) saldo={self.saldo_corrente}>"
