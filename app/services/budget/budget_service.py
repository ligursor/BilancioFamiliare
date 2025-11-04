"""Servizio per la gestione del budget"""
from app.services import BaseService
from app.models.Budget import Budget
from app.models.Categorie import Categorie
from app import db
from datetime import datetime


class BudgetService(BaseService):
    """Servizio per la gestione del budget"""
    
    def get_all_budgets(self):
        """Recupera tutti i budget"""
        return Budget.query.order_by(Budget.categoria_id).all()
    
    def get_budget_by_categoria(self, categoria_id):
        """Recupera il budget per una categoria specifica"""
        return Budget.query.filter(Budget.categoria_id == categoria_id).first()
    
    def get_budgets_dict(self):
        """Recupera i budget come dizionario {categoria_id: importo}"""
        budgets = self.get_all_budgets()
        return {b.categoria_id: float(b.importo or 0) for b in budgets}
    
    def create_or_update_budget(self, categoria_id, importo):
        """Crea o aggiorna un budget per una categoria"""
        budget = self.get_budget_by_categoria(categoria_id)
        
        if budget:
            budget.importo = importo
        else:
            budget = Budget(
                categoria_id=categoria_id,
                importo=importo
            )
            db.session.add(budget)
        
        db.session.commit()
        return budget
    
    def delete_budget(self, categoria_id):
        """Elimina un budget"""
        budget = self.get_budget_by_categoria(categoria_id)
        if not budget:
            return False
        
        db.session.delete(budget)
        db.session.commit()
        return True
    
    def get_budget_with_categoria(self):
        """Recupera i budget con le informazioni delle categorie"""
        budgets = db.session.query(Budget, Categorie).join(
            Categorie, Budget.categoria_id == Categorie.id
        ).all()
        
        result = []
        for budget, categoria in budgets:
            result.append({
                'categoria_id': categoria.id,
                'categoria_nome': categoria.nome,
                'categoria_tipo': categoria.tipo,
                'importo': float(budget.importo or 0)
            })
        
        return result
    
    def calculate_total_budget(self):
        """Calcola il budget totale"""
        budgets = self.get_all_budgets()
        return sum(float(b.importo or 0) for b in budgets)
