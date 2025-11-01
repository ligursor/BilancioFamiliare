"""
Servizio per la gestione di PostePay Evolution (carta, abbonamenti e movimenti)
"""
from app.services import BaseService
from app.models.PostePayEvolution import PostePayEvolution, AbbonamentoPostePay, MovimentoPostePay
from app import db
from datetime import datetime, date
from sqlalchemy import desc, and_
from dateutil.relativedelta import relativedelta


class PostePayEvolutionService(BaseService):
    """Servizio per la gestione di PostePay Evolution"""
    
    # === Gestione Carta ===
    
    def get_carta(self):
        """Recupera l'istanza della carta PostePay Evolution"""
        return PostePayEvolution.query.first()
    
    def create_or_update_carta(self, numero_carta=None, intestatario=None, saldo=None):
        """Crea o aggiorna la carta PostePay Evolution"""
        carta = self.get_carta()
        
        if carta:
            if numero_carta is not None:
                carta.numero_carta = numero_carta
            if intestatario is not None:
                carta.intestatario = intestatario
            if saldo is not None:
                carta.saldo = saldo
        else:
            carta = PostePayEvolution(
                numero_carta=numero_carta,
                intestatario=intestatario,
                saldo=saldo or 0
            )
            db.session.add(carta)
        
        db.session.commit()
        return carta
    
    def get_saldo(self):
        """Recupera il saldo attuale"""
        carta = self.get_carta()
        return float(carta.saldo or 0) if carta else 0.0
    
    def update_saldo(self, nuovo_saldo):
        """Aggiorna il saldo della carta"""
        carta = self.get_carta()
        if not carta:
            carta = self.create_or_update_carta(saldo=nuovo_saldo)
        else:
            carta.saldo = nuovo_saldo
            db.session.commit()
        return carta
    
    # === Gestione Abbonamenti ===
    
    def get_all_abbonamenti(self, solo_attivi=False):
        """Recupera tutti gli abbonamenti PostePay"""
        query = AbbonamentoPostePay.query
        if solo_attivi:
            query = query.filter(AbbonamentoPostePay.attivo == True)
        return query.order_by(AbbonamentoPostePay.descrizione).all()
    
    def get_abbonamento_by_id(self, abbonamento_id):
        """Recupera un abbonamento specifico"""
        return AbbonamentoPostePay.query.filter(AbbonamentoPostePay.id == abbonamento_id).first()
    
    def create_abbonamento(self, descrizione, importo, giorno_addebito, categoria_id=None, attivo=True):
        """Crea un nuovo abbonamento PostePay"""
        abbonamento = AbbonamentoPostePay(
            descrizione=descrizione,
            importo=importo,
            giorno_addebito=giorno_addebito,
            categoria_id=categoria_id,
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
        """Recupera tutti i movimenti PostePay"""
        query = MovimentoPostePay.query
        
        if data_inizio:
            query = query.filter(MovimentoPostePay.data >= data_inizio)
        if data_fine:
            query = query.filter(MovimentoPostePay.data <= data_fine)
        
        return query.order_by(desc(MovimentoPostePay.data)).all()
    
    def get_movimenti_by_abbonamento(self, abbonamento_id):
        """Recupera tutti i movimenti per un abbonamento"""
        return MovimentoPostePay.query.filter(
            MovimentoPostePay.abbonamento_id == abbonamento_id
        ).order_by(desc(MovimentoPostePay.data)).all()
    
    def get_movimento_by_id(self, movimento_id):
        """Recupera un movimento specifico"""
        return MovimentoPostePay.query.filter(MovimentoPostePay.id == movimento_id).first()
    
    def get_movimento_by_abbonamento_mese(self, abbonamento_id, year, month):
        """Recupera il movimento per un abbonamento in un mese specifico"""
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        return MovimentoPostePay.query.filter(
            and_(
                MovimentoPostePay.abbonamento_id == abbonamento_id,
                MovimentoPostePay.data >= start_date,
                MovimentoPostePay.data < end_date
            )
        ).first()
    
    def create_movimento(self, data, importo, tipo, descrizione=None, 
                        abbonamento_id=None, categoria_id=None, transazione_id=None):
        """Crea un nuovo movimento PostePay"""
        movimento = MovimentoPostePay(
            data=data,
            importo=importo,
            tipo=tipo,
            descrizione=descrizione,
            abbonamento_id=abbonamento_id,
            categoria_id=categoria_id,
            transazione_id=transazione_id
        )
        db.session.add(movimento)
        
        # Aggiorna il saldo della carta
        carta = self.get_carta()
        if carta:
            if tipo == 'U':  # Uscita
                carta.saldo -= float(importo or 0)
            elif tipo == 'E':  # Entrata
                carta.saldo += float(importo or 0)
        
        db.session.commit()
        return movimento
    
    def update_movimento(self, movimento_id, **kwargs):
        """Aggiorna un movimento"""
        movimento = self.get_movimento_by_id(movimento_id)
        if not movimento:
            return None
        
        # Se cambia l'importo o il tipo, aggiorna il saldo
        old_importo = float(movimento.importo or 0)
        old_tipo = movimento.tipo
        
        for key, value in kwargs.items():
            if hasattr(movimento, key):
                setattr(movimento, key, value)
        
        # Ricalcola effetto sul saldo
        if 'importo' in kwargs or 'tipo' in kwargs:
            carta = self.get_carta()
            if carta:
                # Annulla vecchio effetto
                if old_tipo == 'U':
                    carta.saldo += old_importo
                elif old_tipo == 'E':
                    carta.saldo -= old_importo
                
                # Applica nuovo effetto
                new_importo = float(movimento.importo or 0)
                if movimento.tipo == 'U':
                    carta.saldo -= new_importo
                elif movimento.tipo == 'E':
                    carta.saldo += new_importo
        
        db.session.commit()
        return movimento
    
    def delete_movimento(self, movimento_id):
        """Elimina un movimento e aggiorna il saldo"""
        movimento = self.get_movimento_by_id(movimento_id)
        if not movimento:
            return False
        
        # Aggiorna il saldo annullando l'effetto del movimento
        carta = self.get_carta()
        if carta:
            importo = float(movimento.importo or 0)
            if movimento.tipo == 'U':  # Era un'uscita, riaggiunge il saldo
                carta.saldo += importo
            elif movimento.tipo == 'E':  # Era un'entrata, toglie il saldo
                carta.saldo -= importo
        
        db.session.delete(movimento)
        db.session.commit()
        return True
    
    def calculate_total_spesa(self, data_inizio=None, data_fine=None):
        """Calcola la spesa totale PostePay in un periodo"""
        movimenti = self.get_all_movimenti(data_inizio, data_fine)
        return sum(float(m.importo or 0) for m in movimenti if m.tipo == 'U')
