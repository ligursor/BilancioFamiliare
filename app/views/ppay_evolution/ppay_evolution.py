"""PostePay Evolution views moved into their own module.

Originally the implementation lived at the package __init__ during migration.
This module holds the actual blueprint and route handlers.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, date, timedelta
from app.models.postepay import PostePayEvolution, AbbonamentoPostePay, MovimentoPostePay
from app import db

ppay_bp = Blueprint('ppay', __name__)

def inizializza_postepay():
    """Inizializza il sistema PostePay se necessario"""
    postepay = PostePayEvolution.query.first()
    if not postepay:
        postepay = PostePayEvolution(
            numero_carta='****1234',  # Placeholder
            saldo_attuale=0.0,
            limite_mensile=3000.0
        )
        db.session.add(postepay)
        db.session.commit()
    return postepay

@ppay_bp.route('/')
def evolution():
    """Dashboard PostePay Evolution - replica dell'implementazione originale"""
    try:
        # Inizializza il sistema PostePay se necessario
        inizializza_postepay()
        
        # Recupera dati
        postepay = PostePayEvolution.query.first()
        abbonamenti = AbbonamentoPostePay.query.order_by(AbbonamentoPostePay.nome).all()
        movimenti = MovimentoPostePay.query.order_by(MovimentoPostePay.data.desc()).limit(10).all()
        
        # Calcola statistiche
        abbonamenti_attivi = [a for a in abbonamenti if a.attivo]
        spesa_mensile = sum(a.importo for a in abbonamenti_attivi)
        
        # Prossimi addebiti (entro 30 giorni)
        oggi = date.today()
        prossimi_addebiti = []
        for abbonamento in abbonamenti_attivi:
            prossimo = abbonamento.prossimo_addebito
            if (prossimo - oggi).days <= 30:
                prossimi_addebiti.append({
                    'abbonamento': abbonamento,
                    'data': prossimo,
                    'giorni': (prossimo - oggi).days
                })
        prossimi_addebiti.sort(key=lambda x: x['data'])

        # LOGICA CORRETTA: saldo scalato progressivamente
        saldo_simulato = postepay.saldo_attuale if postepay else 0
        for addebito in prossimi_addebiti:
            if saldo_simulato >= addebito['abbonamento'].importo:
                addebito['saldo_sufficiente'] = True
                saldo_simulato -= addebito['abbonamento'].importo
            else:
                addebito['saldo_sufficiente'] = False

        # Controllo saldo insufficiente per prossimi addebiti (alert progressivo)
        saldo_alert = postepay.saldo_attuale if postepay else 0
        addebiti_problematici = []
        for addebito in prossimi_addebiti:
            if saldo_alert < addebito['abbonamento'].importo:
                addebiti_problematici.append({
                    'abbonamento': addebito['abbonamento'],
                    'data': addebito['data'],
                    'giorni': addebito['giorni'],
                    'importo_mancante': addebito['abbonamento'].importo - saldo_alert,
                    'saldo_attuale': saldo_alert
                })
            saldo_alert -= addebito['abbonamento'].importo

        # Serializza abbonamenti per JS
        abbonamenti_serializzati = []
        for abbo in abbonamenti:
            abbonamenti_serializzati.append({
                'id': abbo.id,
                'nome': abbo.nome,
                'descrizione': abbo.descrizione,
                'importo': abbo.importo,
                'giorno_addebito': abbo.giorno_addebito,
                'attivo': abbo.attivo
            })

        return render_template('postepay_evolution/ppay_evolution.html',
                             postepay=postepay,
                             abbonamenti=abbonamenti,
                             abbonamenti_json=abbonamenti_serializzati,
                             movimenti=movimenti,
                             spesa_mensile=spesa_mensile,
                             prossimi_addebiti=prossimi_addebiti,
                             addebiti_problematici=addebiti_problematici)
        
    except Exception as e:
        flash(f'Errore nel caricamento PostePay Evolution: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@ppay_bp.route('/ricarica', methods=['POST'])
def ricarica():
    """Aggiunge una ricarica PostePay"""
    try:
        postepay = PostePayEvolution.query.first()
        if not postepay:
            postepay = inizializza_postepay()
        
        importo = float(request.form.get('importo', 0))
        descrizione = request.form.get('descrizione', '').strip()
        data_str = request.form.get('data', '')
        
        if importo <= 0:
            flash('L\'importo deve essere maggiore di zero', 'error')
            return redirect(url_for('ppay.evolution'))
        
        if not descrizione:
            descrizione = f'Ricarica PostePay'
        
        # Parsing della data
        if data_str:
            data_movimento = datetime.strptime(data_str, '%Y-%m-%d').date()
        else:
            data_movimento = date.today()
        
        # Crea movimento
        movimento = MovimentoPostePay(
            data=data_movimento,
            tipo='ricarica',
            importo=importo,
            descrizione=descrizione,
            saldo_dopo=postepay.saldo_attuale + importo
        )
        
        # Aggiorna saldo
        postepay.saldo_attuale += importo
        
        db.session.add(movimento)
        db.session.commit()
        
        flash(f'Ricarica di €{importo:.2f} aggiunta con successo!', 'success')
        
    except ValueError:
        flash('Importo non valido', 'error')
    except Exception as e:
        flash(f'Errore nell\'aggiunta ricarica: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/spesa', methods=['POST'])
def spesa():
    """Aggiunge una spesa PostePay"""
    try:
        postepay = PostePayEvolution.query.first()
        if not postepay:
            postepay = inizializza_postepay()
        
        importo = float(request.form.get('importo', 0))
        descrizione = request.form.get('descrizione', '').strip()
        data_str = request.form.get('data', '')
        
        if importo <= 0:
            flash('L\'importo deve essere maggiore di zero', 'error')
            return redirect(url_for('ppay.evolution'))
        
        if not descrizione:
            descrizione = f'Spesa PostePay'
        
        # Parsing della data
        if data_str:
            data_movimento = datetime.strptime(data_str, '%Y-%m-%d').date()
        else:
            data_movimento = date.today()
        
        # Verifica saldo disponibile
        if postepay.saldo_attuale < importo:
            flash('Saldo insufficiente per questa spesa', 'error')
            return redirect(url_for('ppay.evolution'))
        
        # Crea movimento
        movimento = MovimentoPostePay(
            data=data_movimento,
            tipo='spesa',
            importo=importo,
            descrizione=descrizione,
            saldo_dopo=postepay.saldo_attuale - importo
        )
        
        # Aggiorna saldo
        postepay.saldo_attuale -= importo
        
        db.session.add(movimento)
        db.session.commit()
        
        flash(f'Spesa di €{importo:.2f} aggiunta con successo!', 'success')
        
    except ValueError:
        flash('Importo non valido', 'error')
    except Exception as e:
        flash(f'Errore nell\'aggiunta spesa: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/toggle_abbonamento/<int:abbonamento_id>', methods=['POST'])
def toggle_abbonamento(abbonamento_id):
    """Attiva/disattiva un abbonamento PostePay"""
    try:
        abbonamento = AbbonamentoPostePay.query.get_or_404(abbonamento_id)
        
        abbonamento.attivo = not abbonamento.attivo
        if not abbonamento.attivo:
            abbonamento.data_disattivazione = datetime.utcnow()
        else:
            abbonamento.data_disattivazione = None
        
        db.session.commit()
        
        stato = "attivato" if abbonamento.attivo else "disattivato"
        flash(f'Abbonamento {abbonamento.nome} {stato}!', 'success')
        
    except Exception as e:
        flash(f'Errore nella modifica dell\'abbonamento: {str(e)}', 'error')
    
    return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/elimina_abbonamento/<int:abbonamento_id>', methods=['POST'])
def elimina_abbonamento(abbonamento_id):
    """Elimina un abbonamento PostePay"""
    try:
        abbonamento = AbbonamentoPostePay.query.get_or_404(abbonamento_id)
        nome = abbonamento.nome
        
        # Elimina anche tutti i movimenti associati
        MovimentoPostePay.query.filter_by(abbonamento_id=abbonamento_id).delete()
        
        db.session.delete(abbonamento)
        db.session.commit()
        
        flash(f'Abbonamento {nome} eliminato con successo!', 'success')
        
    except Exception as e:
        flash(f'Errore nell\'eliminazione dell\'abbonamento: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/elimina_movimento/<int:movimento_id>', methods=['POST'])
def elimina_movimento(movimento_id):
    """Elimina un movimento PostePay e aggiorna il saldo"""
    try:
        movimento = MovimentoPostePay.query.get_or_404(movimento_id)
        importo = movimento.importo

        # Elimina il movimento
        db.session.delete(movimento)

        # Aggiorna saldo PostePay invertendo l'effetto del movimento
        postepay = PostePayEvolution.query.first()
        if postepay:
            postepay.saldo_attuale -= importo
            postepay.data_ultimo_aggiornamento = datetime.utcnow()

        db.session.commit()
        flash('Movimento eliminato con successo!', 'success')
    except Exception as e:
        flash(f'Errore nell\'eliminazione del movimento: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/modifica_saldo', methods=['POST'])
def modifica_saldo():
    """Modifica il saldo PostePay Evolution"""
    try:
        nuovo_saldo = float(request.form['nuovo_saldo'])
        motivo = request.form.get('motivo', 'Modifica manuale saldo')
        
        postepay = PostePayEvolution.query.first()
        if not postepay:
            flash('Errore: Sistema PostePay non inizializzato!', 'error')
            return redirect(url_for('ppay.evolution'))
        
        # Calcola la differenza per il movimento
        saldo_precedente = postepay.saldo_attuale
        differenza = nuovo_saldo - saldo_precedente
        
        # Aggiorna il saldo
        postepay.saldo_attuale = nuovo_saldo
        postepay.data_ultimo_aggiornamento = datetime.utcnow()
        
        # Crea un movimento per tracciare la modifica
        if differenza != 0:
            movimento = MovimentoPostePay(
                data=date.today(),
                descrizione=f"{motivo} (da €{saldo_precedente:.2f} a €{nuovo_saldo:.2f})",
                importo=differenza,
                tipo='correzione'
            )
            db.session.add(movimento)
        
        db.session.commit()
        
        if differenza > 0:
            flash(f'Saldo aggiornato! Aggiunta di €{differenza:.2f}', 'success')
        elif differenza < 0:
            flash(f'Saldo aggiornato! Riduzione di €{abs(differenza):.2f}', 'success')
        else:
            flash('Saldo confermato (nessuna modifica)', 'info')
        
    except ValueError:
        flash('Importo non valido', 'error')
    except Exception as e:
        flash(f'Errore nella modifica del saldo: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/aggiungi_abbonamento', methods=['POST'])
def aggiungi_abbonamento():
    """Aggiunge un nuovo abbonamento PostePay"""
    try:
        # Determine giorno_addebito: prefer explicit field, otherwise derive from provided date or today
        giorno_raw = request.form.get('giorno_addebito')
        if giorno_raw:
            try:
                giorno_addebito = int(giorno_raw)
            except ValueError:
                giorno_addebito = None
        else:
            # try to derive from the 'data' field if provided
            data_str = request.form.get('data', '')
            if data_str:
                try:
                    giorno_addebito = datetime.strptime(data_str, '%Y-%m-%d').day
                except Exception:
                    giorno_addebito = None
            else:
                giorno_addebito = None

        if not giorno_addebito:
            # fallback to today's day of month
            giorno_addebito = date.today().day

        abbonamento = AbbonamentoPostePay(
            nome=request.form['nome'],
            descrizione=request.form.get('descrizione', ''),
            importo=float(request.form['importo']),
            giorno_addebito=giorno_addebito,
            attivo=True
        )
        # Server-side lightweight deduplication: if an identical abbonamento
        # was created in the last few seconds, skip to avoid duplicates from
        # accidental double-submit (client-side guard should handle most cases).
        recent_threshold = datetime.utcnow() - timedelta(seconds=5)
        existing = AbbonamentoPostePay.query.filter(
            AbbonamentoPostePay.nome == abbonamento.nome,
            AbbonamentoPostePay.importo == abbonamento.importo,
            AbbonamentoPostePay.giorno_addebito == abbonamento.giorno_addebito,
            AbbonamentoPostePay.data_creazione >= recent_threshold
        ).first()
        if existing:
            flash(f'Abbonamento simile rilevato (evitato duplicato).', 'info')
        else:
            db.session.add(abbonamento)
            db.session.commit()
        
        flash(f'Abbonamento {abbonamento.nome} aggiunto con successo!', 'success')
        
    except Exception as e:
        flash(f'Errore nell\'aggiunta dell\'abbonamento: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/aggiungi_movimento', methods=['POST'])
def aggiungi_movimento():
    """Aggiunge un movimento PostePay manuale"""
    try:
        importo = float(request.form['importo'])
        tipo = request.form['tipo']
        
        # Se è un'uscita, rendi l'importo negativo
        if tipo == 'uscita':
            importo = -abs(importo)
        else:
            importo = abs(importo)
        
        movimento = MovimentoPostePay(
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
            descrizione=request.form['descrizione'],
            importo=importo,
            tipo=request.form['tipo_movimento']
        )
        
        db.session.add(movimento)
        
        # Aggiorna saldo PostePay
        postepay = PostePayEvolution.query.first()
        if postepay:
            postepay.saldo_attuale += importo
            postepay.data_ultimo_aggiornamento = datetime.utcnow()
        
        db.session.commit()
        
        flash('Movimento aggiunto con successo!', 'success')
        
    except Exception as e:
        flash(f'Errore nell\'aggiunta del movimento: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/modifica_movimento_postepay/<int:movimento_id>', methods=['POST'])
def modifica_movimento_postepay(movimento_id):
    """Modifica un movimento PostePay esistente (aggiunge la possibilità di edit inline)."""
    try:
        movimento = MovimentoPostePay.query.get_or_404(movimento_id)
        # store old importo to update saldo
        old_importo = movimento.importo or 0.0

        # parse new values
        new_data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        new_descrizione = request.form.get('descrizione', '').strip()
        new_tipo = request.form.get('tipo_movimento', movimento.tipo)
        # importo is provided as positive; respect 'tipo' (entrata/uscita)
        raw_importo = float(request.form.get('importo', 0))
        tipo_sign = request.form.get('tipo', 'entrata')
        if tipo_sign == 'uscita':
            new_importo = -abs(raw_importo)
        else:
            new_importo = abs(raw_importo)

        # apply changes
        movimento.data = new_data
        movimento.descrizione = new_descrizione
        movimento.tipo = new_tipo
        movimento.importo = new_importo

        # update PostePay saldo by the delta
        postepay = PostePayEvolution.query.first()
        if postepay:
            delta = (new_importo or 0.0) - (old_importo or 0.0)
            postepay.saldo_attuale = (postepay.saldo_attuale or 0.0) + delta
            postepay.data_ultimo_aggiornamento = datetime.utcnow()

        db.session.commit()
        flash('Movimento modificato con successo!', 'success')
    except Exception as e:
        flash(f'Errore nella modifica del movimento: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('ppay.evolution'))


@ppay_bp.route('/reset_postepay', methods=['POST'])
def reset():
    """Reset completo sistema PostePay Evolution"""
    try:
        # Elimina tutti i dati
        MovimentoPostePay.query.delete()
        AbbonamentoPostePay.query.delete()
        PostePayEvolution.query.delete()
        
        db.session.commit()
        
        # Reinizializza
        inizializza_postepay()
        
        flash('Sistema PostePay Evolution resettato e reinizializzato!', 'success')
        
    except Exception as e:
        flash(f'Errore nel reset PostePay: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/modifica_abbonamento_postepay/<int:abbonamento_id>', methods=['POST'])
def modifica_abbonamento_postepay(abbonamento_id):
    """Modifica un abbonamento PostePay esistente (logica copiata da app.py)"""
    try:
        abbonamento = AbbonamentoPostePay.query.get_or_404(abbonamento_id)
        abbonamento.nome = request.form['nome']
        abbonamento.descrizione = request.form.get('descrizione', '')
        abbonamento.importo = float(request.form['importo'])
        abbonamento.giorno_addebito = int(request.form['giorno_addebito'])
        db.session.commit()
        flash(f'Abbonamento {abbonamento.nome} modificato con successo!', 'success')
    except Exception as e:
        flash(f'Errore nella modifica dell\'abbonamento: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('ppay.evolution'))
