"""
Blueprint per gli appunti
Replica l'implementazione originale da app.py
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime
from app.models.appunti import Appunto
from app.models.base import Categoria
from app.models.transazioni import Transazione
from app import db

appunti_bp = Blueprint('appunti', __name__)

@appunti_bp.route('/')
def lista():
    """Visualizza tutti gli appunti"""
    try:
        # Ordina gli appunti per data creazione (più recenti prima)
        appunti = Appunto.query.order_by(
            Appunto.data_creazione.desc()
        ).all()
        
        from app.services.categorie_service import CategorieService
        service_cat = CategorieService()
        categorie = service_cat.get_all_categories(exclude_paypal=True)
        
        return render_template('appunti.html', appunti=appunti, categorie=categorie)
    except Exception as e:
        flash(f'Errore nel caricamento appunti: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@appunti_bp.route('/nuovo', methods=['POST'])
def nuovo():
    """Crea un nuovo appunto"""
    try:
        titolo = request.form['titolo']
        tipo = request.form.get('tipo', 'uscita')
        importo_stimato = float(request.form['importo_stimato']) if request.form.get('importo_stimato') else None
        categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        note = request.form.get('note', '')
        
        appunto = Appunto(
            titolo=titolo,
            tipo=tipo,
            importo_stimato=importo_stimato,
            categoria_id=categoria_id,
            note=note
        )
        
        db.session.add(appunto)
        db.session.commit()
        
        flash(f'Appunto "{titolo}" aggiunto con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'aggiunta dell\'appunto: {str(e)}', 'error')
    
    return redirect(url_for('appunti.lista'))


@appunti_bp.route('/<int:id>/modifica', methods=['POST'])
def modifica(id):
    """Modifica un appunto esistente"""
    appunto = Appunto.query.get_or_404(id)
    
    try:
        if 'titolo' in request.form:
            appunto.titolo = request.form['titolo']
        if 'tipo' in request.form:
            appunto.tipo = request.form['tipo']
        if 'importo_stimato' in request.form:
            appunto.importo_stimato = float(request.form['importo_stimato']) if request.form['importo_stimato'] else None
        if 'categoria_id' in request.form:
            appunto.categoria_id = int(request.form['categoria_id']) if request.form['categoria_id'] else None
        if 'note' in request.form:
            appunto.note = request.form['note']
        
        appunto.data_aggiornamento = datetime.utcnow()
        
        db.session.commit()
        flash(f'Appunto "{appunto.titolo}" modificato con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la modifica dell\'appunto: {str(e)}', 'error')
    
    return redirect(url_for('appunti.lista'))


@appunti_bp.route('/elimina/<int:id>', methods=['POST'])
def elimina(id):
    """Elimina un appunto"""
    appunto = Appunto.query.get_or_404(id)
    titolo = appunto.titolo
    
    try:
        db.session.delete(appunto)
        db.session.commit()
        return jsonify({'success': True, 'message': f'Appunto "{titolo}" eliminato con successo!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Errore durante l\'eliminazione: {str(e)}'}), 500


@appunti_bp.route('/trasferisci', methods=['POST'])
def trasferisci():
    """Trasferisce un appunto nelle transazioni mensili e lo elimina"""
    try:
        appunto_id = int(request.form['appunto_id'])
        data_transazione = datetime.strptime(request.form['data_transazione'], '%Y-%m-%d').date()
        
        # Recupera l'appunto
        appunto = Appunto.query.get_or_404(appunto_id)
        
        # Crea la transazione usando i dati dell'appunto
        transazione = Transazione(
            data=data_transazione,
            data_effettiva=data_transazione if data_transazione <= datetime.now().date() else None,
            descrizione=appunto.titolo,
            importo=appunto.importo_stimato or 0.0,
            categoria_id=appunto.categoria_id,
            tipo=appunto.tipo
        )
        
        # Salva la transazione
        db.session.add(transazione)
        
        # Elimina l'appunto
        db.session.delete(appunto)
        
        db.session.commit()
        
        flash(f'Appunto "{appunto.titolo}" trasferito con successo nelle transazioni!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante il trasferimento: {str(e)}', 'error')
    
    return redirect(url_for('appunti.lista'))


@appunti_bp.route('/<int:id>/dati')
def dati(id):
    """Restituisce i dati di un appunto in formato JSON"""
    try:
        print(f"DEBUG: Richiesta dati per appunto ID: {id}")
        appunto = Appunto.query.get_or_404(id)
        print(f"DEBUG: Appunto trovato: {appunto.titolo}")
        
        result = {
            'success': True,
            'appunto': {
                'id': appunto.id,
                'titolo': appunto.titolo,
                'tipo': appunto.tipo,
                'importo_stimato': appunto.importo_stimato,
                'categoria_id': appunto.categoria_id,
                'note': appunto.note
            }
        }
        print(f"DEBUG: Restituendo JSON: {result}")
        return jsonify(result)
    except Exception as e:
        print(f"DEBUG: Errore in dati appunto: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@appunti_bp.route('/modifica', methods=['POST'])
def modifica_form():
    """Modifica un appunto tramite form"""
    try:
        appunto_id = int(request.form['appunto_id'])
        appunto = Appunto.query.get_or_404(appunto_id)
        
        # Aggiorna i campi
        appunto.titolo = request.form['titolo']
        appunto.tipo = request.form.get('tipo', 'uscita')
        appunto.importo_stimato = float(request.form['importo_stimato']) if request.form.get('importo_stimato') else None
        appunto.categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        appunto.note = request.form.get('note', '')
        appunto.data_aggiornamento = datetime.utcnow()
        
        db.session.commit()
        flash(f'Appunto "{appunto.titolo}" modificato con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la modifica: {str(e)}', 'error')
    
    return redirect(url_for('appunti.lista'))


@appunti_bp.route('/<int:id>/converti', methods=['POST'])
def converti(id):
    """Converte un appunto in una transazione reale"""
    appunto = Appunto.query.get_or_404(id)
    
    try:
        data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        importo = float(request.form['importo'])
        descrizione = request.form.get('descrizione', appunto.titolo)
        
        # Crea la transazione
        transazione = Transazione(
            data=data,
            data_effettiva=data if data <= datetime.now().date() else None,
            descrizione=descrizione,
            importo=importo,
            categoria_id=appunto.categoria_id or int(request.form['categoria_id']),
            tipo='uscita',  # Assumiamo che sia una spesa
            ricorrente=False
        )
        
        db.session.add(transazione)
        db.session.flush()  # Per ottenere l'ID della transazione
        
        # Elimina l'appunto (invece di segnarlo come completato visto che il campo non esiste)
        db.session.delete(appunto)
        
        db.session.commit()
        
        flash(f'Appunto "{appunto.titolo}" convertito in transazione con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la conversione dell\'appunto: {str(e)}', 'error')
    
    return redirect(url_for('appunti.lista'))
