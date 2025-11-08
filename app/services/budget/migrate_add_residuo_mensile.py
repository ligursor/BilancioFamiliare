"""Migration script to add residuo_mensile column to budget_mensili table"""
from app import db
from sqlalchemy import text


def add_residuo_mensile_column():
    """Add residuo_mensile column to budget_mensili table if it doesn't exist"""
    try:
        # Check if column exists
        cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('budget_mensili');")).fetchall()]
        
        if 'residuo_mensile' not in cols:
            # Add the column
            db.session.execute(text("ALTER TABLE budget_mensili ADD COLUMN residuo_mensile REAL DEFAULT 0.0"))
            db.session.commit()
            return True, "Colonna residuo_mensile aggiunta con successo"
        else:
            return True, "Colonna residuo_mensile già presente"
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return False, f"Errore durante la migrazione: {str(e)}"
