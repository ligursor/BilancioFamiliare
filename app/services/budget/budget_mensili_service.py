"""Servizio per la gestione dei budget mensili"""
from app.services import BaseService
from app.models.BudgetMensili import BudgetMensili
from app.models.Budget import Budget
from app.models.Categorie import Categorie
from app import db
from datetime import datetime, date
from sqlalchemy import and_
from app.models.SaldiMensili import SaldiMensili


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
        # Do not populate budgets for a month that was explicitly seeded by a reset
        try:
            seed = SaldiMensili.query.filter_by(year=year, month=month).first()
            if seed and getattr(seed, 'is_seed', False) is True:
                return 0
        except Exception:
            # If anything goes wrong while checking seed, fall back to normal behavior
            pass
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
    
    def update_residuo_mensile(self, categoria_id, year, month, spese_effettuate, spese_pianificate):
        """Aggiorna il residuo_mensile per una categoria in un mese specifico
        
        Args:
            categoria_id: ID della categoria
            year: Anno
            month: Mese
            spese_effettuate: Totale spese già effettuate
            spese_pianificate: Totale spese pianificate (future)
            
        Returns:
            Il residuo calcolato (importo - spese_effettuate - spese_pianificate)
        """
        budget = self.get_budget_by_categoria_mese(categoria_id, year, month)
        if not budget:
            return 0.0
        
        residuo = float(budget.importo or 0) - float(spese_effettuate or 0) - float(spese_pianificate or 0)
        budget.residuo_mensile = residuo
        db.session.commit()
        return residuo
    
    def calculate_and_save_all_residui(self, year, month, budget_items):
        """Calcola e salva i residui mensili per tutti i budget del mese
        
        Args:
            year: Anno
            month: Mese
            budget_items: Lista di dict con struttura {'categoria_id', 'iniziale', 'spese_effettuate', 'spese_pianificate', 'residuo'}
            
        Returns:
            Totale dei residui calcolati
        """
        total_residui = 0.0
        
        for item in budget_items:
            categoria_id = item.get('categoria_id')
            if not categoria_id:
                continue
            
            spese_effettuate = float(item.get('spese_effettuate', 0) or 0)
            spese_pianificate = float(item.get('spese_pianificate', 0) or 0)
            
            residuo = self.update_residuo_mensile(categoria_id, year, month, spese_effettuate, spese_pianificate)
            total_residui += residuo
        
        return total_residui
    
    def get_total_residui_mese(self, year, month):
        """Calcola il totale dei residui mensili per un mese
        
        Returns:
            Somma di tutti i residui_mensili del mese specificato
        """
        budgets = self.get_budget_mese(year, month)
        return sum(float(b.residuo_mensile or 0) for b in budgets)
