"""Gestione dei piani e movimenti PayPal."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime, timedelta
from app.models.Paypal import PaypalAbbonamenti, PaypalMovimenti
from app.models.Transazioni import Transazioni
from app import db
from app.utils.formatting import format_currency

paypal_bp = Blueprint('paypal', __name__)

def aggiorna_importi_rimanenti_paypal():
    """Aggiorna gli importi rimanenti per tutti i piani PayPal attivi"""
    # Include both possible active states ('attivo' legacy and 'in_corso' used elsewhere)
    piani = PaypalAbbonamenti.query.filter(PaypalAbbonamenti.stato.in_(['attivo', 'in_corso'])).all()
    
    for piano in piani:
        rate_non_pagate = PaypalMovimenti.query.filter_by(
            piano_id=piano.id,
            stato='in_attesa'
        ).all()
        # Se alcune rate in_attesa sono in realtà già collegate a una transazioni o hanno data_pagamento,
        # consideriamole pagate e sincronizziamo lo stato per coerenza.
        for rata in list(rate_non_pagate):
            try:
                # Consider a rate paid only when it has an explicit payment date
                if rata.data_pagamento is not None:
                    rata.stato = 'pagata'
                    # data_pagamento already present
                    piano.importo_rimanente = (piano.importo_rimanente or 0.0) - (rata.importo or 0.0)
                    rate_non_pagate.remove(rata)
                else:
                    # Se la rata è scaduta oggi (o prima) e non ha transazioni collegata,
                    # proviamo prima a trovare una Transazioni con importo e data corrispondenti;
                    # se non troviamo una transazioni, consideriamo la rata come pagata automaticamente
                    try:
                        oggi = datetime.now().date()
                        # Only consider unlinked/unpaid rates
                        if rata.data_scadenza <= oggi and rata.data_pagamento is None:
                            from app.models.Transazioni import Transazioni
                            trans = Transazioni.query.filter(
                                ((Transazioni.data == rata.data_scadenza) | (Transazioni.data_effettiva == rata.data_scadenza)),
                                ).all()
                            match = None
                            for t in trans:
                                try:
                                    if abs((t.importo or 0.0) - (rata.importo or 0.0)) < 0.01:
                                        match = t
                                        break
                                except Exception:
                                    continue
                            if match:
                                # Se esiste una transazioni corrispondente, colleghiamola e marchiamo pagata
                                # Mark the rate as paid using the transaction date but do NOT link IDs
                                rata.stato = 'pagata'
                                rata.data_pagamento = match.data_effettiva or match.data
                                piano.importo_rimanente = (piano.importo_rimanente or 0.0) - (rata.importo or 0.0)
                                rate_non_pagate.remove(rata)
                            else:
                                # Nessuna transazioni trovata: consideriamo la rata come pagata alla scadenza
                                rata.stato = 'pagata'
                                rata.data_pagamento = rata.data_scadenza
                                try:
                                    piano.importo_rimanente = (piano.importo_rimanente or 0.0) - (rata.importo or 0.0)
                                except Exception:
                                    pass
                                rate_non_pagate.remove(rata)
                    except Exception:
                        pass
            except Exception:
                # Non blocchiamo l'aggiornamento globale per singoli errori
                pass

        importo_rimanente = sum(rata.importo for rata in rate_non_pagate)
        piano.importo_rimanente = importo_rimanente
        
        # Se non ci sono più rate da pagare, imposta il piano come completato
        if importo_rimanente == 0:
            piano.stato = 'completato'
    
    db.session.commit()

@paypal_bp.route('/')
def dashboard():
    """Mostra la dashboard dei piani PayPal e relative statistiche."""
    try:
        # Aggiorna gli importi rimanenti prima di visualizzare i dati
        aggiorna_importi_rimanenti_paypal()
        # Ricarica i piani dopo la commit per avere lo stato aggiornato
        piani = PaypalAbbonamenti.query.order_by(PaypalAbbonamenti.data_creazione.desc()).all()
        totale_piani = len(piani)
        # Conta come attivi solo quelli con stato 'in_corso'
        piani_attivi = len([p for p in piani if p.stato == 'in_corso'])

        # Ordina i piani in corso a partire dalla scadenza più prossima delle loro rate non pagate
        from datetime import date as _date

        def _next_due_date_for(piano):
            # trova la data_scadenza minima per le rate con stato 'in_attesa'
            dates = [r.data_scadenza for r in (piano.rate or []) if getattr(r, 'stato', None) == 'in_attesa']
            if not dates:
                return None
            try:
                return min(dates)
            except Exception:
                return None

        # sort: active plans (stato == 'in_corso') first, ordered by next due date asc (None goes last),
        # then the rest by creation desc
        FAR_FUTURE = _date(9999, 12, 31)

        def _sort_key(p):
            active_flag = 0 if p.stato == 'in_corso' else 1
            nd = _next_due_date_for(p)
            nd_sort = nd if nd is not None else FAR_FUTURE
            # use creation desc as tiebreaker (more recent first -> negative timestamp)
            try:
                created_ts = p.data_creazione.timestamp() if getattr(p, 'data_creazione', None) else 0
            except Exception:
                created_ts = 0
            return (active_flag, nd_sort, -created_ts)

        piani = sorted(piani, key=_sort_key)

        # Calcola importo rimanente: somma degli importi delle rate non pagate di tutti i piani
        importo_rimanente_totale = 0
        rate_non_pagate_totali = 0

        for piano in piani:
            for rata in piano.rate:
                if rata.stato == 'in_attesa':
                    importo_rimanente_totale += rata.importo
                    rate_non_pagate_totali += 1

        # Prossime rate in scadenza (prossimi 30 giorni)
        oggi = datetime.now().date()
        prossimo_mese = oggi + timedelta(days=30)

        rate_in_scadenza = PaypalMovimenti.query.join(PaypalAbbonamenti).filter(
            PaypalMovimenti.stato == 'in_attesa',
            PaypalMovimenti.data_scadenza >= oggi,
            PaypalMovimenti.data_scadenza <= prossimo_mese
        ).order_by(PaypalMovimenti.data_scadenza).all()

        return render_template('paypal/paypal_dashboard.html',
                               piani=piani,
                               totale_piani=totale_piani,
                               piani_attivi=piani_attivi,
                               importo_rimanente_totale=importo_rimanente_totale,
                               rate_non_pagate_totali=rate_non_pagate_totali,
                               rate_in_scadenza=rate_in_scadenza)

    except Exception as e:
        # Log the full exception so the real cause is visible in the server logs
        try:
            current_app.logger.exception('Errore durante il caricamento della dashboard PayPal')
        except Exception:
            pass
        flash(f'Errore nel caricamento dashboard PayPal: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@paypal_bp.route('/_debug_update')
def _debug_update():
    """Esegue l'aggiornamento PayPal e restituisce lo stato (endpoint di debug)."""
    try:
        aggiorna_importi_rimanenti_paypal()
        return jsonify({'status': 'ok'})
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        # Also log it server-side
        try:
            current_app.logger.exception('Exception from _debug_update')
        except Exception:
            pass
        return jsonify({'status': 'error', 'error': str(e), 'trace': trace}), 500


