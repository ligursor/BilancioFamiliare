"""
Blueprint principale per le route di base
"""
from flask import Blueprint, render_template, current_app
from app.services.bilancio.transazioni_service import TransazioneService
from app.models.base import Categoria, SaldoIniziale
from app.services import get_month_boundaries, get_current_month_name
from app import db

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Dashboard principale - reimplementazione fedele all'app.py originale"""
    # Verifica se è necessario aggiornare il saldo (se è il 27 del mese)
    # TODO: implementare verifica_e_aggiorna_saldo()
    
    from datetime import datetime, date
    from dateutil.relativedelta import relativedelta
    from app.models.transazioni import Transazione
    import calendar
    
    oggi = datetime.now().date()
    
    # Calcola il saldo iniziale del periodo corrente usando la logica del dettaglio
    # (in modo da ereditare il saldo disponibile del mese precedente invece
    # che usare il valore fisso iniziale presente nel DB)
    try:
        from app.services.bilancio.dettaglio_periodo_service import DettaglioPeriodoService
        servizio_dettaglio = DettaglioPeriodoService()
        # ottieni i confini del periodo corrente
        start_date, end_date = get_month_boundaries(oggi)
        dettaglio_corrente = servizio_dettaglio.dettaglio_periodo_interno(start_date, end_date)
        saldo_iniziale_importo = float(dettaglio_corrente.get('saldo_iniziale_mese', 0.0) or 0.0)
    except Exception:
        # Fallback: usa il valore persistito in SaldoIniziale
        saldo_iniziale = SaldoIniziale.query.first()
        saldo_iniziale_importo = saldo_iniziale.importo if saldo_iniziale else 0.0
    
    # Costruisci la lista dei mesi basandoci sui record esistenti in `monthly_summary` (fino a 6)
    # Se ci sono meno di 6 mesi, completiamo la vista con placeholder vuoti.
    mesi = []
    saldo_corrente = saldo_iniziale_importo
    # Ensure ultime_transazioni is always defined to avoid UnboundLocalError
    ultime_transazioni = []

    try:
        from app.models.monthly_summary import MonthlySummary
        # Query fino a 6 mesi presenti in monthly_summary (qualsiasi periodo)
        q = db.session.query(MonthlySummary).order_by(MonthlySummary.year.asc(), MonthlySummary.month.asc()).limit(6).all()
        month_rows = q if q else None
    except Exception:
        month_rows = None

    # If we have monthly_summary rows for current/future periods, use them; otherwise fall back to projecting 6 months
    if month_rows:
        for idx, ms in enumerate(month_rows):
            from datetime import date as _date
            data_mese = _date(ms.year, ms.month, 1)
            start_date, end_date = get_month_boundaries(data_mese)
            # Calcola entrate e uscite per questo mese (transazioni effettive)
            tutte_transazioni_mese = Transazione.query.filter(
                Transazione.data >= start_date,
                Transazione.data <= end_date,
                Transazione.categoria_id.isnot(None)
            ).all()

            # Somme da transazioni effettive
            entrate_eff = 0
            uscite_eff = 0
            for t in tutte_transazioni_mese:
                if t.tipo == 'entrata':
                    entrate_eff += t.importo
                else:
                    uscite_eff += t.importo

            entrate = entrate_eff
            uscite = uscite_eff
            bilancio = entrate - uscite
            saldo_finale_mese = saldo_corrente + bilancio

            # Calcola saldo attuale per il mese corrente (considera solo transazioni già effettuate)
            saldo_attuale_mese = saldo_corrente
            if idx == 0:
                entrate_effettuate = 0
                uscite_effettuate = 0
                for t in tutte_transazioni_mese:
                    if t.data <= oggi:
                        includi = False
                        if t.ricorrente == 0:
                            includi = True
                        elif t.ricorrente == 1:
                            ha_figlie_stesso_mese = any(
                                f.transazione_madre_id == t.id and 
                                f.data.month == t.data.month and 
                                f.data.year == t.data.year
                                for f in tutte_transazioni_mese if f.ricorrente == 0 and f.transazione_madre_id
                            )
                            if not ha_figlie_stesso_mese:
                                includi = True
                        if includi:
                            if t.tipo == 'entrata':
                                entrate_effettuate += t.importo
                            else:
                                uscite_effettuate += t.importo
                saldo_attuale_mese = saldo_corrente + entrate_effettuate - uscite_effettuate

            mesi.append({
                'nome': get_current_month_name(data_mese),
                'start_date': start_date,
                'end_date': end_date,
                'anno_target': end_date.year,
                'mese_target': end_date.month,
                'entrate': entrate,
                'uscite': uscite,
                'bilancio': bilancio,
                'saldo_iniziale_mese': saldo_corrente,
                'saldo_finale_mese': saldo_finale_mese,
                'saldo_attuale_mese': saldo_attuale_mese,
                'mese_corrente': idx == 0,
                'is_placeholder': False
            })

            saldo_corrente = saldo_finale_mese

        # Pad to 6 slots with placeholders if necessary
        if len(mesi) < 6:
            needed = 6 - len(mesi)
            for _ in range(needed):
                mesi.append({
                    'nome': '',
                    'start_date': None,
                    'end_date': None,
                    'anno_target': None,
                    'mese_target': None,
                    'entrate': 0,
                    'uscite': 0,
                    'bilancio': 0,
                    'saldo_iniziale_mese': 0,
                    'saldo_finale_mese': 0,
                    'saldo_attuale_mese': 0,
                    'mese_corrente': False,
                    'is_placeholder': True
                })

        if mesi:
            periodo_corrente_start = mesi[0]['start_date']
            periodo_corrente_end = mesi[0]['end_date']
        else:
            periodo_corrente_start = oggi
            periodo_corrente_end = oggi
    else:
        # fallback: project next 6 months starting from oggi
        MESI_PROIEZIONE = 6
        for i in range(MESI_PROIEZIONE):
            data_mese = oggi + relativedelta(months=i)
            start_date, end_date = get_month_boundaries(data_mese)

            # Calcola entrate e uscite per questo mese (transazioni effettive)
            tutte_transazioni_mese = Transazione.query.filter(
                Transazione.data >= start_date,
                Transazione.data <= end_date,
                Transazione.categoria_id.isnot(None)  # Escludi transazioni PayPal (senza categoria)
            ).all()

            # Somme da transazioni effettive (ora includiamo anche le transazioni
            # generate dalla ricorrenza che sono memorizzate in `transazione` con
            # `id_recurring_tx` non nullo). Evitiamo duplicati tramite controlli
            # successivi.
            entrate_eff = 0
            uscite_eff = 0
            for t in tutte_transazioni_mese:
                includi = True
                if includi:
                    if t.tipo == 'entrata':
                        entrate_eff += t.importo
                    else:
                        uscite_eff += t.importo

            entrate = entrate_eff
            uscite = uscite_eff

            bilancio = entrate - uscite
            saldo_finale_mese = saldo_corrente + bilancio

            # Calcola saldo attuale per il mese corrente (considera solo transazioni già effettuate)
            saldo_attuale_mese = saldo_corrente
            if i == 0:  # Solo per il mese corrente
                # Filtra transazioni già effettuate (data <= oggi)
                entrate_effettuate = 0
                uscite_effettuate = 0
                for t in tutte_transazioni_mese:
                    if t.data <= oggi:  # Solo transazioni già effettuate
                        includi = False
                        if t.ricorrente == 0:  # Figlie e manuali: sempre incluse
                            includi = True
                        elif t.ricorrente == 1:  # Madri: includi solo se non hanno figlie nello stesso mese
                            ha_figlie_stesso_mese = any(
                                f.transazione_madre_id == t.id and 
                                f.data.month == t.data.month and 
                                f.data.year == t.data.year
                                for f in tutte_transazioni_mese if f.ricorrente == 0 and f.transazione_madre_id
                            )
                            if not ha_figlie_stesso_mese:
                                includi = True
                        
                        if includi:
                            if t.tipo == 'entrata':
                                entrate_effettuate += t.importo
                            else:
                                uscite_effettuate += t.importo
                
                saldo_attuale_mese = saldo_corrente + entrate_effettuate - uscite_effettuate

            mesi.append({
                'nome': get_current_month_name(data_mese),
                'start_date': start_date,
                'end_date': end_date,
                'anno_target': end_date.year,  # Usa end_date per il link corretto
                'mese_target': end_date.month,  # Usa end_date per il link corretto
                'entrate': entrate,
                'uscite': uscite,
                'bilancio': bilancio,
                'saldo_iniziale_mese': saldo_corrente,
                'saldo_finale_mese': saldo_finale_mese,
                'saldo_attuale_mese': saldo_attuale_mese,
                'mese_corrente': i == 0,
                'is_placeholder': False
            })

            # Il saldo finale di questo mese diventa il saldo iniziale del prossimo
            saldo_corrente = saldo_finale_mese

        if mesi:
            periodo_corrente_start = mesi[0]['start_date']
            periodo_corrente_end = mesi[0]['end_date']
        else:
            periodo_corrente_start = oggi
            periodo_corrente_end = oggi
        
        # Ottieni le transazioni del periodo corrente con logica corretta (escluse PayPal)
        if mesi:
            periodo_corrente_start = mesi[0]['start_date']
            periodo_corrente_end = mesi[0]['end_date']

            tutte_transazioni_periodo = Transazione.query.filter(
                Transazione.data >= periodo_corrente_start,
                Transazione.data <= periodo_corrente_end,
                Transazione.categoria_id.isnot(None)  # Escludi transazioni PayPal (senza categoria)
            ).all()
            
            # Filtra per evitare duplicazioni madri/figlie
            transazioni_filtrate = []
            for t in tutte_transazioni_periodo:
                if t.ricorrente == 0:  # Figlie e manuali: sempre incluse
                    transazioni_filtrate.append(t)
                elif t.ricorrente == 1:  # Madri: includi solo se non hanno figlie nello stesso mese
                    ha_figlie_stesso_mese = any(
                        f.transazione_madre_id == t.id and 
                        f.data.month == t.data.month and 
                        f.data.year == t.data.year
                        for f in tutte_transazioni_periodo if f.ricorrente == 0 and f.transazione_madre_id
                    )
                    if not ha_figlie_stesso_mese:
                        transazioni_filtrate.append(t)

            # Ordina le transazioni filtrate
            ultime_transazioni = sorted(transazioni_filtrate, 
                                      key=lambda x: (x.data, x.id), reverse=True)[:10]
        else:
            ultime_transazioni = []
    
    # Ottieni categorie per il modal (escludi PayPal) usando il servizio
    from app.services.categorie.categorie_service import CategorieService
    service_cat = CategorieService()
    categorie_dict = service_cat.get_categories_dict(exclude_paypal=True)
    
    return render_template('bilancio/index.html', 
                         mesi=mesi, 
                         ultime_transazioni=ultime_transazioni,
                         saldo_iniziale=saldo_iniziale_importo,
                         categorie=categorie_dict)

