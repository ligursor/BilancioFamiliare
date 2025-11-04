"""Servizio per la gestione dei budget mensili"""
from app.services import BaseService
from app.models.BudgetMensili import BudgetMensili
from app.models.Budget import Budget
from app.models.Categorie import Categorie
from app import db
from datetime import datetime, date
from sqlalchemy import and_


class BudgetMensiliService(BaseService):
    """Servizio per la gestione dei budget mensili"""
    
    def get_budget_mese(self, year, month):
        """Recupera tutti i budget per un mese specifico"""
        return BudgetMensili.query.filter(
            and_(
                BudgetMensili.year == year,
                BudgetMensili.month == month
            )
        ).all()
    
    def get_budget_by_categoria_mese(self, categoria_id, year, month):
        """Recupera il budget per una categoria in un mese specifico"""
        return BudgetMensili.query.filter(
            and_(
                BudgetMensili.categoria_id == categoria_id,
                BudgetMensili.year == year,
                BudgetMensili.month == month
            )
        ).first()
    
    def create_or_update_budget_mese(self, categoria_id, year, month, importo, residuo_precedente=None):
        """Crea o aggiorna un budget mensile"""
        budget = self.get_budget_by_categoria_mese(categoria_id, year, month)
        
        if budget:
            budget.importo = importo
            if residuo_precedente is not None:
                budget.residuo_precedente = residuo_precedente
        else:
            budget = BudgetMensili(
                categoria_id=categoria_id,
                year=year,
                month=month,
                importo=importo,
                residuo_precedente=residuo_precedente or 0
            )
            db.session.add(budget)
        
        db.session.commit()
        return budget
    
    def populate_month_from_base_budget(self, year, month):
        """Popola i budget mensili da quelli base"""
        # Recupera tutti i budget base
        budgets_base = Budget.query.all()
        
        created = 0
        for budget_base in budgets_base:
            # Verifica se esiste già
            existing = self.get_budget_by_categoria_mese(budget_base.categoria_id, year, month)
            if not existing:
                self.create_or_update_budget_mese(
                    categoria_id=budget_base.categoria_id,
                    year=year,
                    month=month,
                    importo=budget_base.importo,
                    residuo_precedente=0
                )
                created += 1
        
        return created
    
    def get_budgets_dict_for_month(self, year, month):
        """Recupera i budget mensili come dizionario {categoria_id: importo}"""
        budgets = self.get_budget_mese(year, month)
        return {b.categoria_id: float(b.importo or 0) for b in budgets}
    
    def delete_budget_mese(self, categoria_id, year, month):
        """Elimina un budget mensile"""
        budget = self.get_budget_by_categoria_mese(categoria_id, year, month)
        if not budget:
            return False
        
        db.session.delete(budget)
        db.session.commit()
        return True
    
    def calculate_total_budget_month(self, year, month):
        """Calcola il budget totale per un mese"""
        budgets = self.get_budget_mese(year, month)
        return sum(float(b.importo or 0) for b in budgets)
