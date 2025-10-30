from app import db

class MonthlySummary(db.Model):
    """Righe riassuntive mensili (usate per storico e per il rollover)."""
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

    @property
    def bilancio(self):
        """Return the month balance (entrate - uscite) using stored saldo values when available."""
        base = float(self.saldo_iniziale or 0.0)
        finale = self.saldo_finale
        if finale is None:
            finale = base + float(self.entrate or 0.0) - float(self.uscite or 0.0)
        return float(finale) - base

    def __repr__(self):
        return (
            f"<MonthlySummary {self.year}-{self.month} "
            f"saldo_iniziale={self.saldo_iniziale} entrate={self.entrate} "
            f"uscite={self.uscite} saldo_finale={self.saldo_finale}>"
        )