@paypal_bp.route('/piano/<int:piano_id>')
def dettaglio(piano_id):
    """Mostra il dettaglio di un piano PayPal."""
    try:
        piano = PaypalAbbonamenti.query.get_or_404(piano_id)
        # carica le rate associate ordinandole per numero
        rate = sorted(piano.rate or [], key=lambda r: getattr(r, 'numero_rata', 0))
        return render_template('paypal/paypal_dettaglio.html', piano=piano, rate=rate)
    except Exception as e:
        try:
            current_app.logger.exception('Errore nel dettaglio piano PayPal')
        except Exception:
            pass
        flash(f'Impossibile caricare il dettaglio del piano: {str(e)}', 'error')
        return redirect(url_for('paypal.dashboard'))

@paypal_bp.route('/nuovo', methods=['GET', 'POST'])
def nuovo():
    """Crea un nuovo piano PayPal."""
    if request.method == 'POST':
        try:
            descrizione = request.form.get('descrizione', '').strip().upper()
            importo_totale = float(request.form.get('importo_totale', 0))
            data_prima_rata_str = request.form.get('data_prima_rata', '')
            
            if not descrizione:
                flash('La descrizione è obbligatoria', 'error')
                return render_template('paypal/paypal_nuovo.html')
            
            if importo_totale <= 0:
                flash('L\'importo totale deve essere maggiore di zero', 'error')
                return render_template('paypal/paypal_nuovo.html')
            
            # Parsing della data
            data_prima_rata = datetime.strptime(data_prima_rata_str, '%Y-%m-%d').date()
            
            # Calcola le date delle rate successive
            data_seconda_rata = data_prima_rata + timedelta(days=30)
            data_terza_rata = data_seconda_rata + timedelta(days=30)
            
            # Calcola l'importo per rata
            importo_rata = round(importo_totale / 3, 2)
            
            # Crea il piano
            piano = PaypalAbbonamenti(
                descrizione=descrizione,
                importo_totale=importo_totale,
                importo_rata=importo_rata,
                data_prima_rata=data_prima_rata,
                data_seconda_rata=data_seconda_rata,
                data_terza_rata=data_terza_rata,
                importo_rimanente=importo_totale,
                stato='in_corso',
                note=request.form.get('note', '').strip()
            )
            
            db.session.add(piano)
            db.session.flush()  # Per ottenere l'ID del piano
            
            # Crea le tre rate
            rate = [
                PaypalMovimenti(piano_id=piano.id, numero_rata=1, importo=importo_rata, data_scadenza=data_prima_rata),
                PaypalMovimenti(piano_id=piano.id, numero_rata=2, importo=importo_rata, data_scadenza=data_seconda_rata),
                PaypalMovimenti(piano_id=piano.id, numero_rata=3, importo=importo_rata, data_scadenza=data_terza_rata)
            ]
            
            for rata in rate:
                db.session.add(rata)
            db.session.flush()
            # Imposta la prima rata come pagata
            prima_rata = rate[0]
            prima_rata.stato = 'pagata'
            prima_rata.data_pagamento = datetime.now().date()
            piano.importo_rimanente -= prima_rata.importo
            db.session.commit()
            
            flash(f'Piano PayPal "{descrizione}" creato con successo!', 'success')
            return redirect(url_for('paypal.dashboard'))
            
        except ValueError:
            flash('Importo non valido', 'error')
        except Exception as e:
            flash(f'Errore nella creazione del piano: {str(e)}', 'error')
            db.session.rollback()
    
    return render_template('paypal/paypal_nuovo.html')

