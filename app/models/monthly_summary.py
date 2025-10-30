from app import db
from datetime import datetime


class MonthlySummary(db.Model):
    """Righe riassuntive mensili (usate per storico e per il rollover)."""
    __tablename__ = 'monthly_summary'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    entrate = db.Column(db.Float, nullable=False, default=0.0)
    uscite = db.Column(db.Float, nullable=False, default=0.0)
    bilancio = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('year', 'month', name='uix_year_month_summary'),
    )

    def __repr__(self):
        return f"<MonthlySummary {self.year}-{self.month} entrate={self.entrate} uscite={self.uscite} bilancio={self.bilancio}>"
