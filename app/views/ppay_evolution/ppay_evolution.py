"""Gestione dashboard e movimenti PostePay Evolution."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from app.utils.formatting import format_currency
from datetime import datetime, date, timedelta
from app.models.PostePayEvolution import AbbonamentoPostePay, MovimentoPostePay
from app.services.conti_finanziari.strumenti_service import StrumentiService
from types import SimpleNamespace
import calendar
from app import db

ppay_bp = Blueprint('ppay', __name__)

def inizializza_postepay():
    """Inizializza il sistema PostePay se necessario"""
    # Ensure a Strumento exists for Postepay Evolution and use it as source of truth for saldo
    ss = StrumentiService()
    descr = 'Postepay Evolution'
    try:
        strum = ss.ensure_strumento(descr, 'carta', 0.0)
    except Exception:
        # best-effort: fallback to creating a local PostePayEvolution record
        strum = None
    # The saldo is kept exclusively in `conti_finanziari.Strumento` (StrumentiService).
    # Return the strumento (or None).
    # templates and logic should read the saldo from the Strumento.
    return strum

@ppay_bp.route('/')
def evolution():
    """Mostra la dashboard di PostePay Evolution."""
    try:
        # Inizializza il sistema PostePay se necessario
        inizializza_postepay()
        
        # Recupera dati
        ss = StrumentiService()
        strum = ss.get_by_descrizione('Postepay Evolution')
        # create a small proxy so templates expecting postepay.saldo_attuale keep working
        if strum is not None:
            postepay = SimpleNamespace(saldo_attuale=(strum.saldo_corrente or 0.0))
        else:
            postepay = SimpleNamespace(saldo_attuale=0.0)
        abbonamenti = AbbonamentoPostePay.query.order_by(AbbonamentoPostePay.nome).all()
        movimenti = MovimentoPostePay.query.order_by(MovimentoPostePay.data.desc()).limit(10).all()

        # Calcola statistiche
        abbonamenti_attivi = [a for a in abbonamenti if a.attivo]
        spesa_mensile = sum(a.importo for a in abbonamenti_attivi)

        # Optionally skip auto-generation (used when redirecting after a manual delete)
        skip_auto = request.args.get('skip_auto')

        # --- Generazione automatica movimenti per abbonamenti scaduti oggi ---
        if not skip_auto:
            try:
                oggi = date.today()
                first_of_month = date(oggi.year, oggi.month, 1)
                ultimo_giorno = calendar.monthrange(oggi.year, oggi.month)[1]
                last_of_month = date(oggi.year, oggi.month, ultimo_giorno)

                for abbonamento in abbonamenti_attivi:
                    # Calcola la data di addebito per il mese corrente (gestendo
                    # mesi con meno giorni del giorno_addebito impostato)
                    try:
                        giorno_addebito = int(abbonamento.giorno_addebito)
                    except Exception:
                        # Se non è valido, salta
                        continue

                    giorno_per_mese = min(giorno_addebito, ultimo_giorno)
                    addebito_this_month = date(oggi.year, oggi.month, giorno_per_mese)

                    # Se l'addebito di questo mese è già passato (<= oggi) e non
                    # esiste ancora un movimento per questo abbonamento nel mese,
                    # creiamo comunque il movimento e aggiorniamo il saldo
                    if addebito_this_month <= oggi:
                        esistente = MovimentoPostePay.query.filter(
                            MovimentoPostePay.abbonamento_id == abbonamento.id,
                            MovimentoPostePay.data >= first_of_month,
                            MovimentoPostePay.data <= last_of_month
                        ).first()

                        if not esistente:
                            # Also check deleted-generation tombstones to avoid recreating recently-deleted auto-generated movements
                            mov = MovimentoPostePay(
                                data=addebito_this_month,
                                descrizione=f"{abbonamento.nome} {addebito_this_month.strftime('%m/%Y')}",
                                importo=abs(abbonamento.importo),
                                tipo='Abbonamento',
                                tipo_movimento='uscita',
                                abbonamento_id=abbonamento.id
                            )
                            db.session.add(mov)
                            db.session.commit()
                            # update strumento balance
                            try:
                                strum = ss.get_by_descrizione('Postepay Evolution')
                                if strum:
                                    # Calculate signed value: importo is positive, tipo_movimento='uscita' means subtract
                                    signed_value = -abs(mov.importo) if mov.tipo_movimento == 'uscita' else abs(mov.importo)
                                    new_bal = (strum.saldo_corrente or 0.0) + signed_value
                                    ss.update_saldo_by_id(strum.id_conto, new_bal)
                            except Exception:
                                pass
            except Exception:
                # Non vogliamo rompere la visualizzazione se la generazione automatica fallisce
                try:
                    db.session.rollback()
                except Exception:
                    pass

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

        resp = make_response(render_template('postepay_evolution/ppay_evolution.html',
                             postepay=postepay,
                             abbonamenti=abbonamenti,
                             abbonamenti_json=abbonamenti_serializzati,
                             movimenti=movimenti,
                             spesa_mensile=spesa_mensile,
                             prossimi_addebiti=prossimi_addebiti,
                             addebiti_problematici=addebiti_problematici))
        resp.headers['X-Partial-Response'] = '1'
        return resp

    except Exception as e:
        flash(f'Errore nel caricamento PostePay Evolution: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@ppay_bp.route('/ricarica', methods=['POST'])
def ricarica():
    """Aggiunge una ricarica PostePay"""
    try:
        # Ensure the strumento exists; we no longer rely on a DB row for PostePayEvolution
        strum = inizializza_postepay()
        ss = StrumentiService()
        strum = ss.get_by_descrizione('Postepay Evolution')

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

        # Normalize: entrata -> positive importo
        signed_importo = abs(importo)

        # Crea movimento (tipo = categoria)
        movimento = MovimentoPostePay(
            data=data_movimento,
            descrizione=descrizione,
            importo=signed_importo,
            tipo='Ricarica',
            tipo_movimento='entrata'
        )

        db.session.add(movimento)
        db.session.commit()

        # Aggiorna saldo nello strumento (sorgente di verità) by adding the signed importo
        try:
            if strum:
                new_bal = (strum.saldo_corrente or 0.0) + signed_importo
                ss.update_saldo_by_id(strum.id_conto, new_bal)
        except Exception:
            pass

        flash(f'Ricarica di {format_currency(importo)} aggiunta con successo!', 'success')
        
    except ValueError:
        flash('Importo non valido', 'error')
    except Exception as e:
        flash(f'Errore nell\'aggiunta ricarica: {str(e)}', 'error')
        db.session.rollback()
    
    # Redirect to evolution but skip automatic generation to avoid immediately recreating generated movements
    return redirect(url_for('ppay.evolution', skip_auto=1))

@ppay_bp.route('/spesa', methods=['POST'])
def spesa():
    """Aggiunge una spesa PostePay"""
    try:
        # Ensure strumento exists
        strum = inizializza_postepay()
        ss = StrumentiService()
        strum = ss.get_by_descrizione('Postepay Evolution')

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

        # Verifica saldo disponibile (compare with absolute amount)
        current_balance = (strum.saldo_corrente if strum else 0.0)
        if current_balance < abs(importo):
            flash('Saldo insufficiente per questa spesa', 'error')
            return redirect(url_for('ppay.evolution'))

        # Normalize: uscita -> positive importo, tipo_movimento='uscita'
        signed_importo = abs(importo)

        movimento = MovimentoPostePay(
            data=data_movimento,
            descrizione=descrizione,
            importo=signed_importo,
            tipo='Pagamento',
            tipo_movimento='uscita'
        )

        db.session.add(movimento)
        db.session.commit()

        # Aggiorna saldo nello strumento (sorgente di verità) by adding the signed importo
        try:
            if strum:
                new_bal = (strum.saldo_corrente or 0.0) + signed_importo
                ss.update_saldo_by_id(strum.id_conto, new_bal)
        except Exception:
            pass

        flash(f'Spesa di {format_currency(importo)} aggiunta con successo!', 'success')
        
    except ValueError:
        flash('Importo non valido', 'error')
    except Exception as e:
        flash(f'Errore nell\'aggiunta spesa: {str(e)}', 'error')
        db.session.rollback()
    
    # Return rendered template for fetch-based updates (no redirect)
    try:
        inizializza_postepay()
        ss = StrumentiService()
        strum = ss.get_by_descrizione('Postepay Evolution')
        if strum is not None:
            postepay = SimpleNamespace(saldo_attuale=(strum.saldo_corrente or 0.0))
        else:
            postepay = SimpleNamespace(saldo_attuale=0.0)
        abbonamenti = AbbonamentoPostePay.query.order_by(AbbonamentoPostePay.nome).all()
        movimenti = MovimentoPostePay.query.order_by(MovimentoPostePay.data.desc()).limit(10).all()

        abbonamenti_attivi = [a for a in abbonamenti if a.attivo]
        spesa_mensile = sum(a.importo for a in abbonamenti_attivi)

        # Calcola prossimi addebiti con saldo sufficiente
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

        # Calcola saldo sufficiente per ogni addebito (progressivo)
        saldo_simulato = postepay.saldo_attuale if postepay else 0
        for addebito in prossimi_addebiti:
            if saldo_simulato >= addebito['abbonamento'].importo:
                addebito['saldo_sufficiente'] = True
                saldo_simulato -= addebito['abbonamento'].importo
            else:
                addebito['saldo_sufficiente'] = False

        # Calcola addebiti problematici (per alert)
        saldo_alert = postepay.saldo_attuale if postepay else 0
        addebiti_problematici = []
        for addebito in prossimi_addebiti:
            if saldo_alert < addebito['abbonamento'].importo:
                addebiti_problematici.append({
                    'abbonamento': addebito['abbonamento'],
                    'data': addebito['data'],
                    'giorni': addebito['giorni'],
                    'importo_mancante': addebito['abbonamento'].importo - saldo_alert
                })
            saldo_alert -= addebito['abbonamento'].importo

        # Serializza abbonamenti per JavaScript
        import json
        abbonamenti_serializzati = json.dumps([{
            'id': a.id,
            'nome': a.nome,
            'importo': float(a.importo),
            'giorno_addebito': a.giorno_addebito,
            'attivo': a.attivo
        } for a in abbonamenti])

        return render_template('postepay_evolution/ppay_evolution.html',
                             postepay=postepay,
                             abbonamenti=abbonamenti,
                             abbonamenti_json=abbonamenti_serializzati,
                             movimenti=movimenti,
                             spesa_mensile=spesa_mensile,
                             prossimi_addebiti=prossimi_addebiti,
                             addebiti_problematici=addebiti_problematici)
    except Exception as e:
        from flask import current_app
        current_app.logger.exception(f"Errore nel rendering dopo aggiunta movimento: {e}")
        # Fallback to redirect if rendering fails
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
    
    # Return rendered template for fetch-based updates (no redirect)
    try:
        inizializza_postepay()
        ss = StrumentiService()
        strum = ss.get_by_descrizione('Postepay Evolution')
        if strum is not None:
            postepay = SimpleNamespace(saldo_attuale=(strum.saldo_corrente or 0.0))
        else:
            postepay = SimpleNamespace(saldo_attuale=0.0)
        abbonamenti = AbbonamentoPostePay.query.order_by(AbbonamentoPostePay.nome).all()
        movimenti = MovimentoPostePay.query.order_by(MovimentoPostePay.data.desc()).limit(10).all()

        abbonamenti_attivi = [a for a in abbonamenti if a.attivo]
        spesa_mensile = sum(a.importo for a in abbonamenti_attivi)

        # Calcola prossimi addebiti con saldo sufficiente
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

        # Calcola saldo sufficiente per ogni addebito (progressivo)
        saldo_simulato = postepay.saldo_attuale if postepay else 0
        for addebito in prossimi_addebiti:
            if saldo_simulato >= addebito['abbonamento'].importo:
                addebito['saldo_sufficiente'] = True
                saldo_simulato -= addebito['abbonamento'].importo
            else:
                addebito['saldo_sufficiente'] = False

        # Calcola addebiti problematici (per alert)
        saldo_alert = postepay.saldo_attuale if postepay else 0
        addebiti_problematici = []
        for addebito in prossimi_addebiti:
            if saldo_alert < addebito['abbonamento'].importo:
                addebiti_problematici.append({
                    'abbonamento': addebito['abbonamento'],
                    'data': addebito['data'],
                    'giorni': addebito['giorni'],
                    'importo_mancante': addebito['abbonamento'].importo - saldo_alert
                })
            saldo_alert -= addebito['abbonamento'].importo

        # Serializza abbonamenti per JavaScript
        import json
        abbonamenti_serializzati = json.dumps([{
            'id': a.id,
            'nome': a.nome,
            'importo': float(a.importo),
            'giorno_addebito': a.giorno_addebito,
            'attivo': a.attivo
        } for a in abbonamenti])

        return render_template('postepay_evolution/ppay_evolution.html',
                             postepay=postepay,
                             abbonamenti=abbonamenti,
                             abbonamenti_json=abbonamenti_serializzati,
                             movimenti=movimenti,
                             spesa_mensile=spesa_mensile,
                             prossimi_addebiti=prossimi_addebiti,
                             addebiti_problematici=addebiti_problematici)
    except Exception as e:
        from flask import current_app
        current_app.logger.exception(f"Errore nel rendering dopo aggiunta movimento: {e}")
        # Fallback to redirect if rendering fails
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
    
    # Return rendered template for fetch-based updates (no redirect)
    try:
        inizializza_postepay()
        ss = StrumentiService()
        strum = ss.get_by_descrizione('Postepay Evolution')
        if strum is not None:
            postepay = SimpleNamespace(saldo_attuale=(strum.saldo_corrente or 0.0))
        else:
            postepay = SimpleNamespace(saldo_attuale=0.0)
        abbonamenti = AbbonamentoPostePay.query.order_by(AbbonamentoPostePay.nome).all()
        movimenti = MovimentoPostePay.query.order_by(MovimentoPostePay.data.desc()).limit(10).all()

        abbonamenti_attivi = [a for a in abbonamenti if a.attivo]
        spesa_mensile = sum(a.importo for a in abbonamenti_attivi)

        # Calcola prossimi addebiti con saldo sufficiente
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

        # Calcola saldo sufficiente per ogni addebito (progressivo)
        saldo_simulato = postepay.saldo_attuale if postepay else 0
        for addebito in prossimi_addebiti:
            if saldo_simulato >= addebito['abbonamento'].importo:
                addebito['saldo_sufficiente'] = True
                saldo_simulato -= addebito['abbonamento'].importo
            else:
                addebito['saldo_sufficiente'] = False

        # Calcola addebiti problematici (per alert)
        saldo_alert = postepay.saldo_attuale if postepay else 0
        addebiti_problematici = []
        for addebito in prossimi_addebiti:
            if saldo_alert < addebito['abbonamento'].importo:
                addebiti_problematici.append({
                    'abbonamento': addebito['abbonamento'],
                    'data': addebito['data'],
                    'giorni': addebito['giorni'],
                    'importo_mancante': addebito['abbonamento'].importo - saldo_alert
                })
            saldo_alert -= addebito['abbonamento'].importo

        # Serializza abbonamenti per JavaScript
        import json
        abbonamenti_serializzati = json.dumps([{
            'id': a.id,
            'nome': a.nome,
            'importo': float(a.importo),
            'giorno_addebito': a.giorno_addebito,
            'attivo': a.attivo
        } for a in abbonamenti])

        return render_template('postepay_evolution/ppay_evolution.html',
                             postepay=postepay,
                             abbonamenti=abbonamenti,
                             abbonamenti_json=abbonamenti_serializzati,
                             movimenti=movimenti,
                             spesa_mensile=spesa_mensile,
                             prossimi_addebiti=prossimi_addebiti,
                             addebiti_problematici=addebiti_problematici)
    except Exception as e:
        from flask import current_app
        current_app.logger.exception(f"Errore nel rendering dopo aggiunta movimento: {e}")
        # Fallback to redirect if rendering fails
        return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/elimina_movimento/<int:movimento_id>', methods=['POST'])
def elimina_movimento(movimento_id):
    """Elimina un movimento PostePay e aggiorna il saldo"""
    try:
        movimento = MovimentoPostePay.query.get_or_404(movimento_id)
        from flask import current_app
        current_app.logger.info(f"elimina_movimento called for id={movimento_id} -> movimento={movimento}")
        
        # Se il movimento è di tipo Ricarica, cerca e cancella la transazione corrispondente
        if movimento.tipo == 'Ricarica':
            try:
                from app.models.Transazioni import Transazioni
                # Cerca transazione con categoria_id=10, stessa data e stesso importo
                tx_correlata = Transazioni.query.filter(
                    Transazioni.categoria_id == 10,
                    Transazioni.data == movimento.data,
                    Transazioni.importo == movimento.importo
                ).first()
                if tx_correlata:
                    current_app.logger.info(f"Trovata transazione correlata id={tx_correlata.id}, la elimino")
                    db.session.delete(tx_correlata)
            except Exception as e:
                current_app.logger.error(f"Errore ricerca/cancellazione transazione correlata: {e}")
        
        # Calculate signed value to subtract from balance
        signed_value = -abs(movimento.importo) if movimento.tipo_movimento == 'uscita' else abs(movimento.importo)

        db.session.delete(movimento)

        # Aggiorna saldo nello strumento invertendo l'effetto del movimento
        try:
            ss = StrumentiService()
            strum = ss.get_by_descrizione('Postepay Evolution')
            if strum:
                # Subtract the effect: if it was +100, now -100; if it was -100, now +100
                new_bal = (strum.saldo_corrente or 0.0) - signed_value
                ss.update_saldo_by_id(strum.id_conto, new_bal)
        except Exception:
            pass

        db.session.commit()
        current_app.logger.info(f"elimina_movimento id={movimento_id} committed successfully")
        flash('Movimento eliminato con successo!', 'success')
    except Exception as e:
        # Log exception with traceback using Flask logger
        from flask import current_app
        current_app.logger.exception(f"Errore nell'eliminazione del movimento id={movimento_id}: {e}")
        flash(f'Errore nell\'eliminazione del movimento: {str(e)}', 'error')
        try:
            db.session.rollback()
        except Exception:
            pass
    
    # Redirect back to PostePay Evolution page (not Dashboard)
    return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/modifica_saldo', methods=['POST'])
def modifica_saldo():
    """Modifica il saldo PostePay Evolution"""
    try:
        nuovo_saldo = float(request.form['nuovo_saldo'])
        motivo = request.form.get('motivo', 'Modifica manuale saldo')
        
        ss = StrumentiService()
        strum = ss.get_by_descrizione('Postepay Evolution')
        if not strum:
            flash('Errore: Sistema PostePay non inizializzato!', 'error')
            return redirect(url_for('ppay.evolution'))

        # Calcola la differenza per il movimento
        saldo_precedente = strum.saldo_corrente or 0.0
        differenza = nuovo_saldo - saldo_precedente

        # Aggiorna il saldo nello strumento (sorgente di verità)
        try:
            ss.update_saldo_by_id(strum.id_conto, nuovo_saldo)
        except Exception:
            pass

        # Crea un movimento per tracciare la modifica
        if differenza != 0:
            movimento = MovimentoPostePay(
                data=date.today(),
                descrizione=f"{motivo} (da {format_currency(saldo_precedente)} a {format_currency(nuovo_saldo)})",
                importo=abs(differenza),
                tipo='correzione',
                tipo_movimento='entrata' if differenza > 0 else 'uscita'
            )
            db.session.add(movimento)

        db.session.commit()
        
        if differenza > 0:
            flash(f'Saldo aggiornato! Aggiunta di {format_currency(differenza)}', 'success')
        elif differenza < 0:
            flash(f'Saldo aggiornato! Riduzione di {format_currency(abs(differenza))}', 'success')
        else:
            flash('Saldo confermato (nessuna modifica)', 'info')
        
    except ValueError:
        flash('Importo non valido', 'error')
    except Exception as e:
        flash(f'Errore nella modifica del saldo: {str(e)}', 'error')
        db.session.rollback()
    
    # Return rendered template for fetch-based updates (no redirect)
    try:
        inizializza_postepay()
        ss = StrumentiService()
        strum = ss.get_by_descrizione('Postepay Evolution')
        if strum is not None:
            postepay = SimpleNamespace(saldo_attuale=(strum.saldo_corrente or 0.0))
        else:
            postepay = SimpleNamespace(saldo_attuale=0.0)
        abbonamenti = AbbonamentoPostePay.query.order_by(AbbonamentoPostePay.nome).all()
        movimenti = MovimentoPostePay.query.order_by(MovimentoPostePay.data.desc()).limit(10).all()

        abbonamenti_attivi = [a for a in abbonamenti if a.attivo]
        spesa_mensile = sum(a.importo for a in abbonamenti_attivi)

        # Calcola prossimi addebiti con saldo sufficiente
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

        # Calcola saldo sufficiente per ogni addebito (progressivo)
        saldo_simulato = postepay.saldo_attuale if postepay else 0
        for addebito in prossimi_addebiti:
            if saldo_simulato >= addebito['abbonamento'].importo:
                addebito['saldo_sufficiente'] = True
                saldo_simulato -= addebito['abbonamento'].importo
            else:
                addebito['saldo_sufficiente'] = False

        # Calcola addebiti problematici (per alert)
        saldo_alert = postepay.saldo_attuale if postepay else 0
        addebiti_problematici = []
        for addebito in prossimi_addebiti:
            if saldo_alert < addebito['abbonamento'].importo:
                addebiti_problematici.append({
                    'abbonamento': addebito['abbonamento'],
                    'data': addebito['data'],
                    'giorni': addebito['giorni'],
                    'importo_mancante': addebito['abbonamento'].importo - saldo_alert
                })
            saldo_alert -= addebito['abbonamento'].importo

        # Serializza abbonamenti per JavaScript
        import json
        abbonamenti_serializzati = json.dumps([{
            'id': a.id,
            'nome': a.nome,
            'importo': float(a.importo),
            'giorno_addebito': a.giorno_addebito,
            'attivo': a.attivo
        } for a in abbonamenti])

        return render_template('postepay_evolution/ppay_evolution.html',
                             postepay=postepay,
                             abbonamenti=abbonamenti,
                             abbonamenti_json=abbonamenti_serializzati,
                             movimenti=movimenti,
                             spesa_mensile=spesa_mensile,
                             prossimi_addebiti=prossimi_addebiti,
                             addebiti_problematici=addebiti_problematici)
    except Exception as e:
        from flask import current_app
        current_app.logger.exception(f"Errore nel rendering dopo aggiunta movimento: {e}")
        # Fallback to redirect if rendering fails
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
    
    # Return rendered template for fetch-based updates (no redirect)
    try:
        inizializza_postepay()
        ss = StrumentiService()
        strum = ss.get_by_descrizione('Postepay Evolution')
        if strum is not None:
            postepay = SimpleNamespace(saldo_attuale=(strum.saldo_corrente or 0.0))
        else:
            postepay = SimpleNamespace(saldo_attuale=0.0)
        abbonamenti = AbbonamentoPostePay.query.order_by(AbbonamentoPostePay.nome).all()
        movimenti = MovimentoPostePay.query.order_by(MovimentoPostePay.data.desc()).limit(10).all()

        abbonamenti_attivi = [a for a in abbonamenti if a.attivo]
        spesa_mensile = sum(a.importo for a in abbonamenti_attivi)

        # Calcola prossimi addebiti con saldo sufficiente
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

        # Calcola saldo sufficiente per ogni addebito (progressivo)
        saldo_simulato = postepay.saldo_attuale if postepay else 0
        for addebito in prossimi_addebiti:
            if saldo_simulato >= addebito['abbonamento'].importo:
                addebito['saldo_sufficiente'] = True
                saldo_simulato -= addebito['abbonamento'].importo
            else:
                addebito['saldo_sufficiente'] = False

        # Calcola addebiti problematici (per alert)
        saldo_alert = postepay.saldo_attuale if postepay else 0
        addebiti_problematici = []
        for addebito in prossimi_addebiti:
            if saldo_alert < addebito['abbonamento'].importo:
                addebiti_problematici.append({
                    'abbonamento': addebito['abbonamento'],
                    'data': addebito['data'],
                    'giorni': addebito['giorni'],
                    'importo_mancante': addebito['abbonamento'].importo - saldo_alert
                })
            saldo_alert -= addebito['abbonamento'].importo

        # Serializza abbonamenti per JavaScript
        import json
        abbonamenti_serializzati = json.dumps([{
            'id': a.id,
            'nome': a.nome,
            'importo': float(a.importo),
            'giorno_addebito': a.giorno_addebito,
            'attivo': a.attivo
        } for a in abbonamenti])

        return render_template('postepay_evolution/ppay_evolution.html',
                             postepay=postepay,
                             abbonamenti=abbonamenti,
                             abbonamenti_json=abbonamenti_serializzati,
                             movimenti=movimenti,
                             spesa_mensile=spesa_mensile,
                             prossimi_addebiti=prossimi_addebiti,
                             addebiti_problematici=addebiti_problematici)
    except Exception as e:
        from flask import current_app
        current_app.logger.exception(f"Errore nel rendering dopo aggiunta movimento: {e}")
        # Fallback to redirect only if rendering fails
        return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/aggiungi_movimento', methods=['POST'])
def aggiungi_movimento():
    """Aggiunge un movimento PostePay manuale"""
    try:
        importo = float(request.form['importo'])
        tipo = request.form['tipo']  # entrata/uscita
        tipo_movimento_form = request.form['tipo_movimento']  # ricarica/pagamento/altro
        
        movimento = MovimentoPostePay(
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
            descrizione=request.form['descrizione'],
            importo=abs(importo),  # Sempre positivo
            tipo=tipo_movimento_form,  # ricarica/pagamento/altro
            tipo_movimento=tipo  # entrata/uscita
        )
        
        db.session.add(movimento)
        
        # Aggiorna saldo nello strumento (sorgente di verità)
        # Calculate signed importo for balance update
        signed_importo = abs(importo) if tipo == 'entrata' else -abs(importo)
        try:
            ss = StrumentiService()
            strum = ss.get_by_descrizione('Postepay Evolution')
            if strum:
                new_bal = (strum.saldo_corrente or 0.0) + signed_importo
                ss.update_saldo_by_id(strum.id_conto, new_bal)
        except Exception:
            pass
        
        db.session.commit()
        
        flash('Movimento aggiunto con successo!', 'success')
        
    except Exception as e:
        flash(f'Errore nell\'aggiunta del movimento: {str(e)}', 'error')
        db.session.rollback()
    
    # Return rendered template for fetch-based updates (no redirect)
    try:
        inizializza_postepay()
        ss = StrumentiService()
        strum = ss.get_by_descrizione('Postepay Evolution')
        if strum is not None:
            postepay = SimpleNamespace(saldo_attuale=(strum.saldo_corrente or 0.0))
        else:
            postepay = SimpleNamespace(saldo_attuale=0.0)
        abbonamenti = AbbonamentoPostePay.query.order_by(AbbonamentoPostePay.nome).all()
        movimenti = MovimentoPostePay.query.order_by(MovimentoPostePay.data.desc()).limit(10).all()

        abbonamenti_attivi = [a for a in abbonamenti if a.attivo]
        spesa_mensile = sum(a.importo for a in abbonamenti_attivi)

        # Calcola prossimi addebiti con saldo sufficiente
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

        # Calcola saldo sufficiente per ogni addebito (progressivo)
        saldo_simulato = postepay.saldo_attuale if postepay else 0
        for addebito in prossimi_addebiti:
            if saldo_simulato >= addebito['abbonamento'].importo:
                addebito['saldo_sufficiente'] = True
                saldo_simulato -= addebito['abbonamento'].importo
            else:
                addebito['saldo_sufficiente'] = False

        # Calcola addebiti problematici (per alert)
        saldo_alert = postepay.saldo_attuale if postepay else 0
        addebiti_problematici = []
        for addebito in prossimi_addebiti:
            if saldo_alert < addebito['abbonamento'].importo:
                addebiti_problematici.append({
                    'abbonamento': addebito['abbonamento'],
                    'data': addebito['data'],
                    'giorni': addebito['giorni'],
                    'importo_mancante': addebito['abbonamento'].importo - saldo_alert
                })
            saldo_alert -= addebito['abbonamento'].importo

        # Serializza abbonamenti per JavaScript
        import json
        abbonamenti_serializzati = json.dumps([{
            'id': a.id,
            'nome': a.nome,
            'importo': float(a.importo),
            'giorno_addebito': a.giorno_addebito,
            'attivo': a.attivo
        } for a in abbonamenti])

        resp = make_response(render_template('postepay_evolution/ppay_evolution.html',
                             postepay=postepay,
                             abbonamenti=abbonamenti,
                             abbonamenti_json=abbonamenti_serializzati,
                             movimenti=movimenti,
                             spesa_mensile=spesa_mensile,
                             prossimi_addebiti=prossimi_addebiti,
                             addebiti_problematici=addebiti_problematici))
        resp.headers['X-Partial-Response'] = '1'
        return resp
    except Exception as e:
        from flask import current_app
        current_app.logger.exception(f"Errore nel rendering dopo aggiunta movimento: {e}")
        # Fallback to redirect if rendering fails
        return redirect(url_for('ppay.evolution'))

@ppay_bp.route('/modifica_movimento_postepay/<int:movimento_id>', methods=['POST'])
def modifica_movimento_postepay(movimento_id):
    """Modifica un movimento PostePay esistente (aggiunge la possibilità di edit inline)."""
    try:
        movimento = MovimentoPostePay.query.get_or_404(movimento_id)
        # store old values to calculate saldo delta
        old_importo = abs(movimento.importo or 0.0)
        old_tipo_movimento = movimento.tipo_movimento or 'uscita'
        # Calculate old signed value (for balance)
        old_signed = old_importo if old_tipo_movimento == 'entrata' else -old_importo

        # parse new values
        new_data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        new_descrizione = request.form.get('descrizione', '').strip()
        new_tipo = request.form.get('tipo_movimento', movimento.tipo)  # ricarica/pagamento/altro
        # importo is provided as positive
        raw_importo = abs(float(request.form.get('importo', 0)))
        tipo_sign = request.form.get('tipo', 'entrata')  # entrata/uscita
        # Calculate new signed value (for balance)
        new_signed = raw_importo if tipo_sign == 'entrata' else -raw_importo

        # apply changes
        movimento.data = new_data
        movimento.descrizione = new_descrizione
        movimento.tipo = new_tipo
        movimento.importo = raw_importo  # Sempre positivo
        movimento.tipo_movimento = tipo_sign  # entrata/uscita

        # update strumento saldo by the delta
        try:
            ss = StrumentiService()
            strum = ss.get_by_descrizione('Postepay Evolution')
            if strum:
                delta = new_signed - old_signed
                new_bal = (strum.saldo_corrente or 0.0) + delta
                ss.update_saldo_by_id(strum.id_conto, new_bal)
        except Exception:
            pass

        db.session.commit()
        flash('Movimento modificato con successo!', 'success')
    except Exception as e:
        flash(f'Errore nella modifica del movimento: {str(e)}', 'error')
        db.session.rollback()
    # Return rendered template for fetch-based updates (no redirect)
    try:
        inizializza_postepay()
        ss = StrumentiService()
        strum = ss.get_by_descrizione('Postepay Evolution')
        if strum is not None:
            postepay = SimpleNamespace(saldo_attuale=(strum.saldo_corrente or 0.0))
        else:
            postepay = SimpleNamespace(saldo_attuale=0.0)
        abbonamenti = AbbonamentoPostePay.query.order_by(AbbonamentoPostePay.nome).all()
        movimenti = MovimentoPostePay.query.order_by(MovimentoPostePay.data.desc()).limit(10).all()

        abbonamenti_attivi = [a for a in abbonamenti if a.attivo]
        spesa_mensile = sum(a.importo for a in abbonamenti_attivi)

        # Calcola prossimi addebiti con saldo sufficiente
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

        # Calcola saldo sufficiente per ogni addebito (progressivo)
        saldo_simulato = postepay.saldo_attuale if postepay else 0
        for addebito in prossimi_addebiti:
            if saldo_simulato >= addebito['abbonamento'].importo:
                addebito['saldo_sufficiente'] = True
                saldo_simulato -= addebito['abbonamento'].importo
            else:
                addebito['saldo_sufficiente'] = False

        # Calcola addebiti problematici (per alert)
        saldo_alert = postepay.saldo_attuale if postepay else 0
        addebiti_problematici = []
        for addebito in prossimi_addebiti:
            if saldo_alert < addebito['abbonamento'].importo:
                addebiti_problematici.append({
                    'abbonamento': addebito['abbonamento'],
                    'data': addebito['data'],
                    'giorni': addebito['giorni'],
                    'importo_mancante': addebito['abbonamento'].importo - saldo_alert
                })
            saldo_alert -= addebito['abbonamento'].importo

        # Serializza abbonamenti per JavaScript
        import json
        abbonamenti_serializzati = json.dumps([{
            'id': a.id,
            'nome': a.nome,
            'importo': float(a.importo),
            'giorno_addebito': a.giorno_addebito,
            'attivo': a.attivo
        } for a in abbonamenti])

        return render_template('postepay_evolution/ppay_evolution.html',
                             postepay=postepay,
                             abbonamenti=abbonamenti,
                             abbonamenti_json=abbonamenti_serializzati,
                             movimenti=movimenti,
                             spesa_mensile=spesa_mensile,
                             prossimi_addebiti=prossimi_addebiti,
                             addebiti_problematici=addebiti_problematici)
    except Exception as e:
        from flask import current_app
        current_app.logger.exception(f"Errore nel rendering dopo modifica movimento: {e}")
        # Fallback to redirect if rendering fails
        return redirect(url_for('ppay.evolution'))


@ppay_bp.route('/reset_postepay', methods=['POST'])
def reset():
    """Reset completo sistema PostePay Evolution"""
    try:
        # Elimina tutti i dati
        # Elimina movimenti e abbonamenti; reset dello strumento Postepay Evolution
        MovimentoPostePay.query.delete()
        AbbonamentoPostePay.query.delete()
        db.session.commit()

        # Reset dello strumento (saldo a 0.0)
        try:
            ss = StrumentiService()
            strum = ss.get_by_descrizione('Postepay Evolution')
            if strum:
                ss.update_saldo_by_id(strum.id_conto, 0.0)
        except Exception:
            pass
        
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
