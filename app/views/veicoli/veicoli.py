"""Gestione delle pagine e operazioni relative al garage (veicoli)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from datetime import datetime, timedelta, date
from app.models.Veicoli import Veicoli, AutoBolli, AutoManutenzioni, Assicurazioni
from sqlalchemy.exc import OperationalError
from sqlalchemy import inspect
from app import db

veicoli_bp = Blueprint('veicoli', __name__)


@veicoli_bp.route('/')
def garage():
    """Dashboard del garage (veicoli)."""
    try:
        current_app.logger.debug('Garage page requested')
        try:
            # marca removed; order by modello only
            veicoli = Veicoli.query.order_by(Veicoli.modello).all()
            current_app.logger.debug('Retrieved %d veicoli from DB', len(veicoli))
        except OperationalError as oe:
            current_app.logger.warning('ORM query failed, falling back to raw SQL: %s', oe)
            rows = db.session.execute(
                "SELECT id, modello, mese_scadenza_bollo, costo_finanziamento, prima_rata, numero_rate, rata_mensile FROM veicoli"
            ).fetchall()

            class VehicleProxy:
                def __init__(self, r):
                    self.id = r['id']
                    # 'marca' column removed; proxy stores only modello
                    self.modello = r['modello']
                    self.mese_scadenza_bollo = r['mese_scadenza_bollo']
                    self.costo_finanziamento = r['costo_finanziamento']
                    self.prima_rata = r['prima_rata']
                    self.numero_rate = r['numero_rate']
                    self.rata_mensile = r['rata_mensile']

                @property
                def nome_completo(self):
                    return f"{self.modello}"

                @property
                def totale_versato(self):
                    from datetime import date
                    oggi = date.today()
                    if not self.prima_rata or not self.numero_rate or not self.rata_mensile:
                        return 0.0
                    if oggi < self.prima_rata:
                        return 0.0
                    mesi_trascorsi = (oggi.year - self.prima_rata.year) * 12 + (oggi.month - self.prima_rata.month)
                    if oggi.day >= self.prima_rata.day:
                        mesi_trascorsi += 1
                    rate_pagate = min(mesi_trascorsi, self.numero_rate or 0)
                    return max(0, rate_pagate * (self.rata_mensile or 0))

                @property
                def rate_rimanenti(self):
                    from datetime import date
                    oggi = date.today()
                    if not self.prima_rata or not self.numero_rate or not self.rata_mensile:
                        return 0
                    if oggi < self.prima_rata:
                        return self.numero_rate
                    mesi_trascorsi = (oggi.year - self.prima_rata.year) * 12 + (oggi.month - self.prima_rata.month)
                    if oggi.day >= self.prima_rata.day:
                        mesi_trascorsi += 1
                    rate_pagate = min(mesi_trascorsi, self.numero_rate or 0)
                    return max(0, (self.numero_rate or 0) - rate_pagate)

                @property
                def saldo_rimanente(self):
                    return max(0, (self.costo_finanziamento or 0) - self.totale_versato)

                @property
                def bollo_scaduto(self):
                    return False

            veicoli = [VehicleProxy(r) for r in rows]


        totale_costo_finanziamento = sum((v.costo_finanziamento or 0) for v in veicoli)
        totale_versato = sum((v.totale_versato or 0) for v in veicoli)
        totale_saldo_rimanente = sum((v.saldo_rimanente or 0) for v in veicoli)

        nomi_mesi = {
            1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile',
            5: 'Maggio', 6: 'Giugno', 7: 'Luglio', 8: 'Agosto',
            9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
        }

        for veicolo in veicoli:
            try:
                veicolo.next_bollo_scadenza = None
                veicolo.next_assicurazione_scadenza = None
                if getattr(veicolo, 'tipo', None) in ('auto', 'moto'):
                    try:
                        mese = getattr(veicolo, 'mese_scadenza_bollo', None)
                        if mese:
                            oggi = datetime.now()
                            current_year = oggi.year
                            pagato_corrente = AutoBolli.query.filter_by(veicolo_id=veicolo.id, anno_riferimento=current_year).first()
                            next_year = current_year + 1 if pagato_corrente else current_year
                            try:
                                veicolo.next_bollo_scadenza = f"{nomi_mesi.get(int(mese), 'Mese '+str(mese))} {next_year}"
                            except Exception:
                                veicolo.next_bollo_scadenza = None
                    except Exception:
                        veicolo.next_bollo_scadenza = None
                    try:
                        last_ass = Assicurazioni.query.filter_by(veicolo_id=veicolo.id).order_by(Assicurazioni.data_pagamento.desc()).first()
                        if last_ass and getattr(last_ass, 'data_pagamento', None):
                            try:
                                next_ass_date = last_ass.data_pagamento.replace(year=last_ass.data_pagamento.year + 1)
                            except ValueError:
                                next_ass_date = last_ass.data_pagamento.replace(day=28, month=2, year=last_ass.data_pagamento.year + 1)
                            veicolo.next_assicurazione_scadenza = next_ass_date.strftime('%d/%m/%Y')
                        else:
                            veicolo.next_assicurazione_scadenza = None
                    except Exception:
                        current_app.logger.debug('Could not compute next expiry for veicolo id=%s', getattr(veicolo, 'id', None))
                        continue
            except Exception:
                current_app.logger.debug('Could not compute next expiry (outer) for veicolo id=%s', getattr(veicolo, 'id', None))
                continue

        ultimi_bolli = AutoBolli.query.join(Veicoli).order_by(AutoBolli.data_pagamento.desc()).limit(5).all()
        ultime_manutenzioni = AutoManutenzioni.query.join(Veicoli).order_by(AutoManutenzioni.data_intervento.desc()).limit(5).all()
        ultime_assicurazioni = Assicurazioni.query.join(Veicoli).order_by(Assicurazioni.data_pagamento.desc()).limit(5).all()

        bolli_in_attesa = []

        for veicolo in veicoli:
            try:
                if getattr(veicolo, 'tipo', None) != 'bici' and veicolo.mese_scadenza_bollo and veicolo.prima_rata:
                    oggi = datetime.now()
                    anno_corrente = oggi.year
                    mese_corrente = oggi.month
                    nome_mese_scadenza = nomi_mesi.get(veicolo.mese_scadenza_bollo, f'Mese {veicolo.mese_scadenza_bollo}')
                    primo_anno_bollo = veicolo.prima_rata.year + 1
                    for anno in range(primo_anno_bollo, anno_corrente + 1):
                        bollo_pagato = AutoBolli.query.filter_by(
                            veicolo_id=veicolo.id,
                            anno_riferimento=anno
                        ).first()
                        if not bollo_pagato:
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
            except Exception as ve_err:
                current_app.logger.exception('Error processing veicolo id=%s nome=%s', getattr(veicolo, 'id', None), getattr(veicolo, 'nome_completo', None))
                bolli_in_attesa.append({
                    'veicolo': veicolo,
                    'tipo': 'Bollo Auto',
                    'anno': None,
                    'mese_scadenza': None,
                    'priorita': 'errore',
                    'giorni': None,
                })

        current_app.logger.debug('Rendering garage template: veicoli=%d bolli=%d manutenzioni=%d', len(veicoli), len(ultimi_bolli), len(ultime_manutenzioni))
        return render_template('garage/veicoli_garage.html',
                    veicoli=veicoli,
                    totale_costo_finanziamento=totale_costo_finanziamento,
                    totale_versato=totale_versato,
                    totale_saldo_rimanente=totale_saldo_rimanente,
                    ultimi_bolli=ultimi_bolli,
                    ultime_manutenzioni=ultime_manutenzioni,
                    ultime_assicurazioni=ultime_assicurazioni,
                    bolli_in_attesa=bolli_in_attesa)
    except Exception as e:
        current_app.logger.exception('Errore nel caricamento garage')
        flash(f'Errore nel caricamento garage: {str(e)}', 'error')
        return redirect(url_for('main.index'))



@veicoli_bp.route('/dettaglio/<int:veicolo_id>')
def dettaglio(veicolo_id):
    """Dettaglio di un veicolo specifico"""
    try:
        current_app.logger.debug('caricamento dettaglio veicolo id=%s', veicolo_id)
        try:
            veicolo = Veicoli.query.get_or_404(veicolo_id)
        except OperationalError as oe:
            current_app.logger.warning('ORM query for dettaglio failed, falling back to raw SQL: %s', oe)
            row = db.session.execute("SELECT id, modello, mese_scadenza_bollo, costo_finanziamento, prima_rata, numero_rate, rata_mensile FROM veicoli WHERE id = :id", {'id': veicolo_id}).fetchone()
            if not row:
                current_app.logger.error('Veicolo id=%s non trovato in raw SQL fallback', veicolo_id)
                return redirect(url_for('veicoli.garage'))

            class VehicleProxySingle:
                def __init__(self, r):
                    self.id = r['id']
                    self.modello = r['modello']
                    self.mese_scadenza_bollo = r['mese_scadenza_bollo']
                    self.costo_finanziamento = r['costo_finanziamento']
                    self.prima_rata = r['prima_rata']
                    self.numero_rate = r['numero_rate']
                    self.rata_mensile = r['rata_mensile']

                @property
                def nome_completo(self):
                    return f"{self.modello}"

                @property
                def totale_versato(self):
                    from datetime import date
                    oggi = date.today()
                    if not self.prima_rata or not self.numero_rate or not self.rata_mensile:
                        return 0.0
                    if oggi < self.prima_rata:
                        return 0.0
                    mesi_trascorsi = (oggi.year - self.prima_rata.year) * 12 + (oggi.month - self.prima_rata.month)
                    if oggi.day >= self.prima_rata.day:
                        mesi_trascorsi += 1
                    rate_pagate = min(mesi_trascorsi, self.numero_rate or 0)
                    return max(0, rate_pagate * (self.rata_mensile or 0))

                @property
                def rate_rimanenti(self):
                    from datetime import date
                    oggi = date.today()
                    if not self.prima_rata or not self.numero_rate or not self.rata_mensile:
                        return 0
                    if oggi < self.prima_rata:
                        return self.numero_rate
                    mesi_trascorsi = (oggi.year - self.prima_rata.year) * 12 + (oggi.month - self.prima_rata.month)
                    if oggi.day >= self.prima_rata.day:
                        mesi_trascorsi += 1
                    rate_pagate = min(mesi_trascorsi, self.numero_rate or 0)
                    return max(0, (self.numero_rate or 0) - rate_pagate)

                @property
                def saldo_rimanente(self):
                    return max(0, (self.costo_finanziamento or 0) - self.totale_versato)

                @property
                def bollo_scaduto(self):
                    return False

            veicolo = VehicleProxySingle(row)

        bolli = AutoBolli.query.filter_by(veicolo_id=veicolo_id).order_by(AutoBolli.anno_riferimento.desc()).all()
        manutenzioni = AutoManutenzioni.query.filter_by(veicolo_id=veicolo_id).order_by(AutoManutenzioni.data_intervento.desc()).all()

        totale_bolli = sum(b.importo for b in bolli) if bolli else 0
        totale_manutenzioni = sum(m.costo for m in manutenzioni)
        costo_totale = (veicolo.costo_finanziamento or 0) + totale_bolli + totale_manutenzioni

        current_app.logger.debug('Rendering dettaglio veicolo id=%s nome=%s', veicolo_id, getattr(veicolo, 'nome_completo', None))
        return render_template('garage/veicoli_dettaglio.html',
                    veicolo=veicolo,
                    bolli=bolli,
                    manutenzioni=manutenzioni,
                    totale_bolli=totale_bolli,
                    totale_manutenzioni=totale_manutenzioni,
                    costo_totale=costo_totale)
    except Exception as e:
        current_app.logger.exception('Errore nel caricamento dettaglio veicolo id=%s', veicolo_id)
        flash(f'Errore nel caricamento dettaglio veicolo: {str(e)}', 'error')
        return redirect(url_for('veicoli.garage'))


@veicoli_bp.route('/aggiungi_veicolo', methods=['POST'])
def aggiungi_veicolo():
    """Aggiunge un nuovo veicoli al garage"""
    try:
        current_app.logger.debug('aggiungi_veicolo called')
        try:
            current_app.logger.debug('Form data: %s', dict(request.form))
        except Exception:
            current_app.logger.exception('Could not serialize request.form')
        tipo = (request.form.get('tipo') or 'auto').strip().lower()

        _mese_raw = request.form.get('mese_scadenza_bollo')
        if tipo == 'bici':
            mese_scadenza = None
        else:
            mese_scadenza = int(_mese_raw) if _mese_raw else 1

        try:
            inspector = inspect(db.engine)
            cols = inspector.get_columns('veicoli')
            col_info = next((c for c in cols if c['name'] == 'mese_scadenza_bollo'), None)
            if col_info and not col_info.get('nullable', True) and mese_scadenza is None:
                current_app.logger.warning('DB column mese_scadenza_bollo is NOT NULL in schema; using fallback value=1 for bici to allow insert')
                mese_scadenza = 1
        except Exception:
            current_app.logger.debug('Could not inspect veicoli table schema before insert')

        if request.form.get('prima_rata'):
            prima_rata = datetime.strptime(request.form['prima_rata'], '%Y-%m-%d').date()
        else:
            prima_rata = date.today()

        # 'marca' removed from form; use only modello
        modello = (request.form.get('modello') or '').strip()
        if not modello:
            flash('Modello è obbligatorio per aggiungere un veicoli.', 'error')
            return redirect(url_for('veicoli.garage'))

        costo = float(request.form['costo_finanziamento']) if request.form.get('costo_finanziamento') else 0.0
        numero_rate = int(request.form['numero_rate']) if request.form.get('numero_rate') else 0
        rata_mensile = float(request.form['rata_mensile']) if request.form.get('rata_mensile') else 0.0

        veicoli = Veicoli(
            modello=modello,
            tipo=tipo,
            mese_scadenza_bollo=mese_scadenza,
            costo_finanziamento=costo,
            prima_rata=prima_rata,
            numero_rate=numero_rate,
            rata_mensile=rata_mensile
        )
        current_app.logger.debug('Creating Veicoli object: modello=%s tipo=%s mese_scadenza=%s costo=%s numero_rate=%s rata=%s prima_rata=%s',
            modello, tipo, mese_scadenza, costo, numero_rate, rata_mensile, prima_rata)
        db.session.add(veicoli)
        db.session.commit()
        current_app.logger.debug('Veicoli committed with id=%s', getattr(veicoli, 'id', None))
        flash(f'Veicoli {veicoli.nome_completo} aggiunto con successo!', 'success')
    except Exception as e:
        current_app.logger.exception('Errore in aggiungi_veicolo')
        flash(f'Errore nell\'aggiunta del veicoli: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('veicoli.garage'))


@veicoli_bp.route('/aggiungi_bollo', methods=['POST'])
def aggiungi_bollo():
    """Aggiunge un pagamento del bollo"""
    try:
        bollo = AutoBolli(
            veicolo_id=int(request.form['veicolo_id']),
            anno_riferimento=int(request.form['anno_riferimento']),
            data_pagamento=datetime.strptime(request.form['data_pagamento'], '%Y-%m-%d').date(),
            importo=float(request.form['importo'])
        )
        db.session.add(bollo)
        db.session.commit()
        veicolo = Veicoli.query.get(bollo.veicolo_id)
        flash(f'Bollo per {veicolo.nome_completo} aggiunto con successo!', 'success')
        if request.form.get('redirect_to_veicolo'):
            return redirect(url_for('veicoli.dettaglio', veicolo_id=bollo.veicolo_id))
        return redirect(url_for('veicoli.garage'))
    except Exception as e:
        flash(f'Errore nell\'aggiunta del bollo: {str(e)}', 'error')
        db.session.rollback()
        return redirect(url_for('veicoli.garage'))


@veicoli_bp.route('/aggiungi_assicurazione', methods=['POST'])
def aggiungi_assicurazione():
    """Aggiunge un pagamento di assicurazione"""
    try:
        ass = Assicurazioni(
            veicolo_id=int(request.form['veicolo_id']),
            anno_riferimento=int(request.form['anno_riferimento']),
            data_pagamento=datetime.strptime(request.form['data_pagamento'], '%Y-%m-%d').date(),
            importo=float(request.form['importo']),
            compagnia=request.form.get('compagnia', '').strip() or None
        )
        db.session.add(ass)
        db.session.commit()
        veicolo = Veicoli.query.get(ass.veicolo_id)
        flash(f'Assicurazione per {veicolo.nome_completo} aggiunta con successo!', 'success')
        if request.form.get('redirect_to_veicolo'):
            return redirect(url_for('veicoli.dettaglio', veicolo_id=ass.veicolo_id))
        return redirect(url_for('veicoli.garage'))
    except Exception as e:
        flash(f'Errore nell\'aggiunta dell\'assicurazione: {str(e)}', 'error')
        db.session.rollback()
        return redirect(url_for('veicoli.garage'))


@veicoli_bp.route('/aggiungi_manutenzione', methods=['POST'])
def aggiungi_manutenzione():
    """Aggiunge un intervento di manutenzione"""
    try:
        # Log form keys for easier debugging
        try:
            current_app.logger.debug('aggiungi_manutenzione form keys: %s', list(request.form.keys()))
        except Exception:
            pass

        veicolo_id = int(request.form['veicolo_id'])
        # Accept either 'descrizione' or 'dettaglio' from the form (template uses 'dettaglio')
        descr = request.form.get('descrizione', request.form.get('dettaglio', '')).strip()

        manutenzione = AutoManutenzioni(
            veicolo_id=veicolo_id,
            data_intervento=datetime.strptime(request.form['data_intervento'], '%Y-%m-%d').date(),
            tipo_intervento=request.form['tipo_intervento'].strip(),
            descrizione=descr,
            costo=float(request.form['costo']),
            km_intervento=int(request.form['km_intervento']) if request.form.get('km_intervento') else None,
            officina=request.form.get('officina', '').strip()
        )
        db.session.add(manutenzione)
        db.session.commit()
        veicolo = Veicoli.query.get(veicolo_id)
        flash(f'Manutenzione per {veicolo.nome_completo} aggiunta con successo!', 'success')
        if request.form.get('redirect_to_veicolo'):
            return redirect(url_for('veicoli.dettaglio', veicolo_id=veicolo_id))
    except Exception as e:
        flash(f'Errore nell\'aggiunta della manutenzione: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('veicoli.garage'))


@veicoli_bp.route('/rimuovi_veicolo/<int:veicolo_id>', methods=['POST'])
def rimuovi_veicolo(veicolo_id):
    try:
        veicolo = Veicoli.query.get_or_404(veicolo_id)
        db.session.delete(veicolo)
        db.session.commit()
        flash(f'Veicolo {veicolo.nome_completo} rimosso dal garage!', 'success')
    except Exception as e:
        flash(f'Errore nella rimozione del veicolo: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('veicoli.garage'))


@veicoli_bp.route('/elimina_bollo/<int:bollo_id>', methods=['POST'])
def elimina_bollo(bollo_id):
    """Elimina un bollo"""
    try:
        bollo = AutoBolli.query.get_or_404(bollo_id)
        veicolo_id = bollo.veicolo_id
        db.session.delete(bollo)
        db.session.commit()
        flash('Bollo eliminato con successo!', 'success')
    except Exception as e:
        current_app.logger.exception('Errore nell\'eliminazione bollo id=%s: %s', bollo_id, e)
        flash(f'Errore durante l\'eliminazione del bollo: {str(e)}', 'error')
        db.session.rollback()

    # If the form requested redirect to dettaglio, go back there
    if request.form.get('redirect_to_veicolo'):
        return redirect(url_for('veicoli.dettaglio', veicolo_id=veicolo_id))
    return redirect(url_for('veicoli.garage'))


@veicoli_bp.route('/elimina_manutenzione/<int:manutenzione_id>', methods=['POST'])
def elimina_manutenzione(manutenzione_id):
    """Elimina una manutenzione"""
    try:
        m = AutoManutenzioni.query.get_or_404(manutenzione_id)
        veicolo_id = m.veicolo_id
        db.session.delete(m)
        db.session.commit()
        flash('Manutenzione eliminata con successo!', 'success')
    except Exception as e:
        current_app.logger.exception('Errore nell\'eliminazione manutenzione id=%s: %s', manutenzione_id, e)
        flash(f'Errore durante l\'eliminazione della manutenzione: {str(e)}', 'error')
        db.session.rollback()

    if request.form.get('redirect_to_veicolo'):
        return redirect(url_for('veicoli.dettaglio', veicolo_id=veicolo_id))
    return redirect(url_for('veicoli.garage'))


@veicoli_bp.route('/elimina_assicurazione/<int:assicurazione_id>', methods=['POST'])
def elimina_assicurazione(assicurazione_id):
    """Elimina una assicurazione"""
    try:
        a = Assicurazioni.query.get_or_404(assicurazione_id)
        veicolo_id = a.veicolo_id
        db.session.delete(a)
        db.session.commit()
        flash('Assicurazione eliminata con successo!', 'success')
    except Exception as e:
        current_app.logger.exception('Errore nell\'eliminazione assicurazione id=%s: %s', assicurazione_id, e)
        flash(f'Errore durante l\'eliminazione dell\'assicurazione: {str(e)}', 'error')
        db.session.rollback()

    if request.form.get('redirect_to_veicolo'):
        return redirect(url_for('veicoli.dettaglio', veicolo_id=veicolo_id))
    return redirect(url_for('veicoli.garage'))


