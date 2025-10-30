from app import db
from datetime import datetime


class RolloverState(db.Model):
    """Singleton-like table to store the last rollover marker (financial period)."""
    __tablename__ = 'rollover_state'

    id = db.Column(db.Integer, primary_key=True)
    marker = db.Column(db.String(32), nullable=False, unique=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<RolloverState {self.marker} updated={self.updated_at}>"
