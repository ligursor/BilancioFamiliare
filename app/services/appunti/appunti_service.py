"""
Servizio per la gestione degli appunti
"""
from app.services import BaseService
from app.models.Appunti import Appunti
from app.models.Categorie import Categorie
from app.models.Transazioni import Transazioni
from app import db
from datetime import datetime, date
from sqlalchemy import desc


class AppuntiService(BaseService):
    """Servizio per la gestione degli appunti"""
    
    def get_all_appunti(self, order_by_date=True):
        """Recupera tutti gli appunti"""
        query = Appunti.query
        if order_by_date:
            query = query.order_by(desc(Appunti.data))
        return query.all()
    
    def get_appunto_by_id(self, appunto_id):
        """Recupera un appunto specifico"""
        return Appunti.query.filter(Appunti.id == appunto_id).first()
    
    def create_appunto(self, testo, importo=None, categoria_id=None, data=None):
        """Crea un nuovo appunto"""
        if data is None:
            data = date.today()
        
        appunto = Appunti(
            testo=testo,
            importo=importo,
            categoria_id=categoria_id,
            data=data
        )
        db.session.add(appunto)
        db.session.commit()
        return appunto
    
    def update_appunto(self, appunto_id, testo=None, importo=None, categoria_id=None, data=None):
        """Aggiorna un appunto esistente"""
        appunto = self.get_appunto_by_id(appunto_id)
        if not appunto:
            return None
        
        if testo is not None:
            appunto.testo = testo
        if importo is not None:
            appunto.importo = importo
        if categoria_id is not None:
            appunto.categoria_id = categoria_id
        if data is not None:
            appunto.data = data
        
        db.session.commit()
        return appunto
    
    def delete_appunto(self, appunto_id):
        """Elimina un appunto"""
        appunto = self.get_appunto_by_id(appunto_id)
        if not appunto:
            return False
        
        db.session.delete(appunto)
        db.session.commit()
        return True
    
    def convert_to_transaction(self, appunto_id):
        """Converte un appunto in una transazione"""
        appunto = self.get_appunto_by_id(appunto_id)
        if not appunto:
            return None
        
        transazione = Transazioni(
            data=appunto.data,
            descrizione=appunto.testo,
            importo=appunto.importo or 0,
            categoria_id=appunto.categoria_id,
            tipo='E' if (appunto.importo or 0) < 0 else 'U'
        )
        db.session.add(transazione)
        db.session.delete(appunto)
        db.session.commit()
        
        return transazione
