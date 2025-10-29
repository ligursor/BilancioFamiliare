"""
Blueprint principale per le route di base
"""
from flask import Blueprint, render_template, current_app
from app.services.transazioni_service import TransazioneService
from app.models.base import Categoria, SaldoIniziale
from app.services import get_month_boundaries, get_current_month_name

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
        from app.services.dettaglio_periodo_service import DettaglioPeriodoService
        servizio_dettaglio = DettaglioPeriodoService()
        # ottieni i confini del periodo corrente
        start_date, end_date = get_month_boundaries(oggi)
        dettaglio_corrente = servizio_dettaglio.dettaglio_periodo_interno(start_date, end_date)
        saldo_iniziale_importo = float(dettaglio_corrente.get('saldo_iniziale_mese', 0.0) or 0.0)
    except Exception:
        # Fallback: usa il valore persistito in SaldoIniziale
        saldo_iniziale = SaldoIniziale.query.first()
        saldo_iniziale_importo = saldo_iniziale.importo if saldo_iniziale else 0.0
    
    # Calcola i prossimi N mesi usando il servizio centrale di dettaglio
    mesi = []
    # Usa il valore di configurazione o default a 6
    MESI_PROIEZIONE = 6

    for i in range(MESI_PROIEZIONE):
        data_mese = oggi + relativedelta(months=i)
        start_date, end_date = get_month_boundaries(data_mese)

        # Usa il servizio centrale per calcolare il dettaglio del mese
        try:
            dettaglio = servizio_dettaglio.dettaglio_periodo_interno(start_date, end_date)
            entrate = float(dettaglio.get('entrate', 0.0) or 0.0)
            uscite = float(dettaglio.get('uscite', 0.0) or 0.0)
            bilancio = float(dettaglio.get('bilancio', 0.0) or 0.0)
            saldo_iniziale_mese = float(dettaglio.get('saldo_iniziale_mese', 0.0) or 0.0)
            saldo_finale_mese = float(dettaglio.get('saldo_finale_mese', 0.0) or 0.0)
            saldo_attuale_mese = float(dettaglio.get('saldo_attuale_mese', 0.0) or 0.0)
        except Exception:
            # In caso di errore, fallback a zeri per non rompere la dashboard
            entrate = uscite = bilancio = saldo_iniziale_mese = saldo_finale_mese = saldo_attuale_mese = 0.0

        mesi.append({
            'nome': get_current_month_name(data_mese),
            'start_date': start_date,
            'end_date': end_date,
            'anno_target': end_date.year,
            'mese_target': end_date.month,
            'entrate': entrate,
            'uscite': uscite,
            'bilancio': bilancio,
            'saldo_iniziale_mese': saldo_iniziale_mese,
            'saldo_finale_mese': saldo_finale_mese,
            'saldo_attuale_mese': saldo_attuale_mese,
            # Non selezionare/ evidenziare alcun mese di default nella dashboard
            'mese_corrente': False
        })
    
    # Ottieni le transazioni del periodo corrente (primo elemento di mesi)
    if mesi:
        periodo_corrente_start = mesi[0]['start_date']
        periodo_corrente_end = mesi[0]['end_date']
        
        # Ottieni le transazioni del periodo corrente con logica corretta (escluse PayPal)
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
    from app.services.categorie_service import CategorieService
    service_cat = CategorieService()
    categorie_dict = service_cat.get_categories_dict(exclude_paypal=True)
    
    return render_template('index.html', 
                         mesi=mesi, 
                         ultime_transazioni=ultime_transazioni,
                         saldo_iniziale=saldo_iniziale_importo,
                         categorie=categorie_dict)

# Route and management UI for 'saldo_iniziale' removed from the main menu.
# The template and explicit management routes were intentionally removed
# to avoid manual edits to the persisted initial balance. The data model
# (`SaldoIniziale`) remains in case it's needed programmatically; any updates
# should now be performed via the application logic / administrative scripts.

@main_bp.route('/forza_rollover')
def forza_rollover():
    """Forza rollover mensile"""
    # Implementazione temporanea - in sviluppo
    from flask import flash, redirect, url_for
    flash('Funzione forza rollover - in sviluppo', 'info')
    return redirect(url_for('main.index'))

# Route rimossa - gestita dal blueprint dettaglio_periodo
