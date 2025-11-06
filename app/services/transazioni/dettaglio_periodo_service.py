"""Service per la gestione del dettaglio periodo - implementazione originale app.py"""
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from app.models.Transazioni import Transazioni
from app.models.Categorie import Categorie
from app.services.conti_finanziari.strumenti_service import StrumentiService
from app.models.Budget import Budget
from app.models.BudgetMensili import BudgetMensili
from app.services import get_month_boundaries
from app import db

class DettaglioPeriodoService:
    """Service per il dettaglio periodo - fedele all'implementazione originale"""
    
    def __init__(self):
        pass
    
    def get_dettaglio_mese(self, anno, mese):
        """Implementazione fedele della funzione dettaglio_periodo_interno dell'app.py originale"""
        # Costruisci le date di inizio e fine
        data_mese = date(anno, mese, 1)
        start_date, end_date = get_month_boundaries(data_mese)

        return self.dettaglio_periodo_interno(start_date, end_date)
    
    def dettaglio_periodo_interno(self, start_date, end_date):
        """Funzione interna per gestire il dettaglio del periodo - copia fedele da app.py"""
        
        # Prefer to fetch transactions by `id_periodo` (YYYYMM) when possible to
        # take advantage of the index. `id_periodo` represents the financial
        # month containing `end_date`.
        try:
            period_id = int(get_month_boundaries(end_date)[1].year) * 100 + int(get_month_boundaries(end_date)[1].month)
            query = Transazioni.query.filter(
                Transazioni.id_periodo == period_id,
                Transazioni.categoria_id.isnot(None)
            )
            transazioni = query.order_by(Transazioni.data.desc()).all()
        except Exception:
            # Fallback to date range if id_periodo is not available in the schema
            query = Transazioni.query.filter(
                Transazioni.data >= start_date,
                Transazioni.data <= end_date,
                Transazioni.categoria_id.isnot(None)  # Escludi transazioni PayPal (senza categorie)
            )
            transazioni = query.order_by(Transazioni.data.desc()).all()
        
        # Separa transazioni effettuate da quelle in attesa
        transazioni_effettuate = []
        transazioni_in_attesa = []
        oggi = datetime.now().date()
        
        for t in transazioni:
            # Una transazioni è effettuata se ha data_effettiva O se la data è nel passato/presente
            if t.data_effettiva is not None or t.data <= oggi:
                transazioni_effettuate.append(t)
            else:
                transazioni_in_attesa.append(t)

        # Ensure both performed and pending transactions are ordered in ascending order (oldest -> newest)
        try:
            transazioni_effettuate.sort(key=lambda x: x.data)
        except Exception:
            # If sorting fails for any reason, ignore to avoid breaking the view
            pass
        try:
            transazioni_in_attesa.sort(key=lambda x: x.data)
        except Exception:
            # If sorting fails for any reason, ignore to avoid breaking the view
            pass

        # Non applichiamo più logica madre/figlia: tutte le transazioni effettuate sono incluse
        # (le transazioni ricorrenti vengono gestite da reset/rollover tramite la tabella delle ricorrenze)
        transazioni_effettuate = transazioni_effettuate

        # Calcola totali effettuati (solo transazioni effettuate)
        entrate_effettuate = sum(t.importo for t in transazioni_effettuate if t.tipo == 'entrata')
        uscite_effettuate = sum(t.importo for t in transazioni_effettuate if t.tipo == 'uscita')
        bilancio_effettuato = entrate_effettuate - uscite_effettuate

        # Calcola totali in attesa
        entrate_in_attesa = sum(t.importo for t in transazioni_in_attesa if t.tipo == 'entrata')
        uscite_in_attesa = sum(t.importo for t in transazioni_in_attesa if t.tipo == 'uscita')

        # Calcola totali previsti (effettuate + in attesa)
        entrate_totali_previste = entrate_effettuate + entrate_in_attesa
        uscite_totali_previste = uscite_effettuate + uscite_in_attesa

        # Sottrai dalle uscite previste il totale delle transazioni di tipo 'uscita'
        # con categoria 'Correzione Saldo' — queste rappresentano adeguamenti che
        # non devono essere contate nelle uscite previste ordinarie.
        try:
            correzioni_effettuate = sum(
                t.importo for t in transazioni_effettuate
                if t.tipo == 'uscita' and getattr(getattr(t, 'categoria', None), 'nome', None) == 'Correzione Saldo'
            )
            correzioni_in_attesa = sum(
                t.importo for t in transazioni_in_attesa
                if t.tipo == 'uscita' and getattr(getattr(t, 'categoria', None), 'nome', None) == 'Correzione Saldo'
            )
            correzioni_totali = float(correzioni_effettuate or 0.0) + float(correzioni_in_attesa or 0.0)
            uscite_totali_previste = max(0.0, float(uscite_totali_previste or 0.0) - correzioni_totali)
        except Exception:
            # Se qualcosa va storto, non blocchiamo la vista: manteniamo il valore originale
            pass
        bilancio_totale_previsto = entrate_totali_previste - uscite_totali_previste

        # Calcola il saldo iniziale per questo mese specifico
        try:
            ss = StrumentiService()
            s = ss.get_by_descrizione('Conto Bancoposta')
            saldo_base_importo = float(s.saldo_iniziale if s and s.saldo_iniziale is not None else 0.0)
        except Exception:
            saldo_base_importo = 0.0

        # Determina la data di partenza per l'accumulazione: we no longer
        # persist a global SaldoIniziale with an update timestamp, so fall back
        # to the first transaction as anchor (same behavior when no saldo record).
        first_trans = Transazioni.query.order_by(Transazioni.data.asc()).first()
        anchor_date = first_trans.data if first_trans else start_date

        # Ottieni i confini del mese dell'ancora
        mese_corrente = anchor_date

        # Inizializza il saldo iniziale del mese a partire dal valore base
        # (se presente) — serve come punto di partenza per l'accumulazione
        # nei cicli successivi.
        saldo_iniziale_mese = float(saldo_base_importo or 0.0)

        # Confini del "mese odierno" (usati per decidere cosa considerare effettuato)
        oggi = datetime.now().date()
        mese_oggi_start, mese_oggi_end = get_month_boundaries(oggi)

        # Itera sui mesi cronologicamente dall'ancora fino al mese target
        while True:
            mese_corrente_start, mese_corrente_end = get_month_boundaries(mese_corrente)

            # Se siamo arrivati al mese target (o oltre), fermiamoci
            if mese_corrente_start >= start_date:
                break

            # Calcola il bilancio di questo mese e aggiungilo al saldo
            # Use id_periodo to fetch transactions for the current financial month
            try:
                mese_id = int(get_month_boundaries(mese_corrente)[1].year) * 100 + int(get_month_boundaries(mese_corrente)[1].month)
                tutte_transazioni_mese = Transazioni.query.filter(
                    Transazioni.id_periodo == mese_id,
                    Transazioni.categoria_id.isnot(None)
                ).all()
            except Exception:
                tutte_transazioni_mese = Transazioni.query.filter(
                    Transazioni.data >= mese_corrente_start,
                    Transazioni.data <= mese_corrente_end,
                    Transazioni.categoria_id.isnot(None)
                ).all()
            # Do not apply category filter to monthly aggregates (categorie filtering removed)
            
            # Per mesi passati, usa solo transazioni effettuate
            # Per mese corrente e futuri, includi tutte le transazioni (per saldo finale)
            filtra_solo_effettuate = mese_corrente_end < mese_oggi_start

            # Separa transazioni effettuate da quelle in attesa per questo mese
            transazioni_mese_effettuate = []
            transazioni_mese_in_attesa = []
            
            for t in tutte_transazioni_mese:
                if t.data_effettiva is not None or t.data <= oggi:
                    transazioni_mese_effettuate.append(t)
                else:
                    transazioni_mese_in_attesa.append(t)

            # Nessuna logica madre/figlia: sommiamo tutte le transazioni nella lista
            def calcola_bilancio_mese(lista_transazioni):
                entrate_mese = 0
                uscite_mese = 0
                for t in lista_transazioni:
                    try:
                        if t.tipo == 'entrata':
                            entrate_mese += t.importo
                        else:
                            uscite_mese += t.importo
                    except Exception:
                        continue
                return entrate_mese - uscite_mese
            
            # Per mesi passati: usa solo transazioni effettuate
            # Per mese corrente/futuri: usa saldo finale (effettuate + in attesa)
            if filtra_solo_effettuate:
                bilancio_mese = calcola_bilancio_mese(transazioni_mese_effettuate)
            else:
                # Per mese corrente e futuri, usa il saldo finale previsto
                bilancio_effettuato = calcola_bilancio_mese(transazioni_mese_effettuate)
                bilancio_in_attesa = calcola_bilancio_mese(transazioni_mese_in_attesa)
                bilancio_mese = bilancio_effettuato + bilancio_in_attesa
            
            saldo_iniziale_mese += bilancio_mese
            
            # Passa al mese successivo
            mese_corrente = mese_corrente + relativedelta(months=1)
        
        # Calcola saldo attuale (solo transazioni già effettuate) se il periodo include la data odierna
        saldo_attuale_mese = saldo_iniziale_mese
        oggi = datetime.now().date()
        
        if start_date <= oggi <= end_date:
            # Filtra solo le transazioni già effettuate (data <= oggi)
            entrate_effettuate = 0
            uscite_effettuate = 0
            for t in transazioni_effettuate:
                if t.data <= oggi:
                    if t.tipo == 'entrata':
                        entrate_effettuate += t.importo
                    else:
                        uscite_effettuate += t.importo
            
            saldo_attuale_mese = saldo_iniziale_mese + entrate_effettuate - uscite_effettuate
        else:
            # Se il periodo non include oggi, saldo attuale = saldo iniziale + bilancio effettuato
            saldo_attuale_mese = saldo_iniziale_mese + bilancio_effettuato

        # Calcola il saldo finale (previsione di fine mese)
        # Per coerenza con la dashboard, il saldo finale viene calcolato
        # come saldo iniziale del mese + il bilancio totale previsto
        # (ovvero entrate previste - uscite previste). In questo modo
        # dettaglio e dashboard useranno la stessa regola.
        try:
            bilancio_totale_previsto = entrate_totali_previste - uscite_totali_previste
        except Exception:
            # Fallback: se per qualche motivo le variabili non sono disponibili,
            # ricadiamo sul vecchio calcolo basato sulle transazioni in attesa
            bilancio_totale_previsto = (entrate_in_attesa - uscite_in_attesa) if ('entrate_in_attesa' in locals() and 'uscite_in_attesa' in locals()) else 0.0

        saldo_finale_mese = saldo_iniziale_mese + bilancio_totale_previsto

        # --- Calcolo budget totale e residuo ---
        # Calcolo breakdown budget per categorie: iniziale, spese effettuate, pianificate, residuo
        try:
            budgets = Budget.query.all()
            budget_items = []
            # Prepara lookup sulle categorie per nome e tipo
            categoria_lookup = {c.id: c for c in Categorie.query.all()}

            for b in budgets:
                # Include all budgets (categorie filtering removed)
                cat_id = b.categoria_id
                cat = categoria_lookup.get(cat_id)
                nome_cat = cat.nome if cat else f'Categorie {cat_id}'
                tipo_cat = cat.tipo if cat else 'uscita'

                spese_effettuate = sum(
                    t.importo for t in transazioni_effettuate
                    if t.tipo == 'uscita' and t.categoria_id == cat_id
                )
                spese_pianificate = sum(
                    t.importo for t in transazioni_in_attesa
                    if t.tipo == 'uscita' and t.categoria_id == cat_id
                )

                # Recupera o crea il BudgetMensili per il mese richiesto
                try:
                    # Use end_date to determine the target month for monthly budgets.
                    # For period views that span month boundaries (e.g. 27/10 - 26/11)
                    # budgets should belong to the month containing the period end.
                    mb = BudgetMensili.query.filter_by(categoria_id=cat_id, year=end_date.year, month=end_date.month).first()
                    if not mb:
                        # Usa il default dal Budget
                        iniziale_month = float(b.importo or 0.0)
                        mb = BudgetMensili(categoria_id=cat_id, year=end_date.year, month=end_date.month, importo=iniziale_month)
                        db.session.add(mb)
                        db.session.commit()
                        # Audit: creazione automatica mensile
                        try:
                            # MonthlyBudgetAudit model rimosso: loggiamo l'evento invece di persistere il record
                            import logging
                            logger = logging.getLogger('bilancio.monthly_budget_audit')
                            logger.info(
                                "monthly_budget_audit: created by system - monthly_budget_id=%s categoria_id=%s year=%s month=%s new_importo=%s",
                                mb.id, cat_id, start_date.year, start_date.month, iniziale_month
                            )
                            # Manteniamo il commit della creazione del BudgetMensili (mb) sopra
                        except Exception:
                            # In caso di problemi con il logging, non vogliamo lasciare la sessione sporca
                            try:
                                db.session.rollback()
                            except Exception:
                                pass
                    iniziale = float(mb.importo or 0.0)
                except Exception:
                    # In caso di problemi con BudgetMensili, ricadi sul default
                    iniziale = float(b.importo or 0.0)

                decurtato = spese_effettuate + spese_pianificate
                residuo = iniziale - decurtato

                budget_items.append({
                    'categoria_id': cat_id,
                    'categoria_nome': nome_cat,
                    'categoria_tipo': tipo_cat,
                    'iniziale': iniziale,
                    'spese_effettuate': float(spese_effettuate or 0.0),
                    'spese_pianificate': float(spese_pianificate or 0.0),
                    'residuo': float(residuo)
                })
        except Exception:
            budget_items = []

        # Somma dei residui di budget per il mese
        # Nuova regola: Uscite previste = somma delle transazioni in uscita (effettuate + in attesa) + somma dei residui di budget
        try:
            # Considera solo residui positivi: sum(max(residuo, 0))
            somma_residui = sum(max(float(item.get('residuo', 0.0) or 0.0), 0.0) for item in budget_items)
        except Exception:
            somma_residui = 0.0

        try:
            uscite_adjusted = float(uscite_totali_previste or 0.0) + float(somma_residui or 0.0)
        except Exception:
            try:
                uscite_adjusted = float(uscite_totali_previste) + float(somma_residui)
            except Exception:
                uscite_adjusted = 0.0

        # Normalizza e previeni negativi
        try:
            uscite_adjusted = max(0.0, float(uscite_adjusted or 0.0))
        except Exception:
            uscite_adjusted = float(uscite_adjusted) if isinstance(uscite_adjusted, (int, float)) else 0.0

        bilancio_adjusted = entrate_totali_previste - uscite_adjusted
        # Allinea il saldo finale con il bilancio "adjusted" (inclusi residui positivi)
        try:
            saldo_finale_mese = saldo_iniziale_mese + bilancio_adjusted
        except Exception:
            # se qualcosa manca, ricadiamo sul valore già calcolato in precedenza
            pass
        
        # Crea un nome per il periodo
        nome_periodo = f"{start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m/%Y')}"
        
        # Determina se il mese è futuro (inizia dopo oggi)
        oggi = datetime.now().date()
        mese_futuro = start_date > oggi
        
        # Per i mesi futuri, calcola un saldo previsto più semplice
        if mese_futuro:
            saldo_previsto_fine_mese = saldo_iniziale_mese + entrate_totali_previste - uscite_totali_previste
        else:
            saldo_previsto_fine_mese = saldo_finale_mese
        
        return {
            'transazioni': transazioni_effettuate,
            'transazioni_in_attesa': transazioni_in_attesa,
            'nome_mese': nome_periodo,
            # Breakdown dei budget per categorie
            'budget_items': budget_items,
            'entrate': entrate_totali_previste,
            'uscite': uscite_adjusted,
            'uscite_original': uscite_totali_previste,
            'bilancio': bilancio_adjusted,
            'bilancio_original': bilancio_totale_previsto,
            'entrate_effettuate': entrate_effettuate,
            'uscite_effettuate': uscite_effettuate,
            'entrate_in_attesa': entrate_in_attesa,
            'uscite_in_attesa': uscite_in_attesa,
            'saldo_iniziale_mese': saldo_iniziale_mese,
            'saldo_finale_mese': saldo_finale_mese,
            'saldo_attuale_mese': saldo_attuale_mese,
            'saldo_previsto_fine_mese': saldo_previsto_fine_mese,
            'mese_futuro': mese_futuro,
            'start_date': start_date,
            'end_date': end_date
        }

    def get_statistiche_per_categoria(self, anno, mese):
        """Ritorna statistiche (totali uscita) per categorie per il mese richiesto."""
        try:
            from datetime import date

            data_mese = date(anno, mese, 1)
            start_date, end_date = get_month_boundaries(data_mese)

            # Consideriamo solo le transazioni di tipo 'uscita' con categorie
            transazioni = Transazioni.query.filter(
                Transazioni.data >= start_date,
                Transazioni.data <= end_date,
                Transazioni.categoria_id.isnot(None),
                Transazioni.tipo == 'uscita'
            ).all()

            # Somma per categorie
            totals = {}
            for t in transazioni:
                cid = t.categoria_id
                try:
                    val = float(t.importo or 0.0)
                except Exception:
                    val = 0.0
                totals[cid] = totals.get(cid, 0.0) + val

            # Recupera nomi categorie
            categoria_lookup = {c.id: c for c in Categorie.query.all()}

            stats = []
            for cid, val in totals.items():
                cat = categoria_lookup.get(cid)
                nome = cat.nome if cat else f'Categorie {cid}'
                stats.append({
                    'categoria_id': cid,
                    'categoria_nome': nome,
                    'importo': float(val)
                })

            # Ordina per importo decrescente
            stats.sort(key=lambda x: x.get('importo', 0.0), reverse=True)
            return stats
        except Exception:
            # In caso di problemi, restituiamo una lista vuota per non rompere la view
            return []
