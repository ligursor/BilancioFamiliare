"""Service per la gestione dei conti personali di Maurizio e Antonietta"""
from datetime import datetime, date
from sqlalchemy import func, and_, desc
from app.models.ContoPersonale import ContoPersonale, ContoPersonaleMovimento as VersamentoPersonale
from app.models.ContiFinanziari import Strumento
from app.services.conti_finanziari.strumenti_service import StrumentiService
from app import db
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class ContiPersonaliService:
    """Service per i conti personali fissi (Maurizio e Antonietta)"""
    
    def __init__(self):
        pass
    
    def inizializza_conto_personale(self, nome_conto):
        """Inizializza un conto personale se non esiste (replica della funzione originale)"""
        try:
            conto = db.session.query(ContoPersonale).filter(
                ContoPersonale.nome_conto == nome_conto
            ).first()

            ss = StrumentiService()
            descr = f"Conto Personale {nome_conto}"
            # assicurati che esista lo strumento e prendi l'id
            try:
                strum = ss.ensure_strumento(descr, 'conto_personale', 0.0)
                strum_id = strum.id_conto if strum else None
            except Exception:
                strum = None
                strum_id = None

            if not conto:
                # preferisci il saldo_iniziale già presente nello Strumento (DB) se esiste;
                # altrimenti usa 0.0 come valore di fallback.
                try:
                    existing = ss.get_by_descrizione(descr)
                    default_iniziale = existing.saldo_iniziale if existing and existing.saldo_iniziale is not None else 0.0
                except Exception:
                    default_iniziale = 0.0

                try:
                    strum = ss.ensure_strumento(descr, 'conto_personale', default_iniziale)
                    strum_id = strum.id_conto if strum else None
                except Exception:
                    strum = None
                    strum_id = None

                conto = ContoPersonale(
                    nome_conto=nome_conto,
                    id_strumento=strum_id
                )
                db.session.add(conto)
                db.session.commit()
            else:
                # se esiste ma non ha id_strumento, proviamo ad associare
                if not conto.id_strumento and strum_id:
                    conto.id_strumento = strum_id
                    # opzionale: sincronizza i saldi dal record strumento se presenti
                    try:
                        # nulla da salvare nel modello conto_personale, i saldi sono gestiti dallo strumento
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
            
            return conto
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Errore nell'inizializzazione conto {nome_conto}: {e}")
            return None
    
    def get_conto_data(self, nome_conto):
        """Recupera i dati completi per un conto"""
        try:
            conto = self.inizializza_conto_personale(nome_conto)
            if not conto:
                return None, []
            
            versamenti = db.session.query(VersamentoPersonale).filter(
                VersamentoPersonale.conto_id == conto.id
            ).order_by(desc(VersamentoPersonale.data)).all()
            
            return conto, versamenti
            
        except Exception as e:
            logger.exception(f"Errore nel recupero dati conto {nome_conto}: {e}")
            return None, []
    
    def aggiungi_versamento(self, nome_conto, data, descrizione, importo):
        """Aggiunge un versamento al conto (replica della funzione originale)"""
        try:
            conto = self.inizializza_conto_personale(nome_conto)
            if not conto:
                return False, "Conto non trovato"
            # Validazione: l'importo deve essere positivo
            try:
                valore = float(importo)
            except Exception:
                return False, "Importo non valido"

            if valore <= 0:
                return False, "L'importo del versamento deve essere maggiore di 0"

            # Calcola il nuovo saldo usando lo Strumento associato come sorgente di verità
            ss = StrumentiService()
            # preferiamo usare id_strumento se presente
            if conto.id_strumento:
                strum = ss.get_by_id(conto.id_strumento)
            else:
                strum = ss.get_by_descrizione(f"Conto Personale {nome_conto}")

            current_saldo = float(strum.saldo_corrente) if strum and strum.saldo_corrente is not None else 0.0
            nuovo_saldo = current_saldo - abs(valore)

            # Crea il versamento: memorizziamo l'importo come POSITIVO (rappresenta l'ammontare versato)
            versamento = VersamentoPersonale(
                conto_id=conto.id,
                data=data,
                descrizione=descrizione,
                importo=abs(valore)  # Memorizzato positivo
            )

            db.session.add(versamento)
            db.session.commit()

            # Dopo aver aggiunto il movimento, ricalcoliamo il saldo corrente aggregando i movimenti
            try:
                # Somma degli importi per il conto (tutti i movimenti sono valori positivi)
                total = db.session.query(func.coalesce(func.sum(VersamentoPersonale.importo), 0)).filter(VersamentoPersonale.conto_id == conto.id).scalar()
                # saldo corrente = saldo_iniziale - total
                if conto.id_strumento:
                    ss.update_saldo_by_id(conto.id_strumento, (strum.saldo_iniziale if strum and strum.saldo_iniziale is not None else 0.0) - float(total))
                else:
                    ss.update_saldo(f"Conto Personale {nome_conto}", (strum.saldo_iniziale if strum and strum.saldo_iniziale is not None else 0.0) - float(total))
            except Exception as e:
                logger.warning(f"Attenzione: impossibile sincronizzare lo strumento per {nome_conto}: {e}", exc_info=True)

            return True, "Versamento aggiunto con successo"
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Errore nell'aggiunta versamento: {e}")
            return False, f"Errore nel versamento: {str(e)}"
    
    def elimina_versamento(self, versamento_id):
        """Elimina un versamento e ripristina il saldo"""
        try:
            versamento = db.session.query(VersamentoPersonale).filter(
                VersamentoPersonale.id == versamento_id
            ).first()
            
            if not versamento:
                return False, "Versamento non trovato"
            
            conto = versamento.conto
            
            # Dopo l'eliminazione, ricalcoliamo il totale dei movimenti e aggiorniamo lo strumento
            try:
                ss = StrumentiService()
                total = db.session.query(func.coalesce(func.sum(VersamentoPersonale.importo), 0)).filter(VersamentoPersonale.conto_id == conto.id).scalar()
                if conto.id_strumento:
                    s = ss.get_by_id(conto.id_strumento)
                    iniz = s.saldo_iniziale if s and s.saldo_iniziale is not None else 0.0
                    ss.update_saldo_by_id(conto.id_strumento, iniz - float(total))
                else:
                    descr = f"Conto Personale {conto.nome_conto}"
                    s = ss.get_by_descrizione(descr)
                    if s:
                        ss.update_saldo(descr, (s.saldo_iniziale or 0.0) - float(total))
            except Exception as e:
                logger.warning(f"Attenzione: impossibile sincronizzare lo strumento per {conto.nome_conto}: {e}", exc_info=True)

            # Elimina il versamento
            db.session.delete(versamento)
            db.session.commit()

            return True, "Versamento eliminato e saldo ripristinato"
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Errore nell'eliminazione versamento: {e}")
            return False, f"Errore nell'eliminazione: {str(e)}"
    
    def reset_conto(self, nome_conto):
        """Reset del conto al saldo iniziale"""
        try:
            conto = db.session.query(ContoPersonale).filter(
                ContoPersonale.nome_conto == nome_conto
            ).first()
            
            if not conto:
                return False, "Conto non trovato"
            
            # Elimina tutti i movimenti
            db.session.query(VersamentoPersonale).filter(
                VersamentoPersonale.conto_id == conto.id
            ).delete()

            # Dopo la cancellazione, il totale è zero quindi impostiamo il saldo corrente al valore iniziale
            try:
                ss = StrumentiService()
                if conto.id_strumento:
                    s = ss.get_by_id(conto.id_strumento)
                    iniz = s.saldo_iniziale if s and s.saldo_iniziale is not None else 0.0
                    ss.update_saldo_by_id(conto.id_strumento, iniz)
                else:
                    descr = f"Conto Personale {nome_conto}"
                    s = ss.get_by_descrizione(descr)
                    if s:
                        ss.update_saldo(descr, s.saldo_iniziale or 0.0)
            except Exception as e:
                logger.warning(f"Attenzione: impossibile sincronizzare lo strumento per {nome_conto}: {e}", exc_info=True)

            db.session.commit()
            return True, f"Conto di {nome_conto} resettato al saldo iniziale"
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Errore nel reset conto: {e}")
            return False, f"Errore durante il reset: {str(e)}"
    
    def aggiorna_saldo_iniziale(self, nome_conto, nuovo_saldo):
        """Aggiorna il saldo iniziale del conto"""
        try:
            conto = db.session.query(ContoPersonale).filter(
                ContoPersonale.nome_conto == nome_conto
            ).first()
            
            if not conto:
                return False, "Conto non trovato"
            
            # Aggiorniamo il saldo iniziale nello strumento corrispondente e adattiamo il saldo corrente
            try:
                ss = StrumentiService()
                if conto.id_strumento:
                    ss.update_saldo_iniziale_by_id(conto.id_strumento, nuovo_saldo)
                    # ricalcola corrente = saldo_iniziale - total_movimenti
                    total = db.session.query(func.coalesce(func.sum(VersamentoPersonale.importo), 0)).filter(VersamentoPersonale.conto_id == conto.id).scalar()
                    ss.update_saldo_by_id(conto.id_strumento, float(nuovo_saldo) - float(total))
                else:
                    descr = f"Conto Personale {nome_conto}"
                    s = ss.get_by_descrizione(descr)
                    if s:
                        ss.update_saldo_iniziale_by_id(s.id_conto, nuovo_saldo)
                        total = db.session.query(func.coalesce(func.sum(VersamentoPersonale.importo), 0)).filter(VersamentoPersonale.conto_id == conto.id).scalar()
                        ss.update_saldo_by_id(s.id_conto, float(nuovo_saldo) - float(total))
            except Exception:
                logger.warning(f"Attenzione: impossibile sincronizzare lo strumento per {nome_conto}", exc_info=True)

            return True, "Saldo iniziale aggiornato con successo"
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Errore nell'aggiornamento saldo iniziale: {e}")
            return False, f"Errore nell'aggiornamento: {str(e)}"
    
    def initialize_default_conti(self):
        """Inizializza i conti predefiniti se non esistono"""
        try:
            # Verifica e crea il conto di Maurizio
            maurizio = self.inizializza_conto_personale('Maurizio')
            
            # Verifica e crea il conto di Antonietta
            antonietta = self.inizializza_conto_personale('Antonietta')
            
            if maurizio and antonietta:
                logger.info("Conti personali di Maurizio e Antonietta inizializzati")
                return True
            
            return False
            
        except Exception as e:
            logger.exception(f"Errore nell'inizializzazione conti predefiniti: {e}")
            return False
