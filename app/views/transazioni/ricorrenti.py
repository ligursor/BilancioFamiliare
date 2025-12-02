"""Blueprint per la gestione delle transazioni ricorrenti."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models.TransazioniRicorrenti import TransazioniRicorrenti
from app.models.Categorie import Categorie
from app.services.transazioni.transazioni_ricorrenti_service import TransazioniRicorrentiService
from app.services.transazioni.generated_transaction_service import GeneratedTransactionService
from datetime import datetime, date

ricorrenti_bp = Blueprint('ricorrenti', __name__, url_prefix='/ricorrenti')
service = TransazioniRicorrentiService()
generated_service = GeneratedTransactionService()


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
            # Propaga la nuova transazione ricorrente nell'orizzonte temporale
            try:
                created_count = generated_service.populate_horizon_from_recurring(
                    months=6,
                    base_date=date.today(),
                    create_only_future=False
                )
                if created_count > 0:
                    flash(f'{created_count} transazioni generate dall\'orizzonte temporale', 'info')
            except Exception as e:
                flash(f'Attenzione: transazione ricorrente creata ma errore nella generazione: {str(e)}', 'warning')
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
            # Aggiorna le transazioni generate nell'orizzonte temporale
            try:
                from app.models.Transazioni import Transazioni
                # Recupera la transazione ricorrente aggiornata
                ricorrente = service.get_by_id(ricorrente_id)
                if ricorrente:
                    # Aggiorna tutte le transazioni generate non ancora effettuate (data_effettiva=NULL)
                    # e non modificate manualmente (tx_modificata=False)
                    generated_txs = Transazioni.query.filter(
                        Transazioni.id_recurring_tx == ricorrente_id,
                        Transazioni.data_effettiva.is_(None),
                        Transazioni.tx_modificata == False
                    ).all()
                    
                    updated_count = 0
                    for tx in generated_txs:
                        if descrizione:
                            tx.descrizione = ricorrente.descrizione
                        if importo is not None:
                            tx.importo = ricorrente.importo
                        if tipo:
                            tx.tipo = ricorrente.tipo
                        if categoria_id is not None:
                            tx.categoria_id = ricorrente.categoria_id
                        updated_count += 1
                    
                    if updated_count > 0:
                        db.session.commit()
                        flash(f'{updated_count} transazioni programmate aggiornate', 'info')
            except Exception as e:
                db.session.rollback()
                flash(f'Attenzione: transazione ricorrente modificata ma errore nell\'aggiornamento delle transazioni generate: {str(e)}', 'warning')
        else:
            flash(message, 'error')
            
    except Exception as e:
        flash(f'Errore nella modifica della transazione ricorrente: {str(e)}', 'error')
    
    return redirect(url_for('ricorrenti.lista'))


@ricorrenti_bp.route('/elimina/<int:ricorrente_id>', methods=['POST'])
def elimina(ricorrente_id):
    """Elimina una transazione ricorrente"""
    try:
        # Prima elimina le transazioni generate associate
        from app.models.Transazioni import Transazioni
        deleted_count = 0
        try:
            generated_txs = Transazioni.query.filter_by(id_recurring_tx=ricorrente_id).all()
            deleted_count = len(generated_txs)
            for tx in generated_txs:
                db.session.delete(tx)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Errore nell\'eliminazione delle transazioni generate: {str(e)}', 'warning')
        
        # Poi elimina la transazione ricorrente
        success, message = service.delete(ricorrente_id)
        
        if success:
            flash(message, 'success')
            if deleted_count > 0:
                flash(f'{deleted_count} transazioni generate eliminate dall\'orizzonte temporale', 'info')
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
