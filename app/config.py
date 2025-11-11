"""Configurazione per l'applicazione di gestione bilancio familiare"""
import os
from datetime import timedelta

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
    
    # Sessione
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=3)  # Durata sessione: 3 minuti
    SESSION_COOKIE_HTTPONLY = True  # Cookie non accessibile da JavaScript
    SESSION_COOKIE_SAMESITE = 'Lax'  # Protezione CSRF
    
    # Server
    HOST = '0.0.0.0'
    PORT = 5001
        
    # Manteniamo il formato valuta (usato estensivamente nelle view/templates)
    FORMATO_VALUTA = "€ {:.2f}"
    
# Mapping minimale: usa solamente la configurazione di default
config = {
    'default': Config,
}
