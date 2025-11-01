"""
Servizio per la gestione di PayPal (abbonamenti e movimenti)
"""
from app.services import BaseService
from app.models.Paypal import PaypalAbbonamenti, PaypalMovimenti
from app import db
from datetime import datetime, date
from sqlalchemy import desc, and_
from dateutil.relativedelta import relativedelta


class PaypalService(BaseService):
    """Servizio per la gestione di PayPal"""
    
    # === Gestione Abbonamenti ===
    
    def get_all_abbonamenti(self, solo_attivi=False):
        """Recupera tutti gli abbonamenti PayPal"""
        query = PaypalAbbonamenti.query
        if solo_attivi:
            query = query.filter(PaypalAbbonamenti.attivo == True)
        return query.order_by(PaypalAbbonamenti.descrizione).all()
    
    def get_abbonamento_by_id(self, abbonamento_id):
        """Recupera un abbonamento specifico"""
        return PaypalAbbonamenti.query.filter(PaypalAbbonamenti.id == abbonamento_id).first()
    
    def create_abbonamento(self, descrizione, importo, giorno_addebito, attivo=True):
        """Crea un nuovo abbonamento PayPal"""
        abbonamento = PaypalAbbonamenti(
            descrizione=descrizione,
            importo=importo,
            giorno_addebito=giorno_addebito,
            attivo=attivo
        )
        db.session.add(abbonamento)
        db.session.commit()
        return abbonamento
    
    def update_abbonamento(self, abbonamento_id, **kwargs):
        """Aggiorna un abbonamento"""
        abbonamento = self.get_abbonamento_by_id(abbonamento_id)
        if not abbonamento:
            return None
        
        for key, value in kwargs.items():
            if hasattr(abbonamento, key):
                setattr(abbonamento, key, value)
        
        db.session.commit()
        return abbonamento
    
    def delete_abbonamento(self, abbonamento_id):
        """Elimina un abbonamento (soft delete)"""
        abbonamento = self.get_abbonamento_by_id(abbonamento_id)
        if not abbonamento:
            return False
        
        abbonamento.attivo = False
        db.session.commit()
        return True
    
    def get_abbonamenti_scaduti(self, data_riferimento=None):
        """Recupera abbonamenti con scadenze passate non ancora pagate"""
        if data_riferimento is None:
            data_riferimento = date.today()
        
        abbonamenti_attivi = self.get_all_abbonamenti(solo_attivi=True)
        scaduti = []
        
        for abb in abbonamenti_attivi:
            # Calcola data scadenza
            year = data_riferimento.year
            month = data_riferimento.month
            giorno = min(abb.giorno_addebito, 28)  # Sicurezza per febbraio
            
            try:
                data_scadenza = date(year, month, giorno)
            except ValueError:
                data_scadenza = date(year, month, 28)
            
            if data_scadenza <= data_riferimento:
                # Verifica se esiste movimento per questo mese
                movimento = self.get_movimento_by_abbonamento_mese(abb.id, year, month)
                if not movimento:
                    scaduti.append(abb)
        
        return scaduti
    
    # === Gestione Movimenti ===
    
    def get_all_movimenti(self, data_inizio=None, data_fine=None):
        """Recupera tutti i movimenti PayPal"""
        query = PaypalMovimenti.query
        
        if data_inizio:
            query = query.filter(PaypalMovimenti.data >= data_inizio)
        if data_fine:
            query = query.filter(PaypalMovimenti.data <= data_fine)
        
        return query.order_by(desc(PaypalMovimenti.data)).all()
    
    def get_movimenti_by_abbonamento(self, abbonamento_id):
        """Recupera tutti i movimenti per un abbonamento"""
        return PaypalMovimenti.query.filter(
            PaypalMovimenti.abbonamento_id == abbonamento_id
        ).order_by(desc(PaypalMovimenti.data)).all()
    
    def get_movimento_by_id(self, movimento_id):
        """Recupera un movimento specifico"""
        return PaypalMovimenti.query.filter(PaypalMovimenti.id == movimento_id).first()
    
    def get_movimento_by_abbonamento_mese(self, abbonamento_id, year, month):
        """Recupera il movimento per un abbonamento in un mese specifico"""
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        return PaypalMovimenti.query.filter(
            and_(
                PaypalMovimenti.abbonamento_id == abbonamento_id,
                PaypalMovimenti.data >= start_date,
                PaypalMovimenti.data < end_date
            )
        ).first()
    
    def create_movimento(self, abbonamento_id, data, importo, descrizione=None, transazione_id=None):
        """Crea un nuovo movimento PayPal"""
        movimento = PaypalMovimenti(
            abbonamento_id=abbonamento_id,
            data=data,
            importo=importo,
            descrizione=descrizione,
            transazione_id=transazione_id
        )
        db.session.add(movimento)
        db.session.commit()
        return movimento
    
    def update_movimento(self, movimento_id, **kwargs):
        """Aggiorna un movimento"""
        movimento = self.get_movimento_by_id(movimento_id)
        if not movimento:
            return None
        
        for key, value in kwargs.items():
            if hasattr(movimento, key):
                setattr(movimento, key, value)
        
        db.session.commit()
        return movimento
    
    def delete_movimento(self, movimento_id):
        """Elimina un movimento"""
        movimento = self.get_movimento_by_id(movimento_id)
        if not movimento:
            return False
        
        db.session.delete(movimento)
        db.session.commit()
        return True
    
    def calculate_total_spesa(self, data_inizio=None, data_fine=None):
        """Calcola la spesa totale PayPal in un periodo"""
        movimenti = self.get_all_movimenti(data_inizio, data_fine)
        return sum(float(m.importo or 0) for m in movimenti)
