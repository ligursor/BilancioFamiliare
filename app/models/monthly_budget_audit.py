from app import db
from datetime import datetime


class MonthlyBudgetAudit(db.Model):
    __tablename__ = 'monthly_budget_audit'

    id = db.Column(db.Integer, primary_key=True)
    monthly_budget_id = db.Column(db.Integer, nullable=True)
    categoria_id = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    old_importo = db.Column(db.Float, nullable=True)
    new_importo = db.Column(db.Float, nullable=True)
    changed_by = db.Column(db.String(128), nullable=True)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<MonthlyBudgetAudit cat={self.categoria_id} {self.year}-{self.month} {self.old_importo}->{self.new_importo} at={self.changed_at}>"
