from app import db


class MonthlySummary(db.Model):
    """Riassunto mensile: saldo iniziale, entrate, uscite, saldo finale per anno/mese."""
    __tablename__ = 'monthly_summary'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    saldo_iniziale = db.Column(db.Float, nullable=False, default=0.0)
    entrate = db.Column(db.Float, nullable=False, default=0.0)
    uscite = db.Column(db.Float, nullable=False, default=0.0)
    saldo_finale = db.Column(db.Float, nullable=False, default=0.0)

    __table_args__ = (
        db.UniqueConstraint('year', 'month', name='uix_year_month_summary'),
    )

    def __repr__(self):
        return f"<MonthlySummary {self.year}-{self.month} saldo_iniziale={self.saldo_iniziale} saldo_finale={self.saldo_finale}>"
