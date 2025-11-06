"""Servizio per la gestione di PostePay Evolution (carta, abbonamenti e movimenti)"""
from app.services import BaseService
from app.models.PostePayEvolution import AbbonamentoPostePay, MovimentoPostePay
from app import db
from datetime import datetime, date
from sqlalchemy import desc, and_
from dateutil.relativedelta import relativedelta
from types import SimpleNamespace
from app.services.conti_finanziari.strumenti_service import StrumentiService


class PostePayEvolutionService(BaseService):
    """Servizio per la gestione di PostePay Evolution"""
    
    # === Gestione Carta ===
    
    def _get_strumento(self):
        """Recupera lo Strumento 'Postepay Evolution' dai conti_finanziari (source of truth).
        """
        try:
            ss = StrumentiService()
            return ss.get_by_descrizione('Postepay Evolution')
        except Exception:
            return None
    
    def create_or_update_carta(self, numero_carta=None, intestatario=None, saldo=None):
        """Crea o aggiorna la carta PostePay Evolution"""
        # Update (or create) the Strumento that holds the saldo. We no longer touch any legacy model.
        try:
            ss = StrumentiService()
            if saldo is not None:
                strum = ss.update_saldo('Postepay Evolution', saldo)
            else:
                # Ensure strumento exists even if saldo not provided
                strum = ss.ensure_strumento('Postepay Evolution', 'carta', 0.0)
            return strum
        except Exception:
            return None
    
    def get_saldo(self):
        """Recupera il saldo attuale"""
        strum = self._get_strumento()
        try:
            return float(getattr(strum, 'saldo_corrente', 0.0) or 0.0)
        except Exception:
            return 0.0
    
    def update_saldo(self, nuovo_saldo):
        """Aggiorna il saldo della carta"""
        try:
            ss = StrumentiService()
            return ss.update_saldo('Postepay Evolution', nuovo_saldo)
        except Exception:
            return None
    
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
                        abbonamento_id=None, categoria_id=None):
        """Crea un nuovo movimento PostePay.

        Note: Movimenti PostePay sono indipendenti dalla tabella `transazioni`.
        Non impostare o salvare un campo `transazione_id` qui.
        """
        movimento = MovimentoPostePay(
            data=data,
            importo=importo,
            tipo=tipo,
            descrizione=descrizione,
            abbonamento_id=abbonamento_id,
            categoria_id=categoria_id
        )
        db.session.add(movimento)
        # Persistiamo il movimento e aggiorniamo lo Strumento (source of truth)
        try:
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            raise

        # Aggiorna saldo nello strumento: importo è già con segno (+ entrata, - uscita)
        try:
            ss = StrumentiService()
            strum = ss.get_by_descrizione('Postepay Evolution')
            if strum:
                new_bal = (strum.saldo_corrente or 0.0) + float(movimento.importo or 0)
                ss.update_saldo_by_id(strum.id_conto, new_bal)
        except Exception:
            pass

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
        
        # Ricalcola effetto sul saldo usando lo Strumento come source of truth
        if 'importo' in kwargs or 'tipo' in kwargs:
            try:
                ss = StrumentiService()
                strum = ss.get_by_descrizione('Postepay Evolution')
                if strum:
                    new_importo = float(movimento.importo or 0)
                    # delta to apply to the strumento is new - old
                    delta = new_importo - old_importo
                    new_bal = (strum.saldo_corrente or 0.0) + delta
                    ss.update_saldo_by_id(strum.id_conto, new_bal)
            except Exception:
                pass
        
        db.session.commit()
        return movimento
    
    def delete_movimento(self, movimento_id):
        """Elimina un movimento e aggiorna il saldo"""
        movimento = self.get_movimento_by_id(movimento_id)
        if not movimento:
            return False
        # Aggiorna il saldo annullando l'effetto del movimento sullo Strumento
        try:
            ss = StrumentiService()
            strum = ss.get_by_descrizione('Postepay Evolution')
            if strum:
                # remove movimento effect: subtract movimento.importo
                new_bal = (strum.saldo_corrente or 0.0) - float(movimento.importo or 0)
                ss.update_saldo_by_id(strum.id_conto, new_bal)
        except Exception:
            pass

        db.session.delete(movimento)
        db.session.commit()
        return True
    
    def calculate_total_spesa(self, data_inizio=None, data_fine=None):
        """Calcola la spesa totale PostePay in un periodo"""
        movimenti = self.get_all_movimenti(data_inizio, data_fine)
        return sum(float(m.importo or 0) for m in movimenti if m.tipo == 'U')