@main_bp.route('/saldo_iniziale')
def saldo_iniziale():
    """Gestione saldo iniziale"""
    saldo = SaldoIniziale.query.first()
    return render_template('bilancio/saldo_iniziale.html', saldo=saldo)

@main_bp.route('/saldo_iniziale/aggiorna', methods=['POST'])
def aggiorna_saldo_iniziale():
    """Aggiorna il saldo iniziale"""
    from flask import request, flash, redirect, url_for
    
    try:
        nuovo_importo = float(request.form['importo'])
        
        saldo = SaldoIniziale.query.first()
        if not saldo:
            saldo = SaldoIniziale(importo=nuovo_importo)
            from app import db
            db.session.add(saldo)
            db.session.commit()
        else:
            saldo.importo = nuovo_importo
            from app import db
            db.session.commit()
        
        flash('Saldo iniziale aggiornato con successo!', 'success')
    except Exception as e:
        flash(f'Errore nell\'aggiornamento: {str(e)}', 'error')
    
    return redirect(url_for('main.saldo_iniziale'))

@main_bp.route('/forza_rollover')
def forza_rollover():
    """Forza rollover mensile"""
    # Implementazione temporanea - in sviluppo
    from flask import flash, redirect, url_for
    flash('Funzione forza rollover - in sviluppo', 'info')
    return redirect(url_for('main.index'))


