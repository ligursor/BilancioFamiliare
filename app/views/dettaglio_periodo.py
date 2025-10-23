"""
Blueprint per il dettaglio periodo
Gestisce le visualizzazioni dettagliate per mese/periodo
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from app.services.dettaglio_periodo_service import DettaglioPeriodoService
from app.services.categorie_service import CategorieService
from flask import request, jsonify

dettaglio_periodo_bp = Blueprint('dettaglio_periodo', __name__)

@dettaglio_periodo_bp.route('/')
def index():
    """Pagina principale dettaglio periodo - mostra mese corrente"""
    oggi = datetime.now()
    return redirect(url_for('dettaglio_periodo.mese', 
                          anno=oggi.year, 
                          mese=oggi.month))

@dettaglio_periodo_bp.route('/<int:anno>/<int:mese>')
def mese(anno, mese):
    """Visualizza il dettaglio di un mese specifico - implementazione originale"""
    try:
        # Validazione dei parametri
        if mese < 1 or mese > 12:
            flash('Mese non valido', 'error')
            return redirect(url_for('dettaglio_periodo.index'))

        # Servizi
        service = DettaglioPeriodoService()

        # Recupera dati per il mese (categoria filtering removed)
        dettaglio = service.get_dettaglio_mese(anno, mese)
        stats_categorie = service.get_statistiche_per_categoria(anno, mese)

        # Prepara categorie per il modal (escludi PayPal) usando il servizio
        service_cat = CategorieService()
        categorie_dict = service_cat.get_categories_dict(exclude_paypal=True)

        # Calcola mese precedente e successivo
        if mese == 1:
            mese_prec, anno_prec = 12, anno - 1
        else:
            mese_prec, anno_prec = mese - 1, anno

        if mese == 12:
            mese_succ, anno_succ = 1, anno + 1
        else:
            mese_succ, anno_succ = mese + 1, anno

        # Usa il template originale (già corretto l'endpoint)
        return render_template('dettaglio_mese.html',
                     # Spacchetta il dizionario dettaglio per compatibilità template
                     **dettaglio,
                     stats_categorie=stats_categorie,
                     categorie=categorie_dict,
                     anno=anno,
                     mese=mese,
                     mese_prec=mese_prec,
                     anno_prec=anno_prec,
                     mese_succ=mese_succ,
                     anno_succ=anno_succ)

    except Exception as e:
        flash(f'Errore nel caricamento dettaglio periodo: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@dettaglio_periodo_bp.route('/<start_date>/<end_date>')
def dettaglio_periodo(start_date, end_date):
    """Mostra il dettaglio delle transazioni per un periodo specifico con date"""
    try:
        from datetime import datetime
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()

        service = DettaglioPeriodoService()

        # Recupera dettaglio del periodo (categoria filtering removed)
        result = service.dettaglio_periodo_interno(start_date_obj, end_date_obj)

        # Prepara categorie per il modal (escludi PayPal) usando il servizio
        service_cat = CategorieService()
        categorie_dict = service_cat.get_categories_dict(exclude_paypal=True)

        # Aggiungi le categorie al risultato
        result['categorie'] = categorie_dict

        # Calcola anno/mese derivati dall'end_date (usati dal template per dataset e navigazione)
        anno = end_date_obj.year
        mese = end_date_obj.month

        if mese == 1:
            mese_prec, anno_prec = 12, anno - 1
        else:
            mese_prec, anno_prec = mese - 1, anno

        if mese == 12:
            mese_succ, anno_succ = 1, anno + 1
        else:
            mese_succ, anno_succ = mese + 1, anno

        # Statistiche per categorie per il mese (necessarie al grafico)
        try:
            stats_categorie = service.get_statistiche_per_categoria(anno, mese)
        except Exception:
            stats_categorie = []
        return render_template('dettaglio_mese.html', **result,
                       stats_categorie=stats_categorie,
                       anno=anno, mese=mese,
                       mese_prec=mese_prec, anno_prec=anno_prec,
                       mese_succ=mese_succ, anno_succ=anno_succ)
    except ValueError:
        return "Date non valide", 400
    except Exception as e:
        flash(f'Errore nel caricamento dettaglio periodo: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@dettaglio_periodo_bp.route('/monthly_budget_update', methods=['POST'])
def monthly_budget_update():
    """Endpoint AJAX per creare/aggiornare un MonthlyBudget per un mese specifico"""
    try:
        data = request.get_json() or {}
        year = int(data.get('year'))
        month = int(data.get('month'))
        categoria_id = int(data.get('categoria_id'))
        importo = float(data.get('importo'))
        from app.models.monthly_budget import MonthlyBudget
        from app import db
        from app.services.dettaglio_periodo_service import DettaglioPeriodoService

        mb = MonthlyBudget.query.filter_by(categoria_id=categoria_id, year=year, month=month).first()
        created = False
        if not mb:
            mb = MonthlyBudget(categoria_id=categoria_id, year=year, month=month, importo=importo)
            db.session.add(mb)
            db.session.commit()
            created = True
        else:
            old = float(mb.importo or 0.0)
            mb.importo = importo
            db.session.commit()

        # Ricalcola il dettaglio del mese per restituire residuo e nuovi totali
        try:
            servizio = DettaglioPeriodoService()
            dettaglio = servizio.get_dettaglio_mese(year, month)
            # trova il budget item relativo
            budget_item = None
            for it in dettaglio.get('budget_items', []):
                if int(it.get('categoria_id')) == int(categoria_id):
                    budget_item = it
                    break

            # Ensure the returned budget_item reflects the updated importo and residuo
            if budget_item is not None:
                try:
                    # force iniziale from MonthlyBudget and recompute residuo
                    iniziale = float(mb.importo or 0.0)
                    spese_eff = float(budget_item.get('spese_effettuate', 0.0) or 0.0)
                    spese_pia = float(budget_item.get('spese_pianificate', 0.0) or 0.0)
                    residuo = iniziale - (spese_eff + spese_pia)
                    budget_item['iniziale'] = iniziale
                    budget_item['residuo'] = float(residuo)
                except Exception:
                    pass

            response = {
                'success': True,
                'importo': mb.importo,
                'budget_item': budget_item,
                'uscite': dettaglio.get('uscite'),
                'bilancio': dettaglio.get('bilancio')
            }
            return jsonify(response)
        except Exception:
            return jsonify({'success': True, 'importo': mb.importo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dettaglio_periodo_bp.route('/confronto')
def confronto():
    """Confronta due periodi"""
    try:
        # Parametri di default (mese corrente vs mese precedente)
        oggi = datetime.now()
        
        anno1 = request.args.get('anno1', oggi.year, type=int)
        mese1 = request.args.get('mese1', oggi.month, type=int)
        
        # Mese precedente di default
        if oggi.month == 1:
            anno2_default, mese2_default = oggi.year - 1, 12
        else:
            anno2_default, mese2_default = oggi.year, oggi.month - 1
            
        anno2 = request.args.get('anno2', anno2_default, type=int)
        mese2 = request.args.get('mese2', mese2_default, type=int)
        
        service = DettaglioPeriodoService()
        
        # Recupera il confronto
        confronto_dati = service.get_confronto_mesi(anno1, mese1, anno2, mese2)
        mesi_disponibili = service.get_mesi_disponibili()
        
        # Nomi dei mesi
        nomi_mesi = [
            'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
            'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'
        ]
        
        return render_template('dettaglio_periodo/confronto.html',
                             confronto=confronto_dati,
                             mesi_disponibili=mesi_disponibili,
                             nomi_mesi=nomi_mesi,
                             anno1=anno1,
                             mese1=mese1,
                             anno2=anno2,
                             mese2=mese2)
        
    except Exception as e:
        flash(f'Errore nel confronto periodi: {str(e)}', 'error')
        return redirect(url_for('dettaglio_periodo.index'))

@dettaglio_periodo_bp.route('/api/statistiche/<int:anno>/<int:mese>')
def api_statistiche(anno, mese):
    """API per le statistiche di un mese (per AJAX)"""
    try:
        service = DettaglioPeriodoService()
        # get_dettaglio_mese returns un dict con i totali già calcolati
        dettaglio = service.get_dettaglio_mese(anno, mese)
        statistiche = {
            'entrate': dettaglio.get('entrate'),
            'uscite': dettaglio.get('uscite'),
            'bilancio': dettaglio.get('bilancio')
        }
        stats_categorie = service.get_statistiche_per_categoria(anno, mese)

        return jsonify({
            'success': True,
            'statistiche': statistiche,
            'stats_categorie': stats_categorie
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dettaglio_periodo_bp.route('/ricorrenti/<int:anno>/<int:mese>')
def ricorrenti(anno, mese):
    """Visualizza solo le transazioni ricorrenti di un mese"""
    try:
        service = DettaglioPeriodoService()
        transazioni_ricorrenti = service.get_transazioni_ricorrenti_mese(anno, mese)
        
        # Nomi dei mesi
        nomi_mesi = [
            'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
            'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'
        ]
        nome_mese = nomi_mesi[mese - 1]
        
        return render_template('dettaglio_periodo/ricorrenti.html',
                             transazioni=transazioni_ricorrenti,
                             anno=anno,
                             mese=mese,
                             nome_mese=nome_mese)
        
    except Exception as e:
        flash(f'Errore nel caricamento transazioni ricorrenti: {str(e)}', 'error')
        return redirect(url_for('dettaglio_periodo.mese', anno=anno, mese=mese))

@dettaglio_periodo_bp.route('/<start_date>/<end_date>/elimina_transazione/<int:id>', methods=['POST'])
def elimina_transazione_periodo(start_date, end_date, id):
    from datetime import datetime
    from app.models.transazioni import Transazione
    from app.models.budget import Budget
    from app import db
    from app.services import get_month_boundaries
    from flask import request, flash, redirect, url_for, current_app

    transazione = Transazione.query.get_or_404(id)
    descrizione = transazione.descrizione
    importo = transazione.importo
    data = transazione.data
    tipo = transazione.tipo

    # Delego la decisione al service: se serve ripristinare/considerare budget il service ritorna True
    servizio = DettaglioPeriodoService()
    try:
        should_handle_budget = servizio.handle_budget_on_delete(transazione)
        if should_handle_budget:
            # Il residuo è calcolato dinamicamente dai MonthlyBudget; informiamo l'utente
            flash(f'€{importo:.2f} ripristinati (residuo ricalcolato dinamicamente) per il budget della categoria.', 'info')

        # Esegui l'eliminazione in una singola transazione DB
        db.session.delete(transazione)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash(f'Errore durante eliminazione transazione: {e}', 'error')
        return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))
    flash(f'Transazione "{descrizione}" eliminata con successo!', 'success')
    # Preserve categoria filter if present
    # Do not pick categoria_id from the submitted form (that would force the view to filter by the newly added category).
    # Only preserve an explicit categoria_id passed via querystring (i.e. when the user had an active filter).
    redirect_url = url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date)
    return redirect(redirect_url)

@dettaglio_periodo_bp.route('/<start_date>/<end_date>/aggiungi_transazione', methods=['POST'])
def aggiungi_transazione_periodo(start_date, end_date):
    from datetime import datetime
    from app.models.transazioni import Transazione
    from app.models.budget import Budget
    from app import db
    from app.services import get_month_boundaries
    from flask import request, flash, redirect, url_for, current_app

    descrizione = request.form.get('descrizione', '').strip()
    importo = float(request.form.get('importo', 0))
    data_str = request.form.get('data', '')
    categoria_id = int(request.form.get('categoria_id', 0))
    tipo = request.form.get('tipo', 'uscita')
    ricorrente = int(request.form.get('ricorrente', 0))
    data = datetime.strptime(data_str, '%Y-%m-%d').date()

    transazione = Transazione(
        descrizione=descrizione,
        importo=importo,
        data=data,
        categoria_id=categoria_id,
        tipo=tipo,
        ricorrente=ricorrente
    )
    servizio = DettaglioPeriodoService()
    try:
        # Valuta se la nuova transazione richiede un'azione sul budget
        if servizio.handle_budget_on_add(transazione):
            # Se in futuro serve modificare MonthlyBudget, gestirlo nel service
            pass

        db.session.add(transazione)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash(f'Errore durante l\'aggiunta della transazione: {e}', 'error')
        return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))
    flash('Transazione aggiunta con successo!', 'success')
    redirect_url = url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date)
    return redirect(redirect_url)

@dettaglio_periodo_bp.route('/<start_date>/<end_date>/modifica_transazione/<int:id>', methods=['POST'])
def modifica_transazione_periodo(start_date, end_date, id):
    from datetime import datetime
    from app.models.transazioni import Transazione
    from app.models.budget import Budget
    from app import db
    from app.services import get_month_boundaries
    from flask import request, flash, redirect, url_for, current_app

    transazione = Transazione.query.get_or_404(id)
    importo_originale = transazione.importo
    data_originale = transazione.data
    tipo_originale = transazione.tipo
    categoria_id_originale = transazione.categoria_id
    ricorrente_originale = transazione.ricorrente

    # Aggiorna solo i campi modificati
    if 'descrizione' in request.form:
        transazione.descrizione = request.form['descrizione'].strip()
    if 'importo' in request.form:
        try:
            importo = float(request.form['importo'])
            if importo <= 0:
                flash('Importo non valido. Deve essere maggiore di zero.', 'error')
                return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))
            transazione.importo = importo
        except Exception as e:
            flash('Importo non valido. Inserisci un numero.', 'error')
            return redirect(url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date))
    if 'data' in request.form:
        transazione.data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
    if 'categoria_id' in request.form:
        transazione.categoria_id = int(request.form['categoria_id'])
    if 'tipo' in request.form:
        transazione.tipo = request.form['tipo']
    if 'ricorrente' in request.form:
        transazione.ricorrente = int(request.form['ricorrente'])
    db.session.add(transazione)
    db.session.commit()
    # Logica decurtazione/ripristino budget (solo per uscita non ricorrente)
    servizio = DettaglioPeriodoService()
    try:
        res = servizio.handle_budget_on_modify(categoria_id_originale, tipo_originale, ricorrente_originale, transazione)
        # res è un dict {'restored': bool, 'applied': bool}
        # Se occorre ripristinare o applicare, il servizio può essere esteso per fare le modifiche
        # Per ora limitiamoci ad informare l'utente se era necessario considerare il budget
        if res.get('restored'):
            flash('Budget originale ripristinato (residuo ricalcolato dinamicamente).', 'info')
        if res.get('applied'):
            flash('Budget aggiornato in base alla nuova transazione (residuo ricalcolato).', 'info')
    except Exception:
        # Non blocchiamo la modifica della transazione per errori nel controllo budget
        pass
    flash('Transazione modificata con successo!', 'success')
    redirect_url = url_for('dettaglio_periodo.dettaglio_periodo', start_date=start_date, end_date=end_date)
    return redirect(redirect_url)
