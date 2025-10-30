"""
Blueprint per la gestione del garage (solo auto)
Questa versione ripristina il comportamento originale: template `auto_garage.html` e nessun supporto per `tipo_veicolo`.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from datetime import datetime, timedelta, date
from app.models.garage import Veicolo, BolloAuto, ManutenzioneAuto
from app import db

auto_bp = Blueprint('auto', __name__)


@auto_bp.route('/')
def garage():
    """Dashboard del garage (auto solamente)"""
    try:
        veicoli = Veicolo.query.order_by(Veicolo.marca, Veicolo.modello).all()

        totale_costo_finanziamento = sum((v.costo_finanziamento or 0) for v in veicoli)
        totale_versato = sum((v.totale_versato or 0) for v in veicoli)
        totale_saldo_rimanente = sum((v.saldo_rimanente or 0) for v in veicoli)

        # Ultimi bolli e manutenzioni
        ultimi_bolli = BolloAuto.query.join(Veicolo).order_by(BolloAuto.data_pagamento.desc()).limit(5).all()
        ultime_manutenzioni = ManutenzioneAuto.query.join(Veicolo).order_by(ManutenzioneAuto.data_intervento.desc()).limit(5).all()

        bolli_in_attesa = []
        nomi_mesi = {
            1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile',
            5: 'Maggio', 6: 'Giugno', 7: 'Luglio', 8: 'Agosto',
            9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
        }

        for veicolo in veicoli:
            if veicolo.mese_scadenza_bollo and veicolo.prima_rata:
                oggi = datetime.now()
                anno_corrente = oggi.year
                mese_corrente = oggi.month
                nome_mese_scadenza = nomi_mesi.get(veicolo.mese_scadenza_bollo, f'Mese {veicolo.mese_scadenza_bollo}')
                primo_anno_bollo = veicolo.prima_rata.year + 1
                for anno in range(primo_anno_bollo, anno_corrente + 1):
                    bollo_pagato = BolloAuto.query.filter_by(
                        veicolo_id=veicolo.id,
                        anno_riferimento=anno
                    ).first()
                    if not bollo_pagato:
                        # Calcolo ultimo giorno del mese di scadenza
                        ultimo_giorno = datetime(anno, veicolo.mese_scadenza_bollo, 28) + timedelta(days=4)
                        ultimo_giorno = ultimo_giorno - timedelta(days=ultimo_giorno.day)
                        giorni = (ultimo_giorno.date() - oggi.date()).days
                        if anno == anno_corrente:
                            if mese_corrente > veicolo.mese_scadenza_bollo:
                                priorita = 'alta'
                            elif mese_corrente == veicolo.mese_scadenza_bollo:
                                priorita = 'media'
                            else:
                                priorita = 'bassa'
                        else:
                            priorita = 'alta'
                        bolli_in_attesa.append({
                            'veicolo': veicolo,
                            'tipo': 'Bollo Auto',
                            'anno': anno,
                            'mese_scadenza': nome_mese_scadenza,
                            'priorita': priorita,
                            'giorni': giorni
                        })

        return render_template('garage/auto_garage.html',
                               veicoli=veicoli,
                               totale_costo_finanziamento=totale_costo_finanziamento,
                               totale_versato=totale_versato,
                               totale_saldo_rimanente=totale_saldo_rimanente,
                               ultimi_bolli=ultimi_bolli,
                               ultime_manutenzioni=ultime_manutenzioni,
                               bolli_in_attesa=bolli_in_attesa,
                               formato_valuta=current_app.config['FORMATO_VALUTA'])
    except Exception as e:
        flash(f'Errore nel caricamento garage: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@auto_bp.route('/dettaglio/<int:veicolo_id>')
def dettaglio(veicolo_id):
    """Dettaglio di un veicolo specifico"""
    try:
        veicolo = Veicolo.query.get_or_404(veicolo_id)

        bolli = BolloAuto.query.filter_by(veicolo_id=veicolo_id).order_by(BolloAuto.anno_riferimento.desc()).all()
        manutenzioni = ManutenzioneAuto.query.filter_by(veicolo_id=veicolo_id).order_by(ManutenzioneAuto.data_intervento.desc()).all()

        totale_bolli = sum(b.importo for b in bolli) if bolli else 0
        totale_manutenzioni = sum(m.costo for m in manutenzioni)
        costo_totale = (veicolo.costo_finanziamento or 0) + totale_bolli + totale_manutenzioni

        return render_template('garage/auto_dettaglio.html',
                               veicolo=veicolo,
                               bolli=bolli,
                               manutenzioni=manutenzioni,
                               totale_bolli=totale_bolli,
                               totale_manutenzioni=totale_manutenzioni,
                               costo_totale=costo_totale,
                               formato_valuta=current_app.config['FORMATO_VALUTA'])
    except Exception as e:
        flash(f'Errore nel caricamento dettaglio veicolo: {str(e)}', 'error')
        return redirect(url_for('auto.garage'))


@auto_bp.route('/aggiungi_veicolo', methods=['POST'])
def aggiungi_veicolo():
    """Aggiunge un nuovo veicolo al garage (solo auto)"""
    try:
        mese_scadenza = request.form.get('mese_scadenza_bollo')
        mese_scadenza = int(mese_scadenza) if mese_scadenza else 1

        if request.form.get('prima_rata'):
            prima_rata = datetime.strptime(request.form['prima_rata'], '%Y-%m-%d').date()
        else:
            prima_rata = date.today()

        marca = (request.form.get('marca') or '').strip()
        modello = (request.form.get('modello') or '').strip()
        if not marca or not modello:
            flash('Marca e Modello sono obbligatori per aggiungere un veicolo.', 'error')
            return redirect(url_for('auto.garage'))

        costo = float(request.form['costo_finanziamento']) if request.form.get('costo_finanziamento') else 0.0
        numero_rate = int(request.form['numero_rate']) if request.form.get('numero_rate') else 0
        rata_mensile = float(request.form['rata_mensile']) if request.form.get('rata_mensile') else 0.0

        veicolo = Veicolo(
            marca=marca,
            modello=modello,
            mese_scadenza_bollo=mese_scadenza,
            costo_finanziamento=costo,
            prima_rata=prima_rata,
            numero_rate=numero_rate,
            rata_mensile=rata_mensile
        )

        db.session.add(veicolo)
        db.session.commit()
        flash(f'Veicolo {veicolo.nome_completo} aggiunto con successo!', 'success')
    except Exception as e:
        flash(f'Errore nell\'aggiunta del veicolo: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('auto.garage'))


@auto_bp.route('/aggiungi_bollo', methods=['POST'])
def aggiungi_bollo():
    """Aggiunge un pagamento del bollo auto"""
    try:
        bollo = BolloAuto(
            veicolo_id=int(request.form['veicolo_id']),
            anno_riferimento=int(request.form['anno_riferimento']),
            data_pagamento=datetime.strptime(request.form['data_pagamento'], '%Y-%m-%d').date(),
            importo=float(request.form['importo'])
        )
        db.session.add(bollo)
        db.session.commit()
        veicolo = Veicolo.query.get(bollo.veicolo_id)
        flash(f'Bollo per {veicolo.nome_completo} aggiunto con successo!', 'success')
        if request.form.get('redirect_to_veicolo'):
            return redirect(url_for('auto.dettaglio', veicolo_id=bollo.veicolo_id))
    except Exception as e:
        flash(f'Errore nell\'aggiunta del bollo: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('auto.garage'))


@auto_bp.route('/aggiungi_manutenzione', methods=['POST'])
def aggiungi_manutenzione():
    """Aggiunge un intervento di manutenzione"""
    try:
        veicolo_id = int(request.form['veicolo_id'])
        manutenzione = ManutenzioneAuto(
            veicolo_id=veicolo_id,
            data_intervento=datetime.strptime(request.form['data_intervento'], '%Y-%m-%d').date(),
            tipo_intervento=request.form['tipo_intervento'].strip(),
            descrizione=request.form.get('descrizione', '').strip(),
            costo=float(request.form['costo']),
            km_intervento=int(request.form['km_intervento']) if request.form.get('km_intervento') else None,
            officina=request.form.get('officina', '').strip()
        )
        db.session.add(manutenzione)
        db.session.commit()
        veicolo = Veicolo.query.get(veicolo_id)
        flash(f'Manutenzione per {veicolo.nome_completo} aggiunta con successo!', 'success')
        if request.form.get('redirect_to_veicolo'):
            return redirect(url_for('auto.dettaglio', veicolo_id=veicolo_id))
    except Exception as e:
        flash(f'Errore nell\'aggiunta della manutenzione: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('auto.garage'))


@auto_bp.route('/rimuovi_veicolo/<int:veicolo_id>', methods=['POST'])
def rimuovi_veicolo(veicolo_id):
    try:
        veicolo = Veicolo.query.get_or_404(veicolo_id)
        db.session.delete(veicolo)
        db.session.commit()
        flash(f'Veicolo {veicolo.nome_completo} rimosso dal garage!', 'success')
    except Exception as e:
        flash(f'Errore nella rimozione del veicolo: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('auto.garage'))


@auto_bp.route('/modifica_veicolo/<int:veicolo_id>', methods=['POST'])
def modifica_veicolo(veicolo_id):
    try:
        veicolo = Veicolo.query.get_or_404(veicolo_id)
        mese_scadenza = request.form.get('mese_scadenza_bollo')
        if mese_scadenza:
            veicolo.mese_scadenza_bollo = int(mese_scadenza)
        if request.form.get('prima_rata'):
            veicolo.prima_rata = datetime.strptime(request.form['prima_rata'], '%Y-%m-%d').date()
        veicolo.marca = request.form['marca'].strip()
        veicolo.modello = request.form['modello'].strip()
        veicolo.costo_finanziamento = float(request.form['costo_finanziamento']) if request.form.get('costo_finanziamento') else 0.0
        veicolo.numero_rate = int(request.form['numero_rate']) if request.form.get('numero_rate') else 0
        veicolo.rata_mensile = float(request.form['rata_mensile']) if request.form.get('rata_mensile') else 0.0
        db.session.commit()
        flash(f'Dati di {veicolo.nome_completo} aggiornati con successo!', 'success')
    except Exception as e:
        flash(f'Errore nella modifica del veicolo: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('auto.dettaglio', veicolo_id=veicolo_id))
