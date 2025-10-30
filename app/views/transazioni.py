"""
Blueprint per la gestione delle transazioni
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from app.services.bilancio.transazioni_service import TransazioneService
from app.models.base import Categoria
from app.models.transazioni import Transazione
from datetime import datetime, date

transazioni_bp = Blueprint('transazioni', __name__)

@transazioni_bp.route('/')
def lista():
    """Lista delle transazioni con paginazione e filtri"""
    try:
        service = TransazioneService()
        # Parametri di filtri (senza paginazione)
        tipo_filtro = request.args.get('tipo', '')
        ordine = request.args.get('ordine', 'data_desc')

        # Recupera tutte le transazioni applicando i filtri e l'ordinamento
        transazioni = service.get_transazioni_filtered(
            tipo_filtro=tipo_filtro if tipo_filtro else None,
            ordine=ordine
        )
        
        # Categorie per i filtri - usa il servizio per leggere dal DB
        from app.services.categorie.categorie_service import CategorieService
        service_cat = CategorieService()
        categorie_dict = service_cat.get_categories_dict(exclude_paypal=True)
        
        return render_template('transazioni.html',
                               transazioni=transazioni,
                               categorie=categorie_dict)
        
    except Exception as e:
        flash(f'Errore nel caricamento delle transazioni: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@transazioni_bp.route('/nuova', methods=['GET', 'POST'])
def nuova():
    """Crea una nuova transazione"""
    if request.method == 'GET':
        from app.services.categorie.categorie_service import CategorieService
        service_cat = CategorieService()
        categorie = service_cat.get_all_categories()
        return render_template('transazioni/nuova.html', categorie=categorie)
    
    try:
        service = TransazioneService()
        
        # Estrai dati dal form
        data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        descrizione = request.form['descrizione']
        importo = float(request.form['importo'])
        categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        tipo = request.form['tipo']
        ricorrente = request.form.get('ricorrente') == 'on'
        frequenza_giorni = int(request.form.get('frequenza_giorni', 0))
        
        # Determina data_effettiva
        data_effettiva = None
        if data <= date.today():
            data_effettiva = data
        
        success, message, transazione = service.create_transazione(
            data=data,
            descrizione=descrizione,
            importo=importo,
            categoria_id=categoria_id,
            tipo=tipo,
            ricorrente=ricorrente,
            frequenza_giorni=frequenza_giorni,
            data_effettiva=data_effettiva
        )
        
        if success:
            flash(f'Transazione "{descrizione}" creata con successo!', 'success')
            return redirect(url_for('transazioni.lista'))
        else:
            flash(f'Errore nella creazione: {message}', 'error')
    
    except ValueError as e:
        flash(f'Errore nei dati inseriti: {str(e)}', 'error')
    except Exception as e:
        flash(f'Errore imprevisto: {str(e)}', 'error')
    
    # Ricarica form in caso di errore
        from app.services.categorie.categorie_service import CategorieService
    service_cat = CategorieService()
    categorie = service_cat.get_all_categories()
    return render_template('transazioni/nuova.html', categorie=categorie)

@transazioni_bp.route('/<int:transazione_id>/completa', methods=['POST'])
def completa(transazione_id):
    """Segna una transazione come completata"""
    try:
        # fetch the transaction to determine its date for redirect
        transazione = Transazione.query.get_or_404(transazione_id)
        service = TransazioneService()
        success, message = service.mark_as_completed(transazione_id)
        
        if success:
            flash('Transazione segnata come completata!', 'success')
        else:
            flash(f'Errore: {message}', 'error')
    except Exception as e:
        flash(f'Errore: {str(e)}', 'error')

    # Redirect back to the month view containing the transaction
    try:
        target_date = getattr(transazione, 'data', None)
        if not target_date:
            target_date = date.today()
        return redirect(url_for('dettaglio_periodo.mese', anno=target_date.year, mese=target_date.month))
    except Exception:
        return redirect(url_for('transazioni.lista'))

@transazioni_bp.route('/<int:transazione_id>/elimina', methods=['POST'])
@transazioni_bp.route('/<int:id>/elimina', methods=['POST'])
def elimina(transazione_id=None, id=None):
    """Elimina una transazione. Supporta sia POST che GET and accepts either
    'transazione_id' or 'id' as path parameter to be compatible with existing templates.
    """
    # Accept either name coming from different templates/routes
    tid = transazione_id or id
    try:
        transazione = Transazione.query.get_or_404(tid)
        service = TransazioneService()

        # Allow deletion regardless of data_effettiva / stato
        success, message = service.delete(transazione)

        if success:
            flash('Transazione eliminata con successo!', 'success')
        else:
            flash(f"Errore nell'eliminazione: {message}", 'error')
    except Exception as e:
        flash(f'Errore: {str(e)}', 'error')

    # Redirect back to the month view containing the (now deleted) transaction
    try:
        target_date = getattr(transazione, 'data', None)
        if not target_date:
            target_date = date.today()
        return redirect(url_for('dettaglio_periodo.mese', anno=target_date.year, mese=target_date.month))
    except Exception:
        return redirect(url_for('transazioni.lista'))

@transazioni_bp.route('/<int:transazione_id>/modifica', methods=['GET', 'POST'])
def modifica(transazione_id):
    """Modifica una transazione esistente"""
    transazione = Transazione.query.get_or_404(transazione_id)
    
    if request.method == 'GET':
        from app.services.categorie.categorie_service import CategorieService
        service_cat = CategorieService()
        categorie = service_cat.get_all_categories()
        return render_template('transazioni/modifica.html', 
                             transazione=transazione, 
                             categorie=categorie)
    
    try:
        service = TransazioneService()
        
        # Aggiorna i campi
        data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        descrizione = request.form['descrizione']
        importo = float(request.form['importo'])
        categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        tipo = request.form['tipo']
        
        success, message = service.update(transazione,
                                        data=data,
                                        descrizione=descrizione,
                                        importo=importo,
                                        categoria_id=categoria_id,
                                        tipo=tipo)
        
        if success:
            flash('Transazione aggiornata con successo!', 'success')
            # Redirect to the month view containing the transaction's date instead of the full transactions list
            try:
                # use the updated transaction date to determine the target month
                target_date = transazione.data if hasattr(transazione, 'data') else None
                if not target_date:
                    # fallback to form data
                    target_date = data
                anno = target_date.year
                mese = target_date.month
                return redirect(url_for('dettaglio_periodo.mese', anno=anno, mese=mese))
            except Exception:
                return redirect(url_for('transazioni.lista'))
        else:
            flash(f'Errore nell\'aggiornamento: {message}', 'error')
    
    except Exception as e:
        flash(f'Errore: {str(e)}', 'error')
    
    # Ricarica form in caso di errore
        from app.services.categorie.categorie_service import CategorieService
    service_cat = CategorieService()
    categorie = service_cat.get_all_categories()
    return render_template('transazioni/modifica.html', 
                         transazione=transazione, 
                         categorie=categorie)

@transazioni_bp.route('/aggiungi', methods=['POST'])
def aggiungi():
    """Aggiungi nuova transazione"""
    try:
        service = TransazioneService()
        
        # Estrai dati dal form
        data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        descrizione = request.form['descrizione']
        importo = float(request.form['importo'])
        categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        tipo = request.form['tipo']
        ricorrente = request.form.get('ricorrente') == 'on'
        frequenza_giorni = int(request.form.get('frequenza_giorni', 0))
        
        # Determina data_effettiva
        data_effettiva = None
        if data <= date.today():
            data_effettiva = data
        
        success, message, transazione = service.create_transazione(
            data=data,
            descrizione=descrizione,
            importo=importo,
            categoria_id=categoria_id,
            tipo=tipo,
            ricorrente=ricorrente,
            frequenza_giorni=frequenza_giorni,
            data_effettiva=data_effettiva
        )
        
        if success:
            flash(f'Transazione "{descrizione}" creata con successo!', 'success')
            
            # Gestisci redirect
            redirect_to = request.form.get('redirect_to', 'transazioni')
            if redirect_to == 'dashboard':
                return redirect(url_for('main.index'))
            elif redirect_to.startswith('dettaglio_periodo:'):
                _, start_date_str, end_date_str = redirect_to.split(':')
                return redirect(url_for('main.dettaglio_periodo', start_date=start_date_str, end_date=end_date_str))
            else:
                # Default: redirect to the month view containing the created transaction
                try:
                    target_date = getattr(transazione, 'data', None) or data
                    return redirect(url_for('dettaglio_periodo.mese', anno=target_date.year, mese=target_date.month))
                except Exception:
                    return redirect(url_for('transazioni.lista'))
        else:
            flash(f'Errore nella creazione: {message}', 'error')
    
    except Exception as e:
        flash(f'Errore: {str(e)}', 'error')
    
    return redirect(url_for('transazioni.lista'))
