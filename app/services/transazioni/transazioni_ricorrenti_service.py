"""
Service per la gestione delle transazioni ricorrenti.
Fornisce operazioni CRUD complete per TransazioniRicorrenti.
"""
from app import db
from app.models.TransazioniRicorrenti import TransazioniRicorrenti
from app.models.Categorie import Categorie
from datetime import date, datetime
from typing import List, Tuple, Optional


class TransazioniRicorrentiService:
    """Service per gestire le transazioni ricorrenti"""
    
    def get_all(self) -> List[TransazioniRicorrenti]:
        """
        Recupera tutte le transazioni ricorrenti
        
        Returns:
            Lista di TransazioniRicorrenti
        """
        return TransazioniRicorrenti.query.order_by(
            TransazioniRicorrenti.giorno.asc(), 
            TransazioniRicorrenti.descrizione.asc()
        ).all()
    
    def get_by_id(self, ricorrente_id: int) -> Optional[TransazioniRicorrenti]:
        """
        Recupera una transazione ricorrente per ID
        
        Args:
            ricorrente_id: ID della transazione ricorrente
            
        Returns:
            TransazioniRicorrenti o None
        """
        return TransazioniRicorrenti.query.get(ricorrente_id)
    
    def get_by_categoria(self, categoria_id: int) -> List[TransazioniRicorrenti]:
        """
        Recupera tutte le transazioni ricorrenti di una categoria
        
        Args:
            categoria_id: ID della categoria
            
        Returns:
            Lista di TransazioniRicorrenti
        """
        return TransazioniRicorrenti.query.filter_by(categoria_id=categoria_id).all()
    
    def create(self, descrizione: str, importo: float, tipo: str, giorno: int = 1,
               categoria_id: int = None, cadenza: str = 'mensile',
               skip_month_if_annual: bool = False) -> Tuple[bool, str, Optional[TransazioniRicorrenti]]:
        """
        Crea una nuova transazione ricorrente
        
        Args:
            descrizione: Descrizione della transazione
            importo: Importo (positivo per entrate, negativo per uscite)
            tipo: 'entrata' o 'uscita'
            giorno: Giorno del mese (1-31)
            categoria_id: ID della categoria (opzionale)
            cadenza: Cadenza ('mensile', 'annuale', ecc.)
            skip_month_if_annual: Salta se esiste ricorrenza annuale
            
        Returns:
            Tuple (success: bool, message: str, ricorrente: TransazioniRicorrenti)
        """
        try:
            # Validazioni
            if not descrizione or not descrizione.strip():
                return False, "La descrizione è obbligatoria", None
            
            if tipo not in ['entrata', 'uscita']:
                return False, "Il tipo deve essere 'entrata' o 'uscita'", None
            
            if giorno < 1 or giorno > 31:
                return False, "Il giorno deve essere tra 1 e 31", None
            
            if categoria_id:
                categoria = Categorie.query.get(categoria_id)
                if not categoria:
                    return False, f"Categoria con ID {categoria_id} non trovata", None
            
            # Crea la transazione ricorrente
            ricorrente = TransazioniRicorrenti(
                descrizione=descrizione.strip(),
                importo=float(importo),
                tipo=tipo,
                giorno=giorno,
                categoria_id=categoria_id,
                cadenza=cadenza,
                skip_month_if_annual=1 if skip_month_if_annual else 0
            )
            
            db.session.add(ricorrente)
            db.session.commit()
            
            return True, "Transazione ricorrente creata con successo", ricorrente
            
        except Exception as e:
            db.session.rollback()
            return False, f"Errore durante la creazione: {str(e)}", None
    
    def update(self, ricorrente_id: int, descrizione: str = None, importo: float = None,
               tipo: str = None, giorno: int = None, categoria_id: int = None,
               cadenza: str = None, skip_month_if_annual: bool = None) -> Tuple[bool, str]:
        """
        Aggiorna una transazione ricorrente esistente
        
        Args:
            ricorrente_id: ID della transazione ricorrente da aggiornare
            Altri parametri opzionali da aggiornare
            
        Returns:
            Tuple (success: bool, message: str)
        """
        try:
            ricorrente = TransazioniRicorrenti.query.get(ricorrente_id)
            if not ricorrente:
                return False, "Transazione ricorrente non trovata"
            
            # Aggiorna i campi forniti
            if descrizione is not None:
                if not descrizione.strip():
                    return False, "La descrizione non può essere vuota"
                ricorrente.descrizione = descrizione.strip()
            
            if importo is not None:
                ricorrente.importo = float(importo)
            
            if tipo is not None:
                if tipo not in ['entrata', 'uscita']:
                    return False, "Il tipo deve essere 'entrata' o 'uscita'"
                ricorrente.tipo = tipo
            
            if giorno is not None:
                if giorno < 1 or giorno > 31:
                    return False, "Il giorno deve essere tra 1 e 31"
                ricorrente.giorno = giorno
            
            if categoria_id is not None:
                if categoria_id > 0:
                    categoria = Categorie.query.get(categoria_id)
                    if not categoria:
                        return False, f"Categoria con ID {categoria_id} non trovata"
                    ricorrente.categoria_id = categoria_id
                else:
                    ricorrente.categoria_id = None
            
            if cadenza is not None:
                ricorrente.cadenza = cadenza
            
            if skip_month_if_annual is not None:
                ricorrente.skip_month_if_annual = 1 if skip_month_if_annual else 0
            
            db.session.commit()
            return True, "Transazione ricorrente aggiornata con successo"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Errore durante l'aggiornamento: {str(e)}"
    
    def delete(self, ricorrente_id: int) -> Tuple[bool, str]:
        """
        Elimina una transazione ricorrente
        
        Args:
            ricorrente_id: ID della transazione ricorrente da eliminare
            
        Returns:
            Tuple (success: bool, message: str)
        """
        try:
            ricorrente = TransazioniRicorrenti.query.get(ricorrente_id)
            if not ricorrente:
                return False, "Transazione ricorrente non trovata"
            
            descrizione = ricorrente.descrizione
            db.session.delete(ricorrente)
            db.session.commit()
            
            return True, f"Transazione ricorrente '{descrizione}' eliminata con successo"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Errore durante l'eliminazione: {str(e)}"
    
    def get_stats(self) -> dict:
        """
        Restituisce statistiche sulle transazioni ricorrenti
        
        Returns:
            Dict con statistiche
        """
        try:
            totale = TransazioniRicorrenti.query.count()
            entrate = TransazioniRicorrenti.query.filter_by(tipo='entrata').all()
            uscite = TransazioniRicorrenti.query.filter_by(tipo='uscita').all()
            
            totale_entrate = sum(r.importo for r in entrate)
            totale_uscite = sum(r.importo for r in uscite)
            
            return {
                'totale': totale,
                'num_entrate': len(entrate),
                'num_uscite': len(uscite),
                'importo_entrate': totale_entrate,
                'importo_uscite': totale_uscite,
                'saldo_mensile': totale_entrate - totale_uscite
            }
        except Exception as e:
            return {
                'error': str(e)
            }
