"""
Service per la gestione dei conti personali di Maurizio e Antonietta
Replica l'implementazione originale con i due conti fissi
"""
from datetime import datetime, date
from sqlalchemy import func, and_, desc
from app.models.conti_personali import ContoPersonale, VersamentoPersonale
from app import db
from flask import current_app

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
            
            if not conto:
                if nome_conto == 'Maurizio':
                    saldo_iniziale = current_app.config['CONTO_MAURIZIO_SALDO_INIZIALE']
                else:  # Antonietta
                    saldo_iniziale = current_app.config['CONTO_ANTONIETTA_SALDO_INIZIALE']
                
                conto = ContoPersonale(
                    nome_conto=nome_conto,
                    saldo_iniziale=saldo_iniziale,
                    saldo_corrente=saldo_iniziale
                )
                db.session.add(conto)
                db.session.commit()
            
            return conto
            
        except Exception as e:
            db.session.rollback()
            print(f"Errore nell'inizializzazione conto {nome_conto}: {e}")
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
            print(f"Errore nel recupero dati conto {nome_conto}: {e}")
            return None, []
    
    def aggiungi_versamento(self, nome_conto, data, descrizione, importo):
        """Aggiunge un versamento al conto (replica della funzione originale)"""
        try:
            conto = self.inizializza_conto_personale(nome_conto)
            if not conto:
                return False, "Conto non trovato"
            
            # Calcola il nuovo saldo (sottrae l'importo perché è un versamento/uscita)
            nuovo_saldo = conto.saldo_corrente - abs(importo)
            
            # Crea il versamento
            versamento = VersamentoPersonale(
                conto_id=conto.id,
                data=data,
                descrizione=descrizione,
                importo=-abs(importo),  # Sempre negativo per i versamenti
                saldo_dopo_versamento=nuovo_saldo
            )
            
            # Aggiorna il saldo del conto
            conto.saldo_corrente = nuovo_saldo
            
            db.session.add(versamento)
            db.session.commit()
            
            return True, "Versamento aggiunto con successo"
            
        except Exception as e:
            db.session.rollback()
            print(f"Errore nell'aggiunta versamento: {e}")
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
            
            # Ripristina il saldo (aggiunge l'importo perché era stato sottratto)
            conto.saldo_corrente -= versamento.importo  # importo è negativo, quindi lo sottrae (= aggiunge)
            
            # Elimina il versamento
            db.session.delete(versamento)
            db.session.commit()
            
            return True, "Versamento eliminato e saldo ripristinato"
            
        except Exception as e:
            db.session.rollback()
            print(f"Errore nell'eliminazione versamento: {e}")
            return False, f"Errore nell'eliminazione: {str(e)}"
    
    def reset_conto(self, nome_conto):
        """Reset del conto al saldo iniziale"""
        try:
            conto = db.session.query(ContoPersonale).filter(
                ContoPersonale.nome_conto == nome_conto
            ).first()
            
            if not conto:
                return False, "Conto non trovato"
            
            # Elimina tutti i versamenti
            db.session.query(VersamentoPersonale).filter(
                VersamentoPersonale.conto_id == conto.id
            ).delete()
            
            # Ripristina il saldo iniziale
            conto.saldo_corrente = conto.saldo_iniziale
            
            db.session.commit()
            
            return True, f"Conto di {nome_conto} resettato al saldo iniziale"
            
        except Exception as e:
            db.session.rollback()
            print(f"Errore nel reset conto: {e}")
            return False, f"Errore durante il reset: {str(e)}"
    
    def aggiorna_saldo_iniziale(self, nome_conto, nuovo_saldo):
        """Aggiorna il saldo iniziale del conto"""
        try:
            conto = db.session.query(ContoPersonale).filter(
                ContoPersonale.nome_conto == nome_conto
            ).first()
            
            if not conto:
                return False, "Conto non trovato"
            
            # Calcola la differenza
            differenza = nuovo_saldo - conto.saldo_iniziale
            
            # Aggiorna entrambi i saldi
            conto.saldo_iniziale = nuovo_saldo
            conto.saldo_corrente += differenza
            
            db.session.commit()
            
            return True, "Saldo iniziale aggiornato con successo"
            
        except Exception as e:
            db.session.rollback()
            print(f"Errore nell'aggiornamento saldo iniziale: {e}")
            return False, f"Errore nell'aggiornamento: {str(e)}"
    
    def initialize_default_conti(self):
        """Inizializza i conti predefiniti se non esistono"""
        try:
            # Verifica e crea il conto di Maurizio
            maurizio = self.inizializza_conto_personale('Maurizio')
            
            # Verifica e crea il conto di Antonietta
            antonietta = self.inizializza_conto_personale('Antonietta')
            
            if maurizio and antonietta:
                print("Conti personali di Maurizio e Antonietta inizializzati")
                return True
            
            return False
            
        except Exception as e:
            print(f"Errore nell'inizializzazione conti predefiniti: {e}")
            return False
