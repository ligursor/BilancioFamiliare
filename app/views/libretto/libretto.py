"""Blueprint per il Libretto Smart"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.services.libretto.libretto_service import LibrettoService
from datetime import datetime

libretto_bp = Blueprint('libretto', __name__)


@libretto_bp.route('/')
def dashboard():
    """Dashboard del Libretto Smart"""
    try:
        service = LibrettoService()
        libretto = service.get_or_create_libretto()
        depositi = service.get_depositi(libretto.id)
        depositi_attivi = service.get_depositi(libretto.id, solo_attivi=True)
        statistiche = service.get_statistiche(libretto.id)
        
        return render_template('libretto/libretto.html',
                             libretto=libretto,
                             depositi=depositi,
                             depositi_attivi=depositi_attivi,
                             statistiche=statistiche)
    except Exception as e:
        flash(f'Errore nel caricamento del libretto: {str(e)}', 'error')
        return render_template('libretto/libretto.html',
                             libretto=None,
                             depositi=[],
                             depositi_attivi=[],
                             statistiche={})


@libretto_bp.route('/aggiorna_saldo', methods=['POST'])
def aggiorna_saldo():
    """Aggiorna il saldo disponibile del libretto"""
    try:
        service = LibrettoService()
        libretto = service.get_libretto()
        
        if not libretto:
            flash('Libretto non trovato', 'error')
            return redirect(url_for('libretto.dashboard'))
        
        nuovo_saldo = request.form.get('saldo_disponibile')
        if nuovo_saldo is None:
            flash('Saldo non specificato', 'error')
            return redirect(url_for('libretto.dashboard'))
        
        service.aggiorna_saldo(libretto.id, nuovo_saldo)
        flash('Saldo aggiornato con successo', 'success')
        
    except Exception as e:
        flash(f'Errore nell\'aggiornamento del saldo: {str(e)}', 'error')
    
    return redirect(url_for('libretto.dashboard'))


@libretto_bp.route('/aggiungi_deposito', methods=['POST'])
def aggiungi_deposito():
    """Aggiunge un nuovo deposito Supersmart"""
    try:
        service = LibrettoService()
        libretto = service.get_libretto()
        
        if not libretto:
            flash('Libretto non trovato', 'error')
            return redirect(url_for('libretto.dashboard'))
        
        # Recupera i dati dal form
        descrizione = request.form.get('descrizione')
        data_attivazione_str = request.form.get('data_attivazione')
        data_scadenza_str = request.form.get('data_scadenza')
        tasso = request.form.get('tasso')
        deposito = request.form.get('deposito')
        netto = request.form.get('netto')
        
        # Validazione
        if not all([descrizione, data_attivazione_str, data_scadenza_str, tasso, deposito, netto]):
            flash('Tutti i campi sono obbligatori', 'error')
            return redirect(url_for('libretto.dashboard'))
        
        # Conversione date
        data_attivazione = datetime.strptime(data_attivazione_str, '%Y-%m-%d').date()
        data_scadenza = datetime.strptime(data_scadenza_str, '%Y-%m-%d').date()
        
        # Crea il deposito
        service.crea_deposito(
            libretto_id=libretto.id,
            descrizione=descrizione,
            data_attivazione=data_attivazione,
            data_scadenza=data_scadenza,
            tasso=tasso,
            deposito=deposito,
            netto=netto
        )
        
        flash('Deposito aggiunto con successo', 'success')
        
    except ValueError as e:
        flash(f'Errore nei dati inseriti: {str(e)}', 'error')
    except Exception as e:
        flash(f'Errore nell\'aggiunta del deposito: {str(e)}', 'error')
    
    return redirect(url_for('libretto.dashboard'))


@libretto_bp.route('/modifica_deposito/<int:deposito_id>', methods=['POST'])
def modifica_deposito(deposito_id):
    """Modifica un deposito esistente"""
    try:
        service = LibrettoService()
        
        # Recupera i dati dal form
        descrizione = request.form.get('descrizione')
        data_attivazione_str = request.form.get('data_attivazione')
        data_scadenza_str = request.form.get('data_scadenza')
        tasso = request.form.get('tasso')
        deposito = request.form.get('deposito')
        netto = request.form.get('netto')
        
        # Conversione date
        data_attivazione = datetime.strptime(data_attivazione_str, '%Y-%m-%d').date() if data_attivazione_str else None
        data_scadenza = datetime.strptime(data_scadenza_str, '%Y-%m-%d').date() if data_scadenza_str else None
        
        # Aggiorna il deposito
        service.aggiorna_deposito(
            deposito_id=deposito_id,
            descrizione=descrizione,
            data_attivazione=data_attivazione,
            data_scadenza=data_scadenza,
            tasso=tasso,
            deposito=deposito,
            netto=netto
        )
        
        flash('Deposito modificato con successo', 'success')
        
    except ValueError as e:
        flash(f'Errore nei dati inseriti: {str(e)}', 'error')
    except Exception as e:
        flash(f'Errore nella modifica del deposito: {str(e)}', 'error')
    
    return redirect(url_for('libretto.dashboard'))


@libretto_bp.route('/elimina_deposito/<int:deposito_id>', methods=['POST'])
def elimina_deposito(deposito_id):
    """Elimina un deposito"""
    try:
        service = LibrettoService()
        service.elimina_deposito(deposito_id)
        flash('Deposito eliminato con successo', 'success')
        
    except ValueError as e:
        flash(f'Deposito non trovato: {str(e)}', 'error')
    except Exception as e:
        flash(f'Errore nell\'eliminazione del deposito: {str(e)}', 'error')
    
    return redirect(url_for('libretto.dashboard'))
