"""
Servizio per la gestione delle transazioni (spostato in app.services.bilancio)
"""
from app.services import BaseService, DateUtilsService
from app.models.transazioni import Transazione
from app.models.base import Categoria
from app import db
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from flask import current_app

class TransazioneService(BaseService):
    """Servizio per la gestione delle transazioni"""
    
    def get_transazioni_by_period(self, data_inizio, data_fine):
        """Recupera le transazioni in un periodo specifico"""
        return Transazione.query.filter(
            Transazione.data >= data_inizio,
            Transazione.data <= data_fine,
            Transazione.categoria_id.isnot(None)  # Escludi transazioni PayPal
        ).order_by(Transazione.data.desc()).all()
    
    def get_transazioni_by_categoria(self, categoria_id):
        """Recupera le transazioni per categoria"""
        return Transazione.query.filter_by(categoria_id=categoria_id).all()
    
    def get_transazioni_ricorrenti(self):
        """Recupera le transazioni ricorrenti"""
        return Transazione.query.filter_by(ricorrente=True).all()

    def get_transazioni_with_pagination(self, page=1, per_page=20, tipo_filtro=None, ordine='data_desc'):
        """Recupera transazioni con paginazione e filtri"""
        query = Transazione.query.filter(Transazione.categoria_id.isnot(None))
        
        # Applica filtro tipo se specificato
        if tipo_filtro in ['entrata', 'uscita']:
            query = query.filter(Transazione.tipo == tipo_filtro)
        
        # Applica ordinamento
        if ordine == 'data_asc':
            query = query.order_by(Transazione.data.asc(), Transazione.id.asc())
        elif ordine == 'data_desc':
            query = query.order_by(Transazione.data.desc(), Transazione.id.desc())
        elif ordine == 'importo_asc':
            query = query.order_by(Transazione.importo.asc(), Transazione.data.desc())
        elif ordine == 'importo_desc':
            query = query.order_by(Transazione.importo.desc(), Transazione.data.desc())
        else:
            # Default: data decrescente
            query = query.order_by(Transazione.data.desc(), Transazione.id.desc())
        
        return query.paginate(page=page, per_page=per_page, error_out=False)

    def get_transazioni_filtered(self, tipo_filtro=None, ordine='data_desc'):
        """Recupera tutte le transazioni applicando filtri e ordinamento, senza paginazione"""
        query = Transazione.query.filter(Transazione.categoria_id.isnot(None))

        # Applica filtro tipo se specificato
        if tipo_filtro in ['entrata', 'uscita']:
            query = query.filter(Transazione.tipo == tipo_filtro)

        # Applica ordinamento
        if ordine == 'data_asc':
            query = query.order_by(Transazione.data.asc(), Transazione.id.asc())
        elif ordine == 'data_desc':
            query = query.order_by(Transazione.data.desc(), Transazione.id.desc())
        elif ordine == 'importo_asc':
            query = query.order_by(Transazione.importo.asc(), Transazione.data.desc())
        elif ordine == 'importo_desc':
            query = query.order_by(Transazione.importo.desc(), Transazione.data.desc())
        else:
            # Default: data decrescente
            query = query.order_by(Transazione.data.desc(), Transazione.id.desc())

        return query.all()

    def calculate_saldo_by_period(self, data_inizio, data_fine):
        """Calcola entrate, uscite e saldo per un periodo"""
        transazioni = self.get_transazioni_by_period(data_inizio, data_fine)
        
        entrate = sum(t.importo for t in transazioni if t.tipo == 'entrata')
        uscite = sum(t.importo for t in transazioni if t.tipo == 'uscita')
        saldo = entrate - uscite
        
        return {
            'entrate': entrate,
            'uscite': uscite,
            'saldo': saldo,
            'num_transazioni': len(transazioni)
        }
    
    def create_transazione(self, data, descrizione, importo, categoria_id, tipo, 
                          ricorrente=False, frequenza_giorni=0, data_effettiva=None):
        """Crea una nuova transazione"""
        try:
            # Se non specificata, determina data_effettiva automaticamente
            if data_effettiva is None and data <= date.today():
                data_effettiva = data
            
            # The Transazione model no longer stores frequenza_giorni; keep the
            # frequency in the service and only persist attributes that exist on the model.
            transazione = Transazione(
                data=data,
                data_effettiva=data_effettiva,
                descrizione=descrizione,
                importo=importo,
                categoria_id=categoria_id,
                tipo=tipo,
                ricorrente=ricorrente,
            )
            
            success, message = self.save(transazione)
            
            if success and ricorrente and frequenza_giorni > 0:
                # Crea istanze future per transazioni ricorrenti
                self._create_recurring_instances(transazione, frequenza_giorni)
            
            return success, message, transazione
            
        except Exception as e:
            return False, str(e), None
    
    def _create_recurring_instances(self, transazione_madre, frequenza_giorni, num_occorrenze=12):
        """Crea le istanze future per transazioni ricorrenti"""
        try:
            for i in range(1, num_occorrenze + 1):
                data_futura = transazione_madre.data + relativedelta(days=i * frequenza_giorni)
                
                # Non creare transazioni troppo nel futuro (oltre 2 anni)
                if data_futura > date.today() + relativedelta(years=2):
                    break
                
                transazione_figlia = Transazione(
                    data=data_futura,
                    data_effettiva=None,  # Le future sono sempre programmate
                    descrizione=transazione_madre.descrizione,
                    importo=transazione_madre.importo,
                    categoria_id=transazione_madre.categoria_id,
                    tipo=transazione_madre.tipo,
                    ricorrente=False,  # Le figlie non sono ricorrenti
                    id_recurring_tx=transazione_madre.id
                )
                
                db.session.add(transazione_figlia)
            
            db.session.commit()
            return True, "Istanze ricorrenti create"
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)
    
    def mark_as_completed(self, transazione_id):
        """Segna una transazione come completata"""
        try:
            transazione = Transazione.query.get(transazione_id)
            if not transazione:
                return False, "Transazione non trovata"
            
            transazione.data_effettiva = date.today()
            success, message = self.update(transazione)
            
            return success, message
            
        except Exception as e:
            return False, str(e)

    def get_transazioni_dashboard(self, periodo_start, periodo_end, limit=10):
        """Recupera transazioni per la dashboard con filtri speciali"""
        # Ottieni tutte le transazioni del periodo
        tutte_transazioni = Transazione.query.filter(
            Transazione.data >= periodo_start,
            Transazione.data <= periodo_end,
            Transazione.categoria_id.isnot(None)  # Escludi PayPal
        ).all()
        
        # Filtra per evitare duplicazioni madri/figlie
        transazioni_filtrate = []
        for t in tutte_transazioni:
            if t.ricorrente == 0:  # Figlie e manuali: sempre incluse
                transazioni_filtrate.append(t)
            elif t.ricorrente == 1:  # Madri: includi solo se non hanno figlie nello stesso mese
                ha_figlie_stesso_mese = any(
                    f.transazione_madre_id == t.id and 
                    f.data.month == t.data.month and 
                    f.data.year == t.data.year
                    for f in tutte_transazioni if f.ricorrente == 0 and f.transazione_madre_id
                )
                if not ha_figlie_stesso_mese:
                    transazioni_filtrate.append(t)
        
        # Ordina e limita
        return sorted(transazioni_filtrate, key=lambda x: (x.data, x.id), reverse=True)[:limit]
