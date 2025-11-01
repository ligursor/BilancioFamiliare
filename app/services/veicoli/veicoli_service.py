"""
Servizio per la gestione dei veicoli (auto, bolli, manutenzioni)
"""
from app.services import BaseService
from app.models.Veicoli import Veicoli, AutoBolli, AutoManutenzioni
from app import db
from datetime import datetime, date
from sqlalchemy import desc, and_


class VeicoliService(BaseService):
    """Servizio per la gestione dei veicoli e relative operazioni"""
    
    # === Gestione Veicoli ===
    
    def get_all_veicoli(self, solo_attivi=False):
        """Recupera tutti i veicoli"""
        query = Veicoli.query
        if solo_attivi:
            query = query.filter(Veicoli.attivo == True)
        return query.order_by(Veicoli.targa).all()
    
    def get_veicolo_by_id(self, veicolo_id):
        """Recupera un veicolo specifico"""
        return Veicoli.query.filter(Veicoli.id == veicolo_id).first()
    
    def get_veicolo_by_targa(self, targa):
        """Recupera un veicolo per targa"""
        return Veicoli.query.filter(Veicoli.targa == targa).first()
    
    def create_veicolo(self, targa, marca=None, modello=None, anno_immatricolazione=None, 
                       km_acquisto=None, data_acquisto=None, prezzo_acquisto=None, attivo=True):
        """Crea un nuovo veicolo"""
        veicolo = Veicoli(
            targa=targa,
            marca=marca,
            modello=modello,
            anno_immatricolazione=anno_immatricolazione,
            km_acquisto=km_acquisto,
            data_acquisto=data_acquisto,
            prezzo_acquisto=prezzo_acquisto,
            attivo=attivo
        )
        db.session.add(veicolo)
        db.session.commit()
        return veicolo
    
    def update_veicolo(self, veicolo_id, **kwargs):
        """Aggiorna un veicolo"""
        veicolo = self.get_veicolo_by_id(veicolo_id)
        if not veicolo:
            return None
        
        for key, value in kwargs.items():
            if hasattr(veicolo, key):
                setattr(veicolo, key, value)
        
        db.session.commit()
        return veicolo
    
    def delete_veicolo(self, veicolo_id):
        """Elimina un veicolo (soft delete, imposta attivo=False)"""
        veicolo = self.get_veicolo_by_id(veicolo_id)
        if not veicolo:
            return False
        
        veicolo.attivo = False
        db.session.commit()
        return True
    
    # === Gestione Bolli ===
    
    def get_bolli_by_veicolo(self, veicolo_id):
        """Recupera tutti i bolli per un veicolo"""
        return AutoBolli.query.filter(
            AutoBolli.veicolo_id == veicolo_id
        ).order_by(desc(AutoBolli.data_scadenza)).all()
    
    def get_bollo_by_id(self, bollo_id):
        """Recupera un bollo specifico"""
        return AutoBolli.query.filter(AutoBolli.id == bollo_id).first()
    
    def create_bollo(self, veicolo_id, data_scadenza, importo, data_pagamento=None, note=None):
        """Crea un nuovo bollo"""
        bollo = AutoBolli(
            veicolo_id=veicolo_id,
            data_scadenza=data_scadenza,
            importo=importo,
            data_pagamento=data_pagamento,
            note=note
        )
        db.session.add(bollo)
        db.session.commit()
        return bollo
    
    def update_bollo(self, bollo_id, **kwargs):
        """Aggiorna un bollo"""
        bollo = self.get_bollo_by_id(bollo_id)
        if not bollo:
            return None
        
        for key, value in kwargs.items():
            if hasattr(bollo, key):
                setattr(bollo, key, value)
        
        db.session.commit()
        return bollo
    
    def delete_bollo(self, bollo_id):
        """Elimina un bollo"""
        bollo = self.get_bollo_by_id(bollo_id)
        if not bollo:
            return False
        
        db.session.delete(bollo)
        db.session.commit()
        return True
    
    def get_bolli_scaduti(self, data_riferimento=None):
        """Recupera bolli scaduti non ancora pagati"""
        if data_riferimento is None:
            data_riferimento = date.today()
        
        return AutoBolli.query.filter(
            and_(
                AutoBolli.data_scadenza <= data_riferimento,
                AutoBolli.data_pagamento.is_(None)
            )
        ).all()
    
    # === Gestione Manutenzioni ===
    
    def get_manutenzioni_by_veicolo(self, veicolo_id):
        """Recupera tutte le manutenzioni per un veicolo"""
        return AutoManutenzioni.query.filter(
            AutoManutenzioni.veicolo_id == veicolo_id
        ).order_by(desc(AutoManutenzioni.data)).all()
    
    def get_manutenzione_by_id(self, manutenzione_id):
        """Recupera una manutenzione specifica"""
        return AutoManutenzioni.query.filter(AutoManutenzioni.id == manutenzione_id).first()
    
    def create_manutenzione(self, veicolo_id, data, tipo, descrizione=None, 
                           importo=None, km=None, fornitore=None):
        """Crea una nuova manutenzione"""
        manutenzione = AutoManutenzioni(
            veicolo_id=veicolo_id,
            data=data,
            tipo=tipo,
            descrizione=descrizione,
            importo=importo,
            km=km,
            fornitore=fornitore
        )
        db.session.add(manutenzione)
        db.session.commit()
        return manutenzione
    
    def update_manutenzione(self, manutenzione_id, **kwargs):
        """Aggiorna una manutenzione"""
        manutenzione = self.get_manutenzione_by_id(manutenzione_id)
        if not manutenzione:
            return None
        
        for key, value in kwargs.items():
            if hasattr(manutenzione, key):
                setattr(manutenzione, key, value)
        
        db.session.commit()
        return manutenzione
    
    def delete_manutenzione(self, manutenzione_id):
        """Elimina una manutenzione"""
        manutenzione = self.get_manutenzione_by_id(manutenzione_id)
        if not manutenzione:
            return False
        
        db.session.delete(manutenzione)
        db.session.commit()
        return True
    
    def calculate_total_cost_veicolo(self, veicolo_id):
        """Calcola il costo totale di un veicolo (acquisto + bolli + manutenzioni)"""
        veicolo = self.get_veicolo_by_id(veicolo_id)
        if not veicolo:
            return 0
        
        total = float(veicolo.prezzo_acquisto or 0)
        
        # Somma bolli pagati
        bolli = self.get_bolli_by_veicolo(veicolo_id)
        total += sum(float(b.importo or 0) for b in bolli if b.data_pagamento)
        
        # Somma manutenzioni
        manutenzioni = self.get_manutenzioni_by_veicolo(veicolo_id)
        total += sum(float(m.importo or 0) for m in manutenzioni)
        
        return total
