"""
Blueprint per la gestione del database
"""
from flask import Blueprint, redirect, url_for, flash
from app.models.base import Categoria, SaldoIniziale
from app.models.transazioni import Transazione
from app.models.paypal import PaypalPiano, PaypalRata
from app.models.conti_personali import ContoPersonale, VersamentoPersonale
from app.models.garage import Veicolo, BolloAuto, ManutenzioneAuto
from app.models.postepay import PostePayEvolution, AbbonamentoPostePay, MovimentoPostePay
from app.models.appunti import Appunto
from app import db
from app.utils.backup import (
    cleanup_old_backups,
    find_latest_backup,
    import_backup_data,
    is_database_empty,
    serialize_date,
    export_database,
    export_database_to_backup
)

database_bp = Blueprint('database', __name__)

@database_bp.route('/')
def index():
    """Gestione database: mostra i file di backup disponibili"""
    import os
    backup_dir = os.path.abspath('./backup')
    files = []
    if os.path.exists(backup_dir):
        for fname in sorted(os.listdir(backup_dir), reverse=True):
            if fname.endswith('.json'):
                files.append(fname)
    html = '<h2>Backup disponibili</h2>'
    if files:
        html += '<ul>'
        for f in files:
            html += f'<li><a href="/backup/{f}" download>{f}</a></li>'
        html += '</ul>'
    else:
        html += '<p>Nessun backup trovato.</p>'
    html += '<br><a href="/">Torna alla home</a>'
    return html

@database_bp.route('/import')
def import_data():
    """Import database"""
    return "Import Database - in sviluppo"

@database_bp.route('/export')
def export():
    """Export manuale: scarica il database in formato JSON"""
    from flask import Response
    return export_database(
        db,
        Categoria, SaldoIniziale, Transazione, PaypalPiano, PaypalRata,
        ContoPersonale, VersamentoPersonale, Veicolo, BolloAuto, ManutenzioneAuto,
        PostePayEvolution, AbbonamentoPostePay, MovimentoPostePay, Appunto,
        flash=flash, Response=Response, url_for=url_for
    )

# RIMOSSO: export automatico dopo operazioni su database
