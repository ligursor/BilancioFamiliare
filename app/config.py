"""Configurazione per l'applicazione di gestione bilancio familiare"""
import os

class Config:
    """Configurazione principale dell'applicazione"""
    
    # Database
    # Usa un path assoluto per il database in sviluppo. Puntiamo alla root del repository
    # così da usare la cartella `db/` presente nella root del progetto.
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "db", "bilancio.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask
    SECRET_KEY = 'bilancio-familiare-secret-key-2025'
    
    # Server
    HOST = '0.0.0.0'
    PORT = 5001
        
    # Manteniamo il formato valuta (usato estensivamente nelle view/templates)
    FORMATO_VALUTA = "€ {:.2f}"
    
# Mapping minimale: usa solamente la configurazione di default
config = {
    'default': Config,
}
