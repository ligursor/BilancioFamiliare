"""Servizio per la gestione del Libretto Smart"""
from app import db
from app.models.Libretto import Libretto
from app.models.Supersmart import Supersmart
from datetime import datetime, date


class LibrettoService:
    """Servizio per gestire le operazioni sul Libretto Smart"""
    
    def get_libretto(self):
        """Recupera il libretto (assumiamo ce ne sia uno solo)"""
        return Libretto.query.first()
    
    def get_or_create_libretto(self, identificativo='LIBRETTO-SMART-001', intestatari='Roberto Ligurso'):
        """Recupera o crea il libretto se non esiste"""
        libretto = self.get_libretto()
        if not libretto:
            libretto = Libretto(
                identificativo=identificativo,
                intestatari=intestatari,
                saldo_disponibile=0.0
            )
            db.session.add(libretto)
            db.session.commit()
        return libretto
    
    def aggiorna_saldo(self, libretto_id, nuovo_saldo):
        """Aggiorna il saldo disponibile del libretto"""
        libretto = Libretto.query.get(libretto_id)
        if not libretto:
            raise ValueError(f"Libretto con id {libretto_id} non trovato")
        
        libretto.saldo_disponibile = float(nuovo_saldo)
        libretto.data_aggiornamento = datetime.utcnow()
        db.session.commit()
        return libretto
    
    def get_depositi(self, libretto_id, solo_attivi=False):
        """Recupera i depositi del libretto"""
        query = Supersmart.query.filter_by(libretto_id=libretto_id)
        
        if solo_attivi:
            oggi = date.today()
            query = query.filter(Supersmart.data_scadenza >= oggi)
        
        return query.order_by(Supersmart.data_scadenza.desc()).all()
    
    def crea_deposito(self, libretto_id, descrizione, data_attivazione, data_scadenza, 
                      tasso, deposito, netto):
        """Crea un nuovo deposito Supersmart"""
        deposito_obj = Supersmart(
            libretto_id=libretto_id,
            descrizione=descrizione,
            data_attivazione=data_attivazione,
            data_scadenza=data_scadenza,
            tasso=float(tasso),
            deposito=float(deposito),
            netto=float(netto)
        )
        db.session.add(deposito_obj)
        db.session.commit()
        return deposito_obj
    
    def aggiorna_deposito(self, deposito_id, descrizione=None, data_attivazione=None,
                         data_scadenza=None, tasso=None, deposito=None, netto=None):
        """Aggiorna un deposito esistente"""
        deposito_obj = Supersmart.query.get(deposito_id)
        if not deposito_obj:
            raise ValueError(f"Deposito con id {deposito_id} non trovato")
        
        if descrizione is not None:
            deposito_obj.descrizione = descrizione
        if data_attivazione is not None:
            deposito_obj.data_attivazione = data_attivazione
        if data_scadenza is not None:
            deposito_obj.data_scadenza = data_scadenza
        if tasso is not None:
            deposito_obj.tasso = float(tasso)
        if deposito is not None:
            deposito_obj.deposito = float(deposito)
        if netto is not None:
            deposito_obj.netto = float(netto)
        
        deposito_obj.data_aggiornamento = datetime.utcnow()
        db.session.commit()
        return deposito_obj
    
    def elimina_deposito(self, deposito_id):
        """Elimina un deposito"""
        deposito_obj = Supersmart.query.get(deposito_id)
        if not deposito_obj:
            raise ValueError(f"Deposito con id {deposito_id} non trovato")
        
        db.session.delete(deposito_obj)
        db.session.commit()
        return True
    
    def get_statistiche(self, libretto_id):
        """Calcola statistiche sui depositi"""
        depositi = self.get_depositi(libretto_id)
        depositi_attivi = self.get_depositi(libretto_id, solo_attivi=True)
        
        totale_depositato_attivo = sum(d.deposito for d in depositi_attivi)
        totale_netto_attivo = sum(d.netto for d in depositi_attivi)
        totale_depositato_storico = sum(d.deposito for d in depositi)
        totale_netto_storico = sum(d.netto for d in depositi)
        
        return {
            'numero_depositi_attivi': len(depositi_attivi),
            'numero_depositi_totali': len(depositi),
            'totale_depositato_attivo': totale_depositato_attivo,
            'totale_netto_attivo': totale_netto_attivo,
            'totale_a_scadenza_attivo': totale_depositato_attivo + totale_netto_attivo,
            'totale_depositato_storico': totale_depositato_storico,
            'totale_netto_storico': totale_netto_storico,
        }
