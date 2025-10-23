"""
Configurazione per l'applicazione di gestione bilancio familiare

Aggiornato: Settembre 2025
- Aggiunta categoria Sport e logica budget semplificata  
- Ottimizzazioni UI e caricamento automatico categorie
- Sistema backup migliorato con rotazione automatica
- Configurazione Docker ottimizzata (solo volumi necessari)
- Architettura modulare e object-oriented
"""
import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env se esiste
load_dotenv()

class Config:
    """Configurazione principale dell'applicazione"""
    
    # Database
    # Usa un path assoluto per il database in sviluppo
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(BASE_DIR, "db", "bilancio.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'bilancio-familiare-secret-key-2025'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    
    # Server
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', '5001'))
    
    # Logica di business (aggiornata settembre 2025)
    GIORNO_INIZIO_MESE = 27  # Il mese inizia il 27 del mese precedente
    MESI_PROIEZIONE = 6      # Numero di mesi da visualizzare nella dashboard
    
    # Budget Logic (aggiornata settembre 2025)
    # Sistema di budget mensile con transazioni pianificate il giorno 26
    GIORNO_BUDGET_MENSILE = 26  # Budget pianificati il 26 del mese
    
    # Logica budget:
    # - Categoria Sport -> decurta dal budget "Sport" del 26
    # - Altre categorie -> decurtano dal budget "Altre Spese" del 26
    
    CATEGORIA_SPORT_ID = 8   # ID della categoria Sport
    BUDGET_SPORT_DESCRIZIONE = 'Sport'  # Nome transazione budget Sport
    BUDGET_SPESE_VARIE_DESCRIZIONE = 'Altre Spese'  # Nome transazione budget Spese Mensili
    CATEGORIA_SPESE_MENSILI_ID = 6  # ID della categoria Spese Mensili
    
    # Configurazione stipendio speciale dicembre
    STIPENDIO_NORMALE_IMPORTO = 2076
    STIPENDIO_DICEMBRE_RIDUZIONE_PERCENTUALE = 20  # Riduzione del 20%
    STIPENDIO_DICEMBRE_GIORNO = 20  # Accreditato il 20 dicembre
    STIPENDIO_NORMALE_GIORNO = 27   # Accreditato il 27 degli altri mesi
    
    # Impostazioni UI
    TITOLO_APP = "Gestione Bilancio Familiare"
    DESCRIZIONE_APP = "Sistema di gestione del bilancio familiare con calcolo mensile personalizzato"
    
    # Formattazione
    FORMATO_VALUTA = "€ {:.2f}"
    FORMATO_DATA = "%d/%m/%Y"
    FORMATO_DATA_COMPLETA = "%d/%m/%Y %H:%M"
    
    # Backup automatico (settembre 2025)
    # Backup automatico: funzionalità disabilitata nel codice principale.
    # Implementazioni originali e script di import/export sono stati
    # archiviati in `_backup/obsolete/`. Ripristinare da lì se necessario.
    
    # UI Improvements (settembre 2025)
    AUTO_LOAD_CATEGORIES = True  # Caricamento automatico categorie
    DEFAULT_TRANSACTION_TYPE = 'uscita'  # Tipo default per nuove transazioni
    
    # Gestione Conti Personali (settembre 2025)
    # Configurazione conti separati per Maurizio e Antonietta
    CONTO_MAURIZIO_SALDO_INIZIALE = 1000.00  # Saldo iniziale configurabile
    CONTO_ANTONIETTA_SALDO_INIZIALE = 1000.00  # Saldo iniziale configurabile
    CONTO_PERSONALE_FORMATO_VALUTA = "€ {:.2f}"  # Formato valuta per conti personali
    
    # PostePay Evolution (settembre 2025)
    # Configurazione per gestione abbonamenti PostePay Evolution
    POSTEPAY_SALDO_INIZIALE = 0  # Saldo iniziale PostePay Evolution
    POSTEPAY_FORMATO_VALUTA = "€ {:.2f}"  # Formato valuta per PostePay
    
    # NOTE: non caricare piani/abbonamenti default da file; usare il DB.

class DevelopmentConfig(Config):
    """Configurazione per l'ambiente di sviluppo"""
    DEBUG = True

class ProductionConfig(Config):
    """Configurazione per l'ambiente di produzione"""
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'production-secret-key-change-me'

class TestingConfig(Config):
    """Configurazione per i test"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# Mapping delle configurazioni
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
