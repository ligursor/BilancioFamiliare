"""Service implementing the monthly rollover logic (extracted from scripts/monthly_rollover.py)."""
from app.services import get_month_boundaries
from datetime import date
from dateutil.relativedelta import relativedelta
from app import db
from sqlalchemy import text


def do_monthly_rollover(force=False, months=1, base_date=None):
    """Perform monthly rollover with new logic:
    
    1. Genera solo transazioni ricorrenti per il mese successivo all'ultimo già presente (mantiene orizzonte 6 mesi)
    2. Calcola il saldo iniziale del mese corrente = saldo_finale + budget_residui del mese precedente
    3. Svuota e ricrea saldi_mensili con seed = mese precedente + nuovo saldo calcolato
    4. Elimina le transazioni del mese precedente (pulizia storico)
    """
    if base_date is None:
        base_date = date.today()

    # Il mese corrente è quello in cui ci troviamo oggi
    current_month_start, current_month_end = get_month_boundaries(base_date)
    
    # Il mese precedente
    prev_month_date = base_date - relativedelta(months=1)
    prev_month_start, prev_month_end = get_month_boundaries(prev_month_date)

    result = {
        'force': bool(force),
        'deleted_old_transactions': 0,
        'created_generated_transactions': 0,
        'deleted_saldi_mensili': 0,
        'new_seed_created': False,
        'seed_saldo_iniziale': 0.0,
        'total_budget_residui': 0.0,
    }

    try:
        # STEP 1: Calcola i residui del mese precedente e aggiorna budget_mensili
        from app.services.budget.budget_mensili_service import BudgetMensiliService
        from app.services.transazioni.dettaglio_periodo_service import DettaglioPeriodoService
        
        budget_service = BudgetMensiliService()
        dettaglio_service = DettaglioPeriodoService()
        
        # Calcola i dettagli del mese precedente per avere i residui corretti
        # Request period details without creating/persisting monthly budgets for the seed month
        prev_month_details = dettaglio_service.dettaglio_periodo_interno(prev_month_start, prev_month_end, create_monthly_budget=False)
        budget_items = prev_month_details.get('budget_items', [])
        
        # Aggiorna i residui_mensili nel database per il mese precedente
        if budget_items:
            total_residui = budget_service.calculate_and_save_all_residui(
                prev_month_end.year, 
                prev_month_end.month, 
                budget_items
            )
            result['total_budget_residui'] = float(total_residui)
        
        # STEP 2: Recupera il saldo_finale del mese precedente
        from app.models.SaldiMensili import SaldiMensili
        prev_saldo_row = SaldiMensili.query.filter_by(
            year=prev_month_end.year,
            month=prev_month_end.month
        ).first()
        
        saldo_finale_prev = 0.0
        if prev_saldo_row:
            saldo_finale_prev = float(prev_saldo_row.saldo_finale or 0.0)
        
        # Calcola il nuovo saldo iniziale: saldo_finale precedente + residui budget precedente
        new_seed_saldo = saldo_finale_prev + result['total_budget_residui']
        result['seed_saldo_iniziale'] = float(new_seed_saldo)
        
        # STEP 3: Archivia ed elimina transazioni del mese precedente (pulizia storico)
        try:
            from app.models.Transazioni import Transazioni
            from app.models.TransazioniArchivio import TransazioniArchivio
            from app.models.Categorie import Categorie
            
            # Recupera tutte le transazioni del mese precedente
            old_transactions = db.session.query(Transazioni).filter(
                Transazioni.data < current_month_start
            ).all()
            
            archived_count = 0
            # Archivia ogni transazione prima di eliminarla
            for tx in old_transactions:
                # Recupera il nome della categoria per denormalizzazione
                categoria_nome = None
                if tx.categoria_id:
                    cat = db.session.query(Categorie).filter_by(id=tx.categoria_id).first()
                    if cat:
                        categoria_nome = cat.nome
                
                # Crea record di archivio
                archived_tx = TransazioniArchivio(
                    transazione_id=tx.id,
                    data=tx.data,
                    data_effettiva=tx.data_effettiva,
                    descrizione=tx.descrizione,
                    importo=tx.importo,
                    categoria_id=tx.categoria_id,
                    categoria_nome=categoria_nome,
                    id_periodo=tx.id_periodo,
                    tipo=tx.tipo,
                    tx_ricorrente=tx.tx_ricorrente,
                    id_recurring_tx=tx.id_recurring_tx,
                    tx_modificata=tx.tx_modificata
                )
                db.session.add(archived_tx)
                archived_count += 1
            
            # Commit dell'archiviazione
            db.session.commit()
            result['archived_transactions'] = archived_count
            
            # Ora elimina le transazioni archiviate
            deleted_old = db.session.query(Transazioni).filter(
                Transazioni.data < current_month_start
            ).delete(synchronize_session=False)
            db.session.commit()
            result['deleted_old_transactions'] = int(deleted_old)
        except Exception as e:
            db.session.rollback()
            result['delete_old_error'] = str(e)
        
        # STEP 4: Trova l'ultimo mese con transazioni generate per determinare da dove generare
        try:
            # Trova l'id_periodo massimo presente nelle transazioni generate
            max_periodo = db.session.execute(
                text('SELECT MAX(id_periodo) FROM transazioni WHERE id_recurring_tx IS NOT NULL')
            ).fetchone()[0]
            
            if max_periodo:
                # Estrai year e month dall'id_periodo (formato YYYYMM)
                last_year = max_periodo // 100
                last_month = max_periodo % 100
                last_gen_date = date(last_year, last_month, 1)
                
                # Genera transazioni per il mese successivo all'ultimo presente
                next_gen_date = last_gen_date + relativedelta(months=1)
            else:
                # Nessuna transazione generata, inizia dal mese corrente
                next_gen_date = current_month_start
            
            # Genera transazioni ricorrenti solo per il mese successivo (mantenendo orizzonte ~6 mesi)
            from app.services.transazioni.generated_transaction_service import GeneratedTransactionService
            gen_service = GeneratedTransactionService()
            
            created = gen_service.populate_horizon_from_recurring(
                months=1,  # Solo il prossimo mese
                base_date=next_gen_date,
                create_only_future=True,
                mark_generated_tx_modificata=False
            )
            result['created_generated_transactions'] = int(created or 0)
            
        except Exception as e:
            result['generation_error'] = str(e)
        
        # STEP 5: Svuota e ricrea saldi_mensili con seed = mese precedente
        try:
            # Elimina tutti i saldi_mensili esistenti
            deleted_count = SaldiMensili.query.delete()
            db.session.commit()
            result['deleted_saldi_mensili'] = int(deleted_count)
            
            # Crea il nuovo seed per il mese precedente
            seed_row = SaldiMensili(
                year=prev_month_end.year,
                month=prev_month_end.month,
                saldo_iniziale=new_seed_saldo,
                entrate=0.0,
                uscite=0.0,
                saldo_finale=new_seed_saldo,
                is_seed=True
            )
            db.session.add(seed_row)
            db.session.commit()
            result['new_seed_created'] = True

            # Aggiorna anche il saldo_iniziale dello strumento 'Conto Bancoposta'
            # in modo che il nuovo seed venga riflesso come saldo iniziale dell'account.
            try:
                from app.services.conti_finanziari.strumenti_service import StrumentiService
                ss = StrumentiService()
                s = ss.get_by_descrizione('Conto Bancoposta')
                if s:
                    # update_saldo_iniziale_by_id adjusts saldo_corrente in modo coerente
                    ss.update_saldo_iniziale_by_id(s.id_conto, float(new_seed_saldo or 0.0))
                else:
                    # se lo strumento non esiste, crealo con il nuovo saldo
                    ss.ensure_strumento('Conto Bancoposta', 'conto_bancario', float(new_seed_saldo or 0.0))
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
            
            # Rigenera i saldi mensili partendo dal seed
            from app.services.transazioni.monthly_summary_service import MonthlySummaryService
            msvc = MonthlySummaryService()
            
            # Rigenera per i prossimi 6 mesi a partire dal mese corrente
            regenerated = 0
            period_list = []
            for i in range(6):
                periodo_date = current_month_start + relativedelta(months=i)
                periodo_start, periodo_end = get_month_boundaries(periodo_date)

                # Assicura che i budget mensili esistano per il mese che stiamo per generare
                try:
                    # non creare/alterare budget per il mese seed (prev_month)
                    if not (periodo_end.year == prev_month_end.year and periodo_end.month == prev_month_end.month):
                        try:
                            budget_service.populate_month_from_base_budget(periodo_end.year, periodo_end.month)
                        except Exception:
                            # best-effort: non bloccare la rigenerazione se la creazione dei budget fallisce
                            pass
                except Exception:
                    pass

                ok, res = msvc.regenerate_month_summary(periodo_end.year, periodo_end.month)
                if ok:
                    regenerated += 1
                    period_list.append((periodo_end.year, periodo_end.month))

            result['monthly_summary_regenerated'] = regenerated
            
            # Applica chaining: propaga saldo_finale -> saldo_iniziale
            if period_list:
                # Aggiungi il seed all'inizio per il chaining
                full_period_list = [(prev_month_end.year, prev_month_end.month)] + period_list
                ok_chain, chain_count = msvc.chain_saldo_across(full_period_list)
                if ok_chain:
                    result['chained'] = chain_count
                else:
                    result['chain_error'] = chain_count
            
        except Exception as e:
            db.session.rollback()
            result['saldi_mensili_error'] = str(e)
        
        return result
        
    except Exception as e:
        # best-effort: return error info
        db.session.rollback()
        return {'error': str(e)}
