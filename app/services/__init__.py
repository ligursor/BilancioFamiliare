"""
Servizio base per la gestione della business logic
"""
from app import db
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import calendar

# Esporta le funzioni per l'import diretto
__all__ = ['BaseService', 'DateUtilsService', 'get_month_boundaries', 'get_current_month_name']

class BaseService:
    """Classe base per i servizi con metodi comuni"""
    
    def __init__(self):
        self.db = db
    
    def save(self, obj):
        """Salva un oggetto nel database"""
        try:
            self.db.session.add(obj)
            self.db.session.commit()
            return True, "Operazione completata con successo"
        except Exception as e:
            self.db.session.rollback()
            return False, str(e)
    
    def delete(self, obj):
        """Elimina un oggetto dal database"""
        try:
            self.db.session.delete(obj)
            self.db.session.commit()
            return True, "Eliminazione completata con successo"
        except Exception as e:
            self.db.session.rollback()
            return False, str(e)
    
    def update(self, obj, **kwargs):
        """Aggiorna un oggetto con i parametri forniti"""
        try:
            for key, value in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            
            obj.data_aggiornamento = datetime.utcnow()
            self.db.session.commit()
            return True, "Aggiornamento completato con successo"
        except Exception as e:
            self.db.session.rollback()
            return False, str(e)

def get_month_boundaries(date_obj, giorno_inizio=27):
    """Calcola i confini del mese personalizzato - implementazione originale da app.py"""
    if date_obj.day >= giorno_inizio:
        # Se siamo dal giorno di inizio in poi, il mese inizia da questo giorno
        start_date = date_obj.replace(day=giorno_inizio)
        if date_obj.month == 12:
            end_date = date(date_obj.year + 1, 1, giorno_inizio - 1)
        else:
            try:
                end_date = date_obj.replace(month=date_obj.month + 1, day=giorno_inizio - 1)
            except ValueError:
                # Il giorno non esiste nel mese successivo
                giorni_nel_mese = calendar.monthrange(date_obj.year, date_obj.month + 1)[1]
                end_date = date(date_obj.year, date_obj.month + 1, min(giorno_inizio - 1, giorni_nel_mese))
    else:
        # Se siamo prima del giorno di inizio, il mese è iniziato dal giorno del mese precedente
        if date_obj.month == 1:
            start_date = date(date_obj.year - 1, 12, giorno_inizio)
        else:
            start_date = date_obj.replace(month=date_obj.month - 1, day=giorno_inizio)
        end_date = date_obj.replace(day=giorno_inizio - 1)
    
    return start_date, end_date

def get_current_month_name(date_obj):
    """Ottiene il nome del mese personalizzato - implementazione originale da app.py"""
    start_date, end_date = get_month_boundaries(date_obj)
    mesi_italiani = [
        'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
        'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'
    ]
    # Usa la data di fine periodo per determinare il nome del mese
    nome_mese = mesi_italiani[end_date.month - 1]
    anno = end_date.year
    periodo = f"{start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m/%Y')}"
    return f"{nome_mese} {anno} - {periodo}"

class DateUtilsService:
    """Servizio per operazioni con le date"""
    
    @staticmethod
    def get_month_boundaries(date_obj, giorno_inizio=27):
        """Calcola i confini del mese personalizzato"""
        return get_month_boundaries(date_obj, giorno_inizio)
    
    @staticmethod
    def get_current_month_name(date_obj):
        """Restituisce il nome del mese in italiano"""
        return get_current_month_name(date_obj)
    
    @staticmethod
    def get_financial_year_months(start_date, num_months=6):
        """Genera una lista di mesi per l'anno finanziario"""
        months = []
        current_date = start_date
        
        for i in range(num_months):
            months.append({
                'inizio': current_date,
                'fine': current_date + relativedelta(months=1) - relativedelta(days=1),
                'nome': current_date.strftime('%B %Y'),
                'numero': i + 1
            })
            current_date = current_date + relativedelta(months=1)
        
        return months