@main_bp.route('/gestione/reset', methods=['GET', 'POST'])
def reset():
    """Interfaccia per resettare il sistema: imposta saldo iniziale e rigenera transazioni/summaries."""
    from flask import request, flash, redirect, url_for, render_template
    from app.models.base import SaldoIniziale

    if request.method == 'POST':
        try:
            importo = float(request.form.get('importo', '0').strip() or 0.0)
            months = int(request.form.get('months', 6))
        except Exception as e:
            flash(f'Input non valido: {str(e)}', 'error')
            return redirect(url_for('main.reset'))

        try:
            from app.services.bilancio.reset_service import ResetService
            svc = ResetService()
            # Enforce application-wide maximum horizon of 6 months
            try:
                months = int(months)
            except Exception:
                months = 6
            if months > 6:
                months = 6

            full_wipe = bool(request.form.get('full_wipe'))
            ok, res = svc.reset_horizon(importo, months=months, full_wipe=full_wipe)
            if ok:
                extra = ' (full wipe)' if full_wipe else ''
                flash(f'Reset eseguito{extra}: saldo impostato a €{importo:.2f}. Transazioni rigenerate: {res.get("created_generated_transactions",0)}. Summaries rigenerati: {res.get("monthly_summary_regenerated",0)}', 'success')
            else:
                flash(f'Errore durante reset: {res}', 'error')
        except Exception as e:
            flash(f'Errore interno durante reset: {str(e)}', 'error')

        return redirect(url_for('main.index'))

    # GET -> mostra form
    saldo = SaldoIniziale.query.first()
    return render_template('bilancio/reset.html', saldo=saldo)

# Route rimossa - gestita dal blueprint dettaglio_periodo
