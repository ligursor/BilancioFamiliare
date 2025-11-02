"""
Blueprint per la gestione delle transazioni ricorrenti.
Fornisce interfaccia per visualizzare, creare, modificare ed eliminare transazioni ricorrenti.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models.TransazioniRicorrenti import TransazioniRicorrenti
from app.models.Categorie import Categorie
from app.services.transazioni.transazioni_ricorrenti_service import TransazioniRicorrentiService
from datetime import datetime, date

ricorrenti_bp = Blueprint('ricorrenti', __name__, url_prefix='/ricorrenti')
service = TransazioniRicorrentiService()


@ricorrenti_bp.route('/')
def lista():
    """Visualizza la lista delle transazioni ricorrenti"""
    try:
        # Recupera le transazioni ricorrenti
        ricorrenti = service.get_all()
        
        # Recupera le categorie per i form
        categorie = Categorie.query.order_by(Categorie.nome).all()
        
        # Statistiche
        stats = service.get_stats()
        
        return render_template(
            'transazioni/ricorrenti.html',
            ricorrenti=ricorrenti,
            categorie=categorie,
            stats=stats
        )
    except Exception as e:
        flash(f'Errore nel caricamento delle transazioni ricorrenti: {str(e)}', 'error')
        return render_template('transazioni/ricorrenti.html', ricorrenti=[], categorie=[], stats={})


@ricorrenti_bp.route('/aggiungi', methods=['POST'])
def aggiungi():
    """Aggiunge una nuova transazione ricorrente"""
    try:
        descrizione = request.form['descrizione']
        importo = float(request.form['importo'])
        tipo = request.form['tipo']
        giorno = int(request.form.get('giorno', 1))
        categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        cadenza = request.form.get('cadenza', 'mensile')
        skip_month_if_annual = request.form.get('skip_month_if_annual', 'off') == 'on'
        
        success, message, ricorrente = service.create(
            descrizione=descrizione,
            importo=importo,
            tipo=tipo,
            giorno=giorno,
            categoria_id=categoria_id,
            cadenza=cadenza,
            skip_month_if_annual=skip_month_if_annual
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
            
    except Exception as e:
        flash(f'Errore nell\'aggiunta della transazione ricorrente: {str(e)}', 'error')
    
    return redirect(url_for('ricorrenti.lista'))


@ricorrenti_bp.route('/modifica/<int:ricorrente_id>', methods=['POST'])
def modifica(ricorrente_id):
    """Modifica una transazione ricorrente esistente"""
    try:
        descrizione = request.form.get('descrizione')
        importo = float(request.form['importo']) if request.form.get('importo') else None
        tipo = request.form.get('tipo')
        giorno = int(request.form['giorno']) if request.form.get('giorno') else None
        categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') and request.form['categoria_id'] else None
        cadenza = request.form.get('cadenza')
        skip_month_if_annual = request.form.get('skip_month_if_annual', 'off') == 'on'
        
        success, message = service.update(
            ricorrente_id=ricorrente_id,
            descrizione=descrizione,
            importo=importo,
            tipo=tipo,
            giorno=giorno,
            categoria_id=categoria_id,
            cadenza=cadenza,
            skip_month_if_annual=skip_month_if_annual
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
            
    except Exception as e:
        flash(f'Errore nella modifica della transazione ricorrente: {str(e)}', 'error')
    
    return redirect(url_for('ricorrenti.lista'))


@ricorrenti_bp.route('/elimina/<int:ricorrente_id>', methods=['POST'])
def elimina(ricorrente_id):
    """Elimina una transazione ricorrente"""
    try:
        success, message = service.delete(ricorrente_id)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
            
    except Exception as e:
        flash(f'Errore nell\'eliminazione della transazione ricorrente: {str(e)}', 'error')
    
    return redirect(url_for('ricorrenti.lista'))


@ricorrenti_bp.route('/dati/<int:ricorrente_id>')
def dati(ricorrente_id):
    """Restituisce i dati di una transazione ricorrente in formato JSON"""
    try:
        ricorrente = service.get_by_id(ricorrente_id)
        if not ricorrente:
            return jsonify({'success': False, 'message': 'Transazione ricorrente non trovata'}), 404
        
        return jsonify({
            'success': True,
            'ricorrente': {
                'id': ricorrente.id,
                'descrizione': ricorrente.descrizione,
                'importo': ricorrente.importo,
                'tipo': ricorrente.tipo,
                'giorno': ricorrente.giorno,
                'categoria_id': ricorrente.categoria_id,
                'cadenza': ricorrente.cadenza,
                'skip_month_if_annual': bool(ricorrente.skip_month_if_annual)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
