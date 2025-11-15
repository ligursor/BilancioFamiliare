"""Blueprint per lo storico delle transazioni archiviate"""
from flask import Blueprint, render_template, request
from app.models.TransazioniArchivio import TransazioniArchivio
from app import db
from sqlalchemy import distinct, desc

storico_bp = Blueprint('storico', __name__, url_prefix='/storico')


@storico_bp.route('/')
def index():
    """Visualizza le transazioni archiviate con filtro per periodo"""
    
    # Recupera il parametro periodo dal query string (formato YYYYMM)
    periodo_selezionato = request.args.get('periodo', type=int)
    
    # Recupera tutti i periodi disponibili nell'archivio (ordinati in ordine crescente)
    periodi_disponibili = db.session.query(
        distinct(TransazioniArchivio.id_periodo)
    ).order_by(TransazioniArchivio.id_periodo.asc()).all()
    
    # Converti in lista di interi
    periodi = [p[0] for p in periodi_disponibili if p[0] is not None]
    
    # Se non è specificato un periodo, usa l'ultimo (più recente)
    if periodo_selezionato is None and periodi:
        periodo_selezionato = periodi[-1]  # Ultimo periodo (più recente)
    
    # Recupera le transazioni del periodo selezionato
    transazioni = []
    if periodo_selezionato:
        transazioni = TransazioniArchivio.query.filter_by(
            id_periodo=periodo_selezionato
        ).order_by(desc(TransazioniArchivio.data)).all()
    
    # Formatta i periodi per la dropdown (YYYYMM -> "Mese YYYY")
    periodi_formattati = []
    for p in periodi:
        year = p // 100
        month = p % 100
        mesi_nomi = ['', 'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
                     'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
        nome_mese = mesi_nomi[month] if 1 <= month <= 12 else f"Mese {month}"
        periodi_formattati.append({
            'id_periodo': p,
            'label': f"{nome_mese} {year}"
        })
    
    # Calcola statistiche per il periodo selezionato
    totale_entrate = sum(tx.importo for tx in transazioni if tx.tipo == 'entrata')
    totale_uscite = sum(tx.importo for tx in transazioni if tx.tipo == 'uscita')
    bilancio = totale_entrate - totale_uscite
    
    return render_template(
        'transazioni/storico.html',
        transazioni=transazioni,
        periodi=periodi_formattati,
        periodo_selezionato=periodo_selezionato,
        totale_entrate=totale_entrate,
        totale_uscite=totale_uscite,
        bilancio=bilancio
    )
