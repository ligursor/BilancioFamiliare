from app import db


class MonthlyBudget(db.Model):
    """Budget specifico per mese e categoria: permette override mensili del budget di default."""
    __tablename__ = 'monthly_budget'

    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    importo = db.Column(db.Float, nullable=False, default=0.0)

    __table_args__ = (
        db.UniqueConstraint('categoria_id', 'year', 'month', name='uix_categoria_year_month'),
    )

    def __repr__(self):
        return f"<MonthlyBudget categoria={self.categoria_id} {self.year}-{self.month} importo={self.importo}>"
