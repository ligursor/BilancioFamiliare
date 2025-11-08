from app import db


class BudgetMensili(db.Model):
    """Budget specifico per mese e categorie: permette override mensili del budget di default."""
    __tablename__ = 'budget_mensili'

    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    importo = db.Column(db.Float, nullable=False, default=0.0)
    # Residuo mensile calcolato: importo - spese_effettuate - spese_pianificate
    # Aggiornato alla fine del mese e usato nel rollover per calcolare il saldo iniziale del mese successivo
    residuo_mensile = db.Column(db.Float, nullable=False, default=0.0)

    __table_args__ = (
        db.UniqueConstraint('categoria_id', 'year', 'month', name='uix_categoria_year_month'),
    )

    def __repr__(self):
        return f"<BudgetMensili categorie={self.categoria_id} {self.year}-{self.month} importo={self.importo} residuo={self.residuo_mensile}>"