# La gestione dei dettagli è stata centralizzata nella dashboard o nella pagina di modifica.

@paypal_bp.route('/rata/<int:rata_id>/paga', methods=['POST'])
def paga_rata(rata_id):
    """Segna una rata come pagata"""
    try:
        rata = PaypalMovimenti.query.get_or_404(rata_id)
        
        if rata.stato == 'pagata':
            flash('Questa rata è già stata pagata', 'warning')
            return redirect(url_for('paypal.dashboard'))
        
        # Segna la rata come pagata
        rata.stato = 'pagata'
        rata.data_pagamento = datetime.now().date()
        
        # Aggiorna l'importo rimanente del piano
        rata.piano.importo_rimanente -= rata.importo
        
        # Se tutte le rate sono pagate, segna il piano come completato
        rate_rimanenti = PaypalMovimenti.query.filter_by(
            piano_id=rata.piano.id,
            stato='in_attesa'
        ).count()
        
        if rate_rimanenti == 0:
            rata.piano.stato = 'completato'
        
        db.session.commit()
        
        flash(f'Rata di {format_currency(rata.importo)} segnata come pagata!', 'success')
        
    except Exception as e:
        flash(f'Errore nel pagamento della rata: {str(e)}', 'error')
    
    return redirect(url_for('paypal.dashboard'))

@paypal_bp.route('/piano/<int:piano_id>/modifica', methods=['GET', 'POST'])
def modifica(piano_id):
    """Modifica un piano PayPal"""
    piano = PaypalAbbonamenti.query.get_or_404(piano_id)
    
    if request.method == 'POST':
        try:
            piano.descrizione = request.form['descrizione'].upper()
            piano.note = request.form.get('note', '')
            # piano.stato non viene più modificato dall'utente
            piano.data_aggiornamento = datetime.utcnow()
            
            db.session.commit()
            flash(f'Piano "{piano.descrizione}" aggiornato con successo!', 'success')
            return redirect(url_for('paypal.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante la modifica: {str(e)}', 'error')
    
    return render_template('paypal/paypal_modifica.html', piano=piano)

@paypal_bp.route('/piano/<int:piano_id>/elimina', methods=['POST'])
def elimina(piano_id):
    """Elimina un piano PayPal"""
    piano = PaypalAbbonamenti.query.get_or_404(piano_id)
    try:
        descrizione = piano.descrizione
        db.session.delete(piano)
        db.session.commit()
        flash(f'Piano "{descrizione}" eliminato con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'eliminazione: {str(e)}', 'error')
    
    return redirect(url_for('paypal.dashboard'))
