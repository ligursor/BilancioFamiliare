"""
Service per la gestione del dettaglio periodo - implementazione originale app.py
"""
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from app.models.transazioni import Transazione
from app.models.base import Categoria, SaldoIniziale
from app.models.budget import Budget
from app.models.monthly_budget import MonthlyBudget
from app.services import get_month_boundaries
from app import db

class DettaglioPeriodoService:
    """Service per il dettaglio periodo - fedele all'implementazione originale"""
    
    def __init__(self):
        pass
    
    def get_dettaglio_mese(self, anno, mese, categoria_id=None):
        """
        Implementazione fedele della funzione dettaglio_periodo_interno dell'app.py originale
        """
        # Costruisci le date di inizio e fine
        data_mese = date(anno, mese, 1)
        start_date, end_date = get_month_boundaries(data_mese)

        return self.dettaglio_periodo_interno(start_date, end_date, categoria_id=categoria_id)
    
    def dettaglio_periodo_interno(self, start_date, end_date, categoria_id=None):
        """Funzione interna per gestire il dettaglio del periodo - copia fedele da app.py"""
        
        # Prendi tutte le transazioni del periodo (escluse PayPal)
        query = Transazione.query.filter(
            Transazione.data >= start_date,
            Transazione.data <= end_date,
            Transazione.categoria_id.isnot(None)  # Escludi transazioni PayPal (senza categoria)
        )
        if categoria_id:
            query = query.filter(Transazione.categoria_id == categoria_id)
        transazioni = query.order_by(Transazione.data.desc()).all()
        
        # Separa transazioni effettuate da quelle in attesa
        transazioni_effettuate = []
        transazioni_in_attesa = []
        oggi = datetime.now().date()
        
        for t in transazioni:
            # Una transazione è effettuata se ha data_effettiva O se la data è nel passato/presente
            if t.data_effettiva is not None or t.data <= oggi:
                transazioni_effettuate.append(t)
            else:
                transazioni_in_attesa.append(t)
        
        # Filtra manualmente per evitare duplicazioni madri/figlie nello stesso mese (solo per quelle effettuate)
        transazioni_filtrate = []
        for t in transazioni_effettuate:
            if t.ricorrente == 0:  # Figlie e manuali: sempre incluse
                transazioni_filtrate.append(t)
            elif t.ricorrente == 1:  # Madri: includi solo se non hanno figlie nello stesso mese
                # Controlla se esistono figlie di questa madre nello stesso mese
                ha_figlie_stesso_mese = any(
                    f.transazione_madre_id == t.id and 
                    f.data.month == t.data.month and 
                    f.data.year == t.data.year
                    for f in transazioni_effettuate if f.ricorrente == 0 and f.transazione_madre_id
                )
                if not ha_figlie_stesso_mese:
                    transazioni_filtrate.append(t)
        
        transazioni_effettuate = transazioni_filtrate
        
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
        bilancio_totale_previsto = entrate_totali_previste - uscite_totali_previste
        
        # Calcola il saldo iniziale per questo mese specifico
        saldo_base = SaldoIniziale.query.first()
        saldo_base_importo = saldo_base.importo if saldo_base else 0.0
        
        # Calcola tutti i bilanci dei mesi precedenti a questo
        oggi = datetime.now().date()
        saldo_iniziale_mese = saldo_base_importo
        
        # Ottieni i confini del mese corrente
        mese_oggi_start, mese_oggi_end = get_month_boundaries(oggi)
        
        # Itera sui mesi dal mese corrente fino al mese richiesto
        mese_corrente = oggi
        
        while True:
            mese_corrente_start, mese_corrente_end = get_month_boundaries(mese_corrente)
            
            # Se siamo arrivati al mese target, fermiamoci
            if mese_corrente_start >= start_date:
                break
                
            # Calcola il bilancio di questo mese e aggiungilo al saldo
            tutte_transazioni_mese = Transazione.query.filter(
                Transazione.data >= mese_corrente_start,
                Transazione.data <= mese_corrente_end,
                Transazione.categoria_id.isnot(None)  # Escludi transazioni PayPal (senza categoria)
            ).all()
            # Applica filtro per categoria anche ai conteggi mensili quando richiesto
            if categoria_id:
                tutte_transazioni_mese = [t for t in tutte_transazioni_mese if t.categoria_id == categoria_id]
            
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
            
            # Filtra per evitare duplicazioni madri/figlie
            def calcola_bilancio_mese(lista_transazioni):
                entrate_mese = 0
                uscite_mese = 0
                for t in lista_transazioni:
                    includi = False
                    if t.ricorrente == 0:  # Figlie e manuali: sempre incluse
                        includi = True
                    elif t.ricorrente == 1:  # Madri: includi solo se non hanno figlie nello stesso mese
                        ha_figlie_stesso_mese = any(
                            f.transazione_madre_id == t.id and 
                            f.data.month == t.data.month and 
                            f.data.year == t.data.year
                            for f in lista_transazioni if f.ricorrente == 0 and f.transazione_madre_id
                        )
                        if not ha_figlie_stesso_mese:
                            includi = True
                    
                    if includi:
                        if t.tipo == 'entrata':
                            entrate_mese += t.importo
                        else:
                            uscite_mese += t.importo
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
        # Saldo finale = saldo attuale + bilancio delle transazioni in attesa
        bilancio_in_attesa = entrate_in_attesa - uscite_in_attesa
        
        saldo_finale_mese = saldo_attuale_mese + bilancio_in_attesa

        # --- Calcolo budget totale e residuo ---
        # Calcolo breakdown budget per categoria: iniziale, spese effettuate, pianificate, residuo
        try:
            budgets = Budget.query.all()
            budget_items = []
            # Prepara lookup sulle categorie per nome e tipo
            categoria_lookup = {c.id: c for c in Categoria.query.all()}

            for b in budgets:
                # Se è stato passato un filtro categoria e non coincide con questo budget, saltalo
                if categoria_id and b.categoria_id != categoria_id:
                    continue
                cat_id = b.categoria_id
                cat = categoria_lookup.get(cat_id)
                nome_cat = cat.nome if cat else f'Categoria {cat_id}'
                tipo_cat = cat.tipo if cat else 'uscita'

                spese_effettuate = sum(
                    t.importo for t in transazioni_effettuate
                    if t.tipo == 'uscita' and t.categoria_id == cat_id
                )
                spese_pianificate = sum(
                    t.importo for t in transazioni_in_attesa
                    if t.tipo == 'uscita' and t.categoria_id == cat_id
                )

                # Recupera o crea il MonthlyBudget per il mese richiesto
                try:
                    mb = MonthlyBudget.query.filter_by(categoria_id=cat_id, year=start_date.year, month=start_date.month).first()
                    if not mb:
                        # Usa il default dal Budget
                        iniziale_month = float(b.importo or 0.0)
                        mb = MonthlyBudget(categoria_id=cat_id, year=start_date.year, month=start_date.month, importo=iniziale_month)
                        db.session.add(mb)
                        db.session.commit()
                        # Audit: creazione automatica mensile
                        try:
                            from app.models.monthly_budget_audit import MonthlyBudgetAudit
                            audit = MonthlyBudgetAudit(monthly_budget_id=mb.id, categoria_id=cat_id, year=start_date.year, month=start_date.month, old_importo=None, new_importo=iniziale_month, changed_by='system')
                            db.session.add(audit)
                            db.session.commit()
                        except Exception:
                            db.session.rollback()
                    iniziale = float(mb.importo or 0.0)
                except Exception:
                    # In caso di problemi con MonthlyBudget, ricadi sul default
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

        # Somma dei residui positivi dei budget
        try:
            somma_residui_positivi = sum(max(item.get('residuo', 0.0), 0.0) for item in budget_items)
        except Exception:
            somma_residui_positivi = 0.0

        # Aggiorna le uscite previste includendo i residui positivi
        uscite_adjusted = (uscite_totali_previste if 'uscite_totali_previste' in locals() else uscite_totali_previste) + somma_residui_positivi
        bilancio_adjusted = entrate_totali_previste - uscite_adjusted
        
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
            # Breakdown dei budget per categoria
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
        """
        Calcola le statistiche per categoria per un mese specifico
        """
        try:
            # Query per categoria con somma importi
            from sqlalchemy import extract, func
            query = db.session.query(
                Categoria.id,
                Categoria.nome,
                Categoria.tipo,
                func.sum(Transazione.importo).label('totale'),
                func.count(Transazione.id).label('num_transazioni')
            ).join(Categoria).filter(
                extract('year', Transazione.data) == anno,
                extract('month', Transazione.data) == mese,
                Categoria.nome != 'PayPal'  # Escludi PayPal
            ).group_by(Categoria.id, Categoria.nome, Categoria.tipo).all()
            
            stats = []
            for row in query:
                stats.append({
                    'id': row.id,
                    'nome': row.nome,
                    'tipo': row.tipo,
                    'totale': float(row.totale) if row.totale else 0.0,
                    'num_transazioni': row.num_transazioni
                })
            
            return stats
            
        except Exception as e:
            print(f"Errore nel calcolo statistiche per categoria: {e}")
            return []
