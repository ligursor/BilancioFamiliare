"""Blueprint per la gestione dei conti personali.

Questa versione evita riferimenti a nomi specifici e usa identificatori
dinamici (id o nome) per risalire al conto richiesto.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from datetime import datetime, date
from app.services.conto_personale.conti_personali_service import ContiPersonaliService
from app import db
from sqlalchemy import func

conti_bp = Blueprint('conti', __name__)


@conti_bp.route('/')
def lista():
    """Lista dei conti personali: se esiste almeno un conto reindirizza al primo, altrimenti mostra errore."""
    try:
        from app.models.ContoPersonale import ContoPersonale
        conti = ContoPersonale.query.order_by(ContoPersonale.id.asc()).all()
        if not conti:
            flash('Nessun conto personale configurato', 'warning')
            return redirect(url_for('main.index'))
        # redirect al primo conto per compatibilità
        return redirect(url_for('conti.view', conto_id=conti[0].id))
    except Exception as e:
        flash(f'Errore nel caricamento conti personali: {e}', 'error')
        return redirect(url_for('main.index'))


@conti_bp.route('/<int:conto_id>')
def view(conto_id):
    """Visualizza il dashboard di un conto personale identificato dall'id.

    Manteniamo la compatibilità con il service esistente che lavora con il nome
    del conto, quindi recuperiamo il nome dal modello e invochiamo il service.
    """
    try:
        from app.models.ContoPersonale import ContoPersonale
        service = ContiPersonaliService()

        conto = ContoPersonale.query.get(conto_id)
        if not conto:
            flash('Conto personale non trovato', 'error')
            return redirect(url_for('main.index'))

        conto, versamenti = service.get_conto_data(conto.nome_conto)

        if not conto:
            flash('Errore nel caricamento del conto', 'error')
            return redirect(url_for('main.index'))

        return render_template('conti_personali/conto_personale.html',
                               conto=conto,
                               versamenti=versamenti,
                               nome_persona=conto.nome_conto,
                               config=current_app.config)

    except Exception as e:
        flash(f'Errore nel caricamento conto: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@conti_bp.route('/aggiungi_versamento/<int:conto_id>', methods=['POST'])
def aggiungi_versamento(conto_id):
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
            return redirect(url_for('conti.view', conto_id=conto_id))

        if importo <= 0:
            flash('L\'importo deve essere maggiore di zero', 'error')
            return redirect(url_for('conti.view', conto_id=conto_id))
        
        # Aggiungi il versamento: risolviamo il nome del conto a partire dall'id
        from app.models.ContoPersonale import ContoPersonale
        conto = ContoPersonale.query.get(conto_id)
        if not conto:
            flash('Conto non trovato', 'error')
            return redirect(url_for('main.index'))

        success, message = service.aggiungi_versamento(conto.nome_conto, data, descrizione, importo)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
            
    except ValueError:
        flash('Importo non valido', 'error')
    except Exception as e:
        flash(f'Errore nell\'aggiunta versamento: {str(e)}', 'error')
    
    return redirect(url_for('conti.view', conto_id=conto_id))

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
            return redirect(url_for('conti.lista'))  # fallback

        conto_id = versamento.conto.id
        nome_conto = versamento.conto.nome_conto

        # If the client hasn't confirmed, show a confirmation page
        confirm = request.form.get('confirm') or request.args.get('confirm')
        if confirm not in ('1', 'true', 'yes'):
            # Render a small confirmation template with versamento details
            try:
                return render_template('conti_personali/confirm_delete_versamento.html',
                                       versamento=versamento,
                                       conto_id=conto_id)
            except Exception:
                # Fallback: if template missing, require a query param to confirm
                flash('Conferma richiesta per cancellare il versamento.', 'warning')
                return redirect(url_for('conti.view', conto_id=conto_id))

        # Elimina il versamento (confirmed)
        success, message = service.elimina_versamento(versamento_id)

        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')

        return redirect(url_for('conti.view', conto_id=conto_id))

    except Exception as e:
        flash(f"Errore nell'eliminazione: {str(e)}", 'error')
        return redirect(url_for('conti.lista'))  # fallback

@conti_bp.route('/reset_conto/<int:conto_id>', methods=['POST'])
def reset_conto(conto_id):
    """Reset del conto al saldo iniziale"""
    try:
        from app.models.ContoPersonale import ContoPersonale
        service = ContiPersonaliService()
        conto = ContoPersonale.query.get(conto_id)
        if not conto:
            flash('Conto non trovato', 'error')
            return redirect(url_for('conti.lista'))

        success, message = service.reset_conto(conto.nome_conto)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
            
    except Exception as e:
        flash(f'Errore durante il reset: {str(e)}', 'error')
    
    return redirect(url_for('conti.view', conto_id=conto_id))

@conti_bp.route('/aggiorna_saldo_iniziale/<int:conto_id>', methods=['POST'])
def aggiorna_saldo_iniziale(conto_id):
    """Aggiorna il saldo iniziale del conto"""
    try:
        from app.models.ContoPersonale import ContoPersonale
        service = ContiPersonaliService()
        conto = ContoPersonale.query.get(conto_id)
        if not conto:
            flash('Conto non trovato', 'error')
            return redirect(url_for('conti.lista'))
        
        nuovo_saldo = float(request.form.get('nuovo_saldo_iniziale', 0))
        
        success, message = service.aggiorna_saldo_iniziale(conto.nome_conto, nuovo_saldo)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
            
    except ValueError:
        flash('Saldo non valido', 'error')
    except Exception as e:
        flash(f'Errore nell\'aggiornamento: {str(e)}', 'error')
    
    return redirect(url_for('conti.view', conto_id=conto_id))
