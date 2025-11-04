"""Blueprint per la gestione dei conti personali di Maurizio e Antonietta"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from datetime import datetime, date
from app.services.conto_personale.conti_personali_service import ContiPersonaliService

conti_bp = Blueprint('conti', __name__)

@conti_bp.route('/')
def lista():
    """Reindirizza alla lista - non più utilizzato, manteniamo per compatibilità"""
    return redirect(url_for('conti.maurizio'))
@conti_bp.route('/maurizio')
def maurizio():
    """Dashboard per il conto di Maurizio (replica dell'implementazione originale)"""
    try:
        service = ContiPersonaliService()
        conto, versamenti = service.get_conto_data('Maurizio')
        
        if not conto:
            flash('Errore nel caricamento conto di Maurizio', 'error')
            return redirect(url_for('main.index'))
        
        return render_template('conti_personali/conto_personale.html',
                               conto=conto,
                               versamenti=versamenti,
                               nome_persona='Maurizio',
                               config=current_app.config)
        
    except Exception as e:
        flash(f'Errore nel caricamento conto: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@conti_bp.route('/antonietta')
def antonietta():
    """Dashboard per il conto di Antonietta (replica dell'implementazione originale)"""
    try:
        service = ContiPersonaliService()
        conto, versamenti = service.get_conto_data('Antonietta')
        
        if not conto:
            flash('Errore nel caricamento conto di Antonietta', 'error')
            return redirect(url_for('main.index'))
        
        return render_template('conti_personali/conto_personale.html',
                               conto=conto,
                               versamenti=versamenti,
                               nome_persona='Antonietta',
                               config=current_app.config)
        
    except Exception as e:
        flash(f'Errore nel caricamento conto: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@conti_bp.route('/aggiungi_versamento/<nome_conto>', methods=['POST'])
def aggiungi_versamento(nome_conto):
    """Aggiunge un versamento al conto specificato"""
    try:
        service = ContiPersonaliService()
        
        # Parsing dei dati dal form
        data_str = request.form.get('data')
        if data_str:
            data = datetime.strptime(data_str, '%Y-%m-%d').date()
        else:
            data = date.today()
        
        descrizione = request.form.get('descrizione', '').strip()
        importo = float(request.form.get('importo', 0))
        
        # Validazioni
        if not descrizione:
            flash('La descrizione è obbligatoria', 'error')
            return redirect(url_for('conti.' + nome_conto.lower()))
        
        if importo <= 0:
            flash('L\'importo deve essere maggiore di zero', 'error')
            return redirect(url_for('conti.' + nome_conto.lower()))
        
        # Aggiungi il versamento
        success, message = service.aggiungi_versamento(nome_conto, data, descrizione, importo)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
            
    except ValueError:
        flash('Importo non valido', 'error')
    except Exception as e:
        flash(f'Errore nell\'aggiunta versamento: {str(e)}', 'error')
    
    return redirect(url_for('conti.' + nome_conto.lower()))

@conti_bp.route('/elimina_versamento/<int:versamento_id>', methods=['POST'])
def elimina_versamento(versamento_id):
    """Elimina un versamento e ripristina il saldo"""
    try:
        service = ContiPersonaliService()
        
        # Prima recuperiamo il nome del conto per il redirect
        from app.models.ContoPersonale import ContoPersonaleMovimento as VersamentoPersonale
        from app import db

        versamento = db.session.query(VersamentoPersonale).filter(
            VersamentoPersonale.id == versamento_id
        ).first()
        
        if not versamento:
            flash('Versamento non trovato', 'error')
            return redirect(url_for('conti.maurizio'))  # fallback
        
        nome_conto = versamento.conto.nome_conto
        
        # Elimina il versamento
        success, message = service.elimina_versamento(versamento_id)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('conti.' + nome_conto.lower()))
        
    except Exception as e:
        flash(f'Errore nell\'eliminazione: {str(e)}', 'error')
        return redirect(url_for('conti.maurizio'))  # fallback

@conti_bp.route('/reset_conto/<nome_conto>', methods=['POST'])
def reset_conto(nome_conto):
    """Reset del conto al saldo iniziale"""
    try:
        service = ContiPersonaliService()
        success, message = service.reset_conto(nome_conto)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
            
    except Exception as e:
        flash(f'Errore durante il reset: {str(e)}', 'error')
    
    return redirect(url_for('conti.' + nome_conto.lower()))

@conti_bp.route('/aggiorna_saldo_iniziale/<nome_conto>', methods=['POST'])
def aggiorna_saldo_iniziale(nome_conto):
    """Aggiorna il saldo iniziale del conto"""
    try:
        service = ContiPersonaliService()
        
        nuovo_saldo = float(request.form.get('nuovo_saldo', 0))
        
        success, message = service.aggiorna_saldo_iniziale(nome_conto, nuovo_saldo)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
            
    except ValueError:
        flash('Saldo non valido', 'error')
    except Exception as e:
        flash(f'Errore nell\'aggiornamento: {str(e)}', 'error')
    
    return redirect(url_for('conti.' + nome_conto.lower()))
