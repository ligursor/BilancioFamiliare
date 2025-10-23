"""
monthly_budget_audit - STUB

Questa definizione è stata rimossa dal codice attivo su richiesta dell'utente
e archiviata in `_backup/obsolete/app_models_monthly_budget_audit.py`.

Se è necessario ripristinarla, recuperare il file nell'archivio e ripristinarlo
nel percorso originale, quindi applicare le migrazioni DB se necessario.
"""

def _monthly_budget_audit_removed_placeholder(*args, **kwargs):
    raise RuntimeError(
        "MonthlyBudgetAudit model è stato rimosso dal codice attivo. "
        "Vedi `_backup/obsolete/app_models_monthly_budget_audit.py` per l'implementazione originale."
    )

# Export a placeholder name so imports like `from app.models.monthly_budget_audit import MonthlyBudgetAudit`
# will still succeed at import-time (module present) but using the model will raise quickly.
class MonthlyBudgetAudit:
    def __new__(cls, *args, **kwargs):
        _monthly_budget_audit_removed_placeholder()
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
