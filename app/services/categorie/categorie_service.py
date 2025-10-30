"""
Servizio per la gestione delle categorie
"""
from app.services import BaseService
from app.models.base import Categoria
from app import db

class CategorieService(BaseService):
    """Servizio per la gestione delle categorie"""
    
    def get_all_categories(self, exclude_paypal=True):
        """Recupera tutte le categorie"""
        if exclude_paypal:
            return Categoria.query.filter(Categoria.nome != 'PayPal').all()
        return Categoria.query.all()
    
    def get_categories_dict(self, exclude_paypal=True):
        """Recupera categorie come dizionario per i template"""
        categorie = self.get_all_categories(exclude_paypal)
        return [{'id': c.id, 'nome': c.nome, 'tipo': c.tipo} for c in categorie]
    
    def get_categories_by_type(self, tipo):
        """Recupera categorie per tipo (entrata/uscita)"""
        return Categoria.query.filter_by(tipo=tipo).filter(Categoria.nome != 'PayPal').all()
    
    def create_categoria(self, nome, tipo):
        """Crea una nuova categoria"""
        try:
            # Verifica che non esista già
            existing = Categoria.query.filter_by(nome=nome).first()
            if existing:
                return False, f"Categoria '{nome}' già esistente"
            
            categoria = Categoria(nome=nome, tipo=tipo)
            success, message = self.save(categoria)
            
            return success, message if not success else f"Categoria '{nome}' creata con successo"
            
        except Exception as e:
            return False, str(e)
    
    def update_categoria(self, categoria_id, nome=None, tipo=None):
        """Aggiorna una categoria esistente"""
        try:
            categoria = Categoria.query.get(categoria_id)
            if not categoria:
                return False, "Categoria non trovata"
            
            # Verifica che non sia PayPal (categoria speciale)
            if categoria.nome == 'PayPal':
                return False, "Non è possibile modificare la categoria PayPal"
            
            if nome and nome != categoria.nome:
                # Verifica che il nuovo nome non esista già
                existing = Categoria.query.filter_by(nome=nome).first()
                if existing and existing.id != categoria.id:
                    return False, f"Categoria '{nome}' già esistente"
                categoria.nome = nome
            
            if tipo and tipo != categoria.tipo:
                categoria.tipo = tipo
            
            success, message = self.update(categoria)
            return success, message if not success else f"Categoria aggiornata con successo"
            
        except Exception as e:
            return False, str(e)
    
    def delete_categoria(self, categoria_id):
        """Elimina una categoria"""
        try:
            categoria = Categoria.query.get(categoria_id)
            if not categoria:
                return False, "Categoria non trovata"
            
            # Verifica che non sia PayPal (categoria speciale)
            if categoria.nome == 'PayPal':
                return False, "Non è possibile eliminare la categoria PayPal"
            
            # Verifica che non ci siano transazioni associate
            if categoria.transazioni:
                return False, f"Impossibile eliminare la categoria '{categoria.nome}': ci sono {len(categoria.transazioni)} transazioni associate"
            
            nome = categoria.nome
            success, message = self.delete(categoria)
            
            return success, message if not success else f"Categoria '{nome}' eliminata con successo"
            
        except Exception as e:
            return False, str(e)
    
    def get_categories_stats(self):
        """Calcola statistiche delle categorie"""
        try:
            categorie = self.get_all_categories()
            stats = []
            
            for categoria in categorie:
                num_transazioni = len(categoria.transazioni) if categoria.transazioni else 0
                stats.append({
                    'categoria': categoria,
                    'num_transazioni': num_transazioni
                })
            
            return stats
            
        except Exception as e:
            return []
