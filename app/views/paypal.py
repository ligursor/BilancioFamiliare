"""
Blueprint per la gestione PayPal
Replica l'implementazione originale da app.py
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
from app.models.paypal import PaypalPiano, PaypalRata
from app.models.transazioni import Transazione
from app import db

paypal_bp = Blueprint('paypal', __name__)

def aggiorna_importi_rimanenti_paypal():
    """Aggiorna gli importi rimanenti per tutti i piani PayPal attivi"""
    piani = PaypalPiano.query.filter_by(stato='attivo').all()
    
    for piano in piani:
        rate_non_pagate = PaypalRata.query.filter_by(
            piano_id=piano.id,
            stato='in_attesa'
        ).all()
        
        importo_rimanente = sum(rata.importo for rata in rate_non_pagate)
        piano.importo_rimanente = importo_rimanente
        
        # Se non ci sono più rate da pagare, imposta il piano come completato
        if importo_rimanente == 0:
            piano.stato = 'completato'
    
    db.session.commit()

@paypal_bp.route('/')
def dashboard():
    """Dashboard per la gestione dei piani PayPal - replica dell'implementazione originale"""
    try:
        # Aggiorna gli importi rimanenti prima di visualizzare i dati
        aggiorna_importi_rimanenti_paypal()
        # Ricarica i piani dopo la commit per avere lo stato aggiornato
        piani = PaypalPiano.query.order_by(PaypalPiano.data_creazione.desc()).all()
        totale_piani = len(piani)
        # Conta come attivi solo quelli con stato 'in_corso'
        piani_attivi = len([p for p in piani if p.stato == 'in_corso'])
        
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
        
        rate_in_scadenza = PaypalRata.query.join(PaypalPiano).filter(
            PaypalRata.stato == 'in_attesa',
            PaypalRata.data_scadenza >= oggi,
            PaypalRata.data_scadenza <= prossimo_mese
        ).order_by(PaypalRata.data_scadenza).all()
        
        return render_template('paypal_dashboard.html', 
                             piani=piani, 
                             totale_piani=totale_piani,
                             piani_attivi=piani_attivi,
                             importo_rimanente_totale=importo_rimanente_totale,
                             rate_non_pagate_totali=rate_non_pagate_totali,
                             rate_in_scadenza=rate_in_scadenza)
        
    except Exception as e:
        flash(f'Errore nel caricamento dashboard PayPal: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@paypal_bp.route('/nuovo', methods=['GET', 'POST'])
def nuovo():
    """Crea un nuovo piano PayPal"""
    if request.method == 'POST':
        try:
            descrizione = request.form.get('descrizione', '').strip().upper()
            importo_totale = float(request.form.get('importo_totale', 0))
            data_prima_rata_str = request.form.get('data_prima_rata', '')
            
            if not descrizione:
                flash('La descrizione è obbligatoria', 'error')
                return render_template('paypal_nuovo.html')
            
            if importo_totale <= 0:
                flash('L\'importo totale deve essere maggiore di zero', 'error')
                return render_template('paypal_nuovo.html')
            
            # Parsing della data
            data_prima_rata = datetime.strptime(data_prima_rata_str, '%Y-%m-%d').date()
            
            # Calcola le date delle rate successive
            data_seconda_rata = data_prima_rata + timedelta(days=30)
            data_terza_rata = data_seconda_rata + timedelta(days=30)
            
            # Calcola l'importo per rata
            importo_rata = round(importo_totale / 3, 2)
            
            # Crea il piano
            piano = PaypalPiano(
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
                PaypalRata(piano_id=piano.id, numero_rata=1, importo=importo_rata, data_scadenza=data_prima_rata),
                PaypalRata(piano_id=piano.id, numero_rata=2, importo=importo_rata, data_scadenza=data_seconda_rata),
                PaypalRata(piano_id=piano.id, numero_rata=3, importo=importo_rata, data_scadenza=data_terza_rata)
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
    
    return render_template('paypal_nuovo.html')

@paypal_bp.route('/piano/<int:piano_id>')
def dettaglio(piano_id):
    """Dettaglio di un piano PayPal"""
    try:
        piano = PaypalPiano.query.get_or_404(piano_id)
        rate = PaypalRata.query.filter_by(piano_id=piano_id).order_by(PaypalRata.numero_rata).all()
        return render_template('paypal_dettaglio.html', piano=piano, rate=rate)
    except Exception as e:
        flash(f'Errore nel caricamento piano: {str(e)}', 'error')
        return redirect(url_for('paypal.dashboard'))

@paypal_bp.route('/rata/<int:rata_id>/paga', methods=['POST'])
def paga_rata(rata_id):
    """Segna una rata come pagata"""
    try:
        rata = PaypalRata.query.get_or_404(rata_id)
        
        if rata.stato == 'pagata':
            flash('Questa rata è già stata pagata', 'warning')
            return redirect(url_for('paypal.dashboard'))
        
        # Segna la rata come pagata
        rata.stato = 'pagata'
        rata.data_pagamento = datetime.now().date()
        
        # Aggiorna l'importo rimanente del piano
        rata.piano.importo_rimanente -= rata.importo
        
        # Se tutte le rate sono pagate, segna il piano come completato
        rate_rimanenti = PaypalRata.query.filter_by(
            piano_id=rata.piano.id,
            stato='in_attesa'
        ).count()
        
        if rate_rimanenti == 0:
            rata.piano.stato = 'completato'
        
        db.session.commit()
        
        flash(f'Rata di €{rata.importo:.2f} segnata come pagata!', 'success')
        
    except Exception as e:
        flash(f'Errore nel pagamento della rata: {str(e)}', 'error')
    
    return redirect(url_for('paypal.dashboard'))

@paypal_bp.route('/piano/<int:piano_id>/modifica', methods=['GET', 'POST'])
def modifica(piano_id):
    """Modifica un piano PayPal"""
    piano = PaypalPiano.query.get_or_404(piano_id)
    
    if request.method == 'POST':
        try:
            piano.descrizione = request.form['descrizione'].upper()
            piano.note = request.form.get('note', '')
            # piano.stato non viene più modificato dall'utente
            piano.data_aggiornamento = datetime.utcnow()
            
            db.session.commit()
            flash(f'Piano "{piano.descrizione}" aggiornato con successo!', 'success')
            return redirect(url_for('paypal.dettaglio', piano_id=piano_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante la modifica: {str(e)}', 'error')
    
    return render_template('paypal_modifica.html', piano=piano)

@paypal_bp.route('/piano/<int:piano_id>/elimina')
def elimina(piano_id):
    """Elimina un piano PayPal"""
    piano = PaypalPiano.query.get_or_404(piano_id)
    try:
        descrizione = piano.descrizione
        db.session.delete(piano)
        db.session.commit()
        flash(f'Piano "{descrizione}" eliminato con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'eliminazione: {str(e)}', 'error')
    
    return redirect(url_for('paypal.dashboard'))
