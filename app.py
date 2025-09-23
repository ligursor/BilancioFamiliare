from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import calendar
import os
from config import config

app = Flask(__name__)

# Carica la configurazione in base all'ambiente
config_name = os.environ.get('FLASK_ENV', 'default')
app.config.from_object(config[config_name])

db = SQLAlchemy(app)

# Aggiungi datetime al contesto dei template
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# Modelli del database
class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'entrata' o 'uscita'

class SaldoIniziale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    importo = db.Column(db.Float, nullable=False, default=0.0)
    data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
class Transazione(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    data_effettiva = db.Column(db.Date, nullable=True)  # NULL = transazione programmata, NOT NULL = transazione effettuata
    descrizione = db.Column(db.String(200), nullable=False)
    importo = db.Column(db.Float, nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)  # nullable per transazioni PayPal
    categoria = db.relationship('Categoria', backref=db.backref('transazioni', lazy=True))
    tipo = db.Column(db.String(20), nullable=False)  # 'entrata' o 'uscita'
    ricorrente = db.Column(db.Boolean, default=False)
    frequenza_giorni = db.Column(db.Integer, default=0)  # 30=mensile, 365=annuale
    transazione_madre_id = db.Column(db.Integer, db.ForeignKey('transazione.id'), nullable=True)  # collegamento alla transazione madre
    figli = db.relationship('Transazione', backref=db.backref('madre', remote_side=[id]), lazy='dynamic')
    
    @property
    def e_programmata(self):
        """Restituisce True se la transazione è programmata (data futura e non ancora effettuata)"""
        return self.data_effettiva is None and self.data > datetime.now().date()
    
    @property
    def e_effettuata(self):
        """Restituisce True se la transazione è stata effettuata (ha data_effettiva o è nel passato)"""
        return self.data_effettiva is not None or self.data <= datetime.now().date()
    
    @property
    def e_in_attesa(self):
        """Restituisce True se la transazione è in attesa (data futura e data_effettiva NULL)"""
        return self.data_effettiva is None and self.data > datetime.now().date()

class PaypalPiano(db.Model):
    """Modello per i piani di pagamento PayPal a 3 rate"""
    id = db.Column(db.Integer, primary_key=True)
    descrizione = db.Column(db.String(200), nullable=False)
    importo_totale = db.Column(db.Float, nullable=False)
    importo_rata = db.Column(db.Float, nullable=False)
    data_prima_rata = db.Column(db.Date, nullable=False)
    data_seconda_rata = db.Column(db.Date, nullable=False)
    data_terza_rata = db.Column(db.Date, nullable=False)
    importo_rimanente = db.Column(db.Float, nullable=True, default=0.0)
    stato = db.Column(db.String(20), nullable=False, default='attivo')  # 'attivo', 'completato', 'sospeso'
    note = db.Column(db.Text, nullable=True)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class PaypalRata(db.Model):
    """Modello per le singole rate dei piani PayPal"""
    id = db.Column(db.Integer, primary_key=True)
    piano_id = db.Column(db.Integer, db.ForeignKey('paypal_piano.id'), nullable=False)
    piano = db.relationship('PaypalPiano', backref=db.backref('rate', lazy=True, cascade='all, delete-orphan'))
    numero_rata = db.Column(db.Integer, nullable=False)  # 1, 2, 3
    importo = db.Column(db.Float, nullable=False)
    data_scadenza = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.Date, nullable=True)
    stato = db.Column(db.String(20), nullable=False, default='in_attesa')  # 'in_attesa', 'pagata', 'scaduta'
    transazione_id = db.Column(db.Integer, db.ForeignKey('transazione.id'), nullable=True)  # collegamento alla transazione
    transazione = db.relationship('Transazione', backref=db.backref('rata_paypal', uselist=False))

class ContoPersonale(db.Model):
    """Modello per i conti personali di Maurizio e Antonietta"""
    id = db.Column(db.Integer, primary_key=True)
    nome_conto = db.Column(db.String(50), nullable=False)  # 'Maurizio' o 'Antonietta'
    saldo_iniziale = db.Column(db.Float, nullable=False)
    saldo_corrente = db.Column(db.Float, nullable=False)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class VersamentoPersonale(db.Model):
    """Modello per i versamenti sui conti personali"""
    id = db.Column(db.Integer, primary_key=True)
    conto_id = db.Column(db.Integer, db.ForeignKey('conto_personale.id'), nullable=False)
    conto = db.relationship('ContoPersonale', backref=db.backref('versamenti', lazy=True, cascade='all, delete-orphan'))
    data = db.Column(db.Date, nullable=False, default=datetime.now().date)
    descrizione = db.Column(db.String(200), nullable=False)
    importo = db.Column(db.Float, nullable=False)
    saldo_dopo_versamento = db.Column(db.Float, nullable=False)  # saldo dopo questo versamento
    data_inserimento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Veicolo(db.Model):
    """Modello per i veicoli nel garage (struttura semplificata per gestione separata)"""
    id = db.Column(db.Integer, primary_key=True)
    marca = db.Column(db.String(100), nullable=False)
    modello = db.Column(db.String(100), nullable=False)
    mese_scadenza_bollo = db.Column(db.Integer, nullable=False)  # 1-12 (gennaio-dicembre)
    costo_finanziamento = db.Column(db.Float, nullable=False)
    prima_rata = db.Column(db.Date, nullable=False)
    numero_rate = db.Column(db.Integer, nullable=False)
    rata_mensile = db.Column(db.Float, nullable=False)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    @property
    def totale_versato(self):
        """Calcola il totale versato in base alla data odierna e alla prima rata"""
        from datetime import date
        oggi = date.today()
        
        if oggi < self.prima_rata:
            return 0.0
        
        # Calcola quanti mesi sono passati dalla prima rata
        mesi_trascorsi = (oggi.year - self.prima_rata.year) * 12 + (oggi.month - self.prima_rata.month)
        
        # Se siamo oltre il giorno della rata nel mese corrente, conta anche questo mese
        if oggi.day >= self.prima_rata.day:
            mesi_trascorsi += 1
        
        # Non può superare il numero totale di rate
        rate_pagate = min(mesi_trascorsi, self.numero_rate)
        
        return max(0, rate_pagate * self.rata_mensile)
    
    @property
    def rate_rimanenti(self):
        """Calcola le rate rimanenti"""
        from datetime import date
        oggi = date.today()
        
        if oggi < self.prima_rata:
            return self.numero_rate
        
        # Calcola quanti mesi sono passati dalla prima rata
        mesi_trascorsi = (oggi.year - self.prima_rata.year) * 12 + (oggi.month - self.prima_rata.month)
        
        # Se siamo oltre il giorno della rata nel mese corrente, conta anche questo mese
        if oggi.day >= self.prima_rata.day:
            mesi_trascorsi += 1
        
        rate_pagate = min(mesi_trascorsi, self.numero_rate)
        return max(0, self.numero_rate - rate_pagate)
    
    @property
    def saldo_rimanente(self):
        """Calcola il saldo rimanente"""
        return max(0, self.costo_finanziamento - self.totale_versato)
    
    @property
    def nome_completo(self):
        """Restituisce nome completo del veicolo"""
        return f"{self.marca} {self.modello}"
    
    @property
    def bollo_scaduto_anno_corrente(self):
        """Verifica se il bollo è scaduto per l'anno corrente"""
        from datetime import date
        oggi = date.today()
        
        # Se siamo oltre il mese di scadenza nell'anno corrente
        if oggi.month > self.mese_scadenza_bollo:
            # Verifica se esiste un pagamento per l'anno corrente
            bollo_pagato = BolloAuto.query.filter_by(
                veicolo_id=self.id, 
                anno_riferimento=oggi.year
            ).first()
            
            return bollo_pagato is None
        
        return False
    
    @property
    def giorni_alla_scadenza_bollo(self):
        """Calcola i giorni alla prossima scadenza bollo"""
        from datetime import date
        oggi = date.today()
        
        # Data di scadenza per l'anno corrente (ultimo giorno del mese di scadenza)
        import calendar
        ultimo_giorno = calendar.monthrange(oggi.year, self.mese_scadenza_bollo)[1]
        data_scadenza = date(oggi.year, self.mese_scadenza_bollo, ultimo_giorno)
        
        return (data_scadenza - oggi).days

class BolloAuto(db.Model):
    """Modello per i pagamenti del bollo auto (struttura semplificata)"""
    id = db.Column(db.Integer, primary_key=True)
    veicolo_id = db.Column(db.Integer, db.ForeignKey('veicolo.id'), nullable=False)
    veicolo = db.relationship('Veicolo', backref=db.backref('bolli', lazy=True, cascade='all, delete-orphan'))
    anno_riferimento = db.Column(db.Integer, nullable=False)
    importo = db.Column(db.Float, nullable=False)
    data_pagamento = db.Column(db.Date, nullable=False)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class ManutenzioneAuto(db.Model):
    """Modello per gli interventi di manutenzione (struttura semplificata)"""
    id = db.Column(db.Integer, primary_key=True)
    veicolo_id = db.Column(db.Integer, db.ForeignKey('veicolo.id'), nullable=False)
    veicolo = db.relationship('Veicolo', backref=db.backref('manutenzioni', lazy=True, cascade='all, delete-orphan'))
    data_intervento = db.Column(db.Date, nullable=False)
    tipo_intervento = db.Column(db.String(200), nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    costo = db.Column(db.Float, nullable=False)
    km_intervento = db.Column(db.Integer, nullable=True)
    officina = db.Column(db.String(200), nullable=True)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Appunto(db.Model):
    """Modello per gli appunti/promemoria di spese future"""
    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default='uscita')  # 'uscita', 'entrata'
    importo_stimato = db.Column(db.Float, nullable=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)
    categoria = db.relationship('Categoria', backref=db.backref('appunti', lazy=True))
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    note = db.Column(db.Text, nullable=True)

# Modelli PostePay Evolution (settembre 2025)
class PostePayEvolution(db.Model):
    """Modello per il saldo PostePay Evolution"""
    id = db.Column(db.Integer, primary_key=True)
    saldo_attuale = db.Column(db.Float, nullable=False, default=0.0)
    data_ultimo_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class AbbonamentoPostePay(db.Model):
    """Modello per gli abbonamenti PostePay Evolution"""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    importo = db.Column(db.Float, nullable=False)
    giorno_addebito = db.Column(db.Integer, nullable=False)  # Giorno del mese (1-31)
    attivo = db.Column(db.Boolean, nullable=False, default=True)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_disattivazione = db.Column(db.DateTime, nullable=True)

    @property
    def prossimo_addebito(self):
        """Calcola la data del prossimo addebito"""
        oggi = date.today()
        
        # Prova prima con il mese corrente
        try:
            prossima_data = date(oggi.year, oggi.month, self.giorno_addebito)
            if prossima_data > oggi:
                return prossima_data
        except ValueError:
            # Il giorno non esiste nel mese corrente (es. 31 febbraio)
            pass
        
        # Se siamo già passati o il giorno non esiste, prova il mese prossimo
        prossimo_mese = oggi.month + 1
        prossimo_anno = oggi.year
        if prossimo_mese > 12:
            prossimo_mese = 1
            prossimo_anno += 1
        
        try:
            return date(prossimo_anno, prossimo_mese, self.giorno_addebito)
        except ValueError:
            # Se anche nel prossimo mese il giorno non esiste, usa l'ultimo giorno del mese
            import calendar
            ultimo_giorno = calendar.monthrange(prossimo_anno, prossimo_mese)[1]
            return date(prossimo_anno, prossimo_mese, min(self.giorno_addebito, ultimo_giorno))

class MovimentoPostePay(db.Model):
    """Modello per i movimenti PostePay Evolution"""
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    descrizione = db.Column(db.String(200), nullable=False)
    importo = db.Column(db.Float, nullable=False)  # Positivo per entrate, negativo per uscite
    tipo = db.Column(db.String(50), nullable=False)  # 'ricarica', 'abbonamento', 'altro'
    abbonamento_id = db.Column(db.Integer, db.ForeignKey('abbonamento_poste_pay.id'), nullable=True)
    abbonamento = db.relationship('AbbonamentoPostePay', backref=db.backref('movimenti', lazy=True))
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

def get_month_boundaries(date):
    """Calcola i confini del mese personalizzato"""
    giorno_inizio = app.config['GIORNO_INIZIO_MESE']
    if date.day >= giorno_inizio:
        # Se siamo dal giorno di inizio in poi, il mese inizia da questo giorno
        start_date = date.replace(day=giorno_inizio)
        if date.month == 12:
            end_date = datetime(date.year + 1, 1, giorno_inizio - 1).date()
        else:
            end_date = date.replace(month=date.month + 1, day=giorno_inizio - 1)
    else:
        # Se siamo prima del giorno di inizio, il mese è iniziato dal giorno del mese precedente
        if date.month == 1:
            start_date = datetime(date.year - 1, 12, giorno_inizio).date()
        else:
            start_date = date.replace(month=date.month - 1, day=giorno_inizio)
        end_date = date.replace(day=giorno_inizio - 1)
    
    return start_date, end_date

def get_current_month_name(date):
    """Ottiene il nome del mese personalizzato"""
    start_date, end_date = get_month_boundaries(date)
    mesi_italiani = [
        'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
        'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'
    ]
    # Usa la data di fine periodo per determinare il nome del mese
    nome_mese = mesi_italiani[end_date.month - 1]
    anno = end_date.year
    periodo = f"{start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m/%Y')}"
    return f"{nome_mese} {anno}&nbsp;-&nbsp;{periodo}"

def get_month_name_for_chart(date):
    """Ottiene solo il nome del mese per i grafici"""
    start_date, end_date = get_month_boundaries(date)
    mesi_italiani = [
        'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
        'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'
    ]
    # Usa la data di fine periodo per determinare il nome del mese
    return mesi_italiani[end_date.month - 1]

def excel_date_to_datetime(excel_date):
    """Converte una data Excel (numero seriale) in datetime"""
    if isinstance(excel_date, (int, float)):
        # Data base di Excel: 1 gennaio 1900
        base_date = datetime(1900, 1, 1)
        # Excel considera erronemente il 1900 come anno bisestile, quindi sottrai 2 giorni
        return base_date + timedelta(days=excel_date - 2)
    return None

def verifica_e_crea_transazioni_annuali():
    """Verifica e crea automaticamente le transazioni annuali mancanti SOLO entro i prossimi 6 mesi"""
    oggi = datetime.now().date()
    limite_sei_mesi = oggi + relativedelta(months=6)
    
    # Trova tutte le transazioni madri annuali
    transazioni_annuali = Transazione.query.filter(
        Transazione.ricorrente == True,
        Transazione.frequenza_giorni == 365
    ).all()
    
    for madre in transazioni_annuali:
        # Calcola la prossima occorrenza di questa transazione annuale
        anno_corrente = oggi.year
        
        # Prova prima con l'anno corrente
        try:
            data_anno_corrente = datetime(anno_corrente, madre.data.month, madre.data.day).date()
            
            # Se la data di quest'anno è già passata, prova l'anno prossimo
            if data_anno_corrente < oggi:
                data_target = datetime(anno_corrente + 1, madre.data.month, madre.data.day).date()
            else:
                data_target = data_anno_corrente
                
        except ValueError:
            # Data non valida (es. 29 febbraio in anno non bisestile)
            continue
        
        # Crea la transazione SOLO se è entro i prossimi 6 mesi E non è la stessa data della madre
        if data_target <= limite_sei_mesi and data_target != madre.data:
            # Verifica se la transazione esiste già
            esistente = Transazione.query.filter_by(
                descrizione=madre.descrizione,
                data=data_target,
                transazione_madre_id=madre.id
            ).first()
            
            if not esistente:
                nuova_transazione = Transazione(
                    descrizione=madre.descrizione,
                    importo=madre.importo,
                    data=data_target,
                    tipo=madre.tipo,
                    categoria_id=madre.categoria_id,
                    ricorrente=False,
                    transazione_madre_id=madre.id
                )
                db.session.add(nuova_transazione)
                print(f"Creata transazione annuale: {madre.descrizione} per {data_target}")
    
    db.session.commit()

def verifica_e_aggiorna_saldo():
    """Verifica se è il giorno di inizio mese e aggiorna il saldo se necessario"""
    oggi = datetime.now().date()
    giorno_inizio = app.config['GIORNO_INIZIO_MESE']
    
    # NON chiamare verifica_e_crea_transazioni_annuali() durante l'inizializzazione
    # Queste funzioni vengono chiamate solo durante il normale funzionamento,
    # non durante la creazione iniziale del database
    
    # Verifica se ci sono già transazioni nel database (segno che non è inizializzazione)
    if Transazione.query.count() > 0:
        # Solo se il database è già popolato, verifica le transazioni annuali
        verifica_e_crea_transazioni_annuali()
        verifica_e_crea_stipendi_dicembre()
    
    if oggi.day == giorno_inizio:
        # Calcola il mese appena concluso (quello che finisce oggi)
        mese_concluso_start, mese_concluso_end = get_month_boundaries(oggi - relativedelta(days=1))
        
        # Calcola il bilancio del mese concluso (logica corretta per madri/figlie)
        # Prendi tutte le transazioni del mese (escluse quelle PayPal senza categoria)
        tutte_transazioni_mese = Transazione.query.filter(
            Transazione.data >= mese_concluso_start,
            Transazione.data <= mese_concluso_end,
            Transazione.categoria_id.isnot(None)  # Escludi transazioni PayPal (senza categoria)
        ).all()
        
        # Filtra per evitare duplicazioni
        entrate_mese = 0
        uscite_mese = 0
        for t in tutte_transazioni_mese:
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
                    entrate_mese += t.importo
                else:
                    uscite_mese += t.importo
        
        bilancio_mese_concluso = entrate_mese - uscite_mese
        
        # Aggiorna il saldo iniziale
        saldo = SaldoIniziale.query.first()
        if saldo:
            nuovo_saldo = saldo.importo + bilancio_mese_concluso
            saldo.importo = nuovo_saldo
            saldo.data_aggiornamento = datetime.utcnow()
        else:
            saldo = SaldoIniziale(importo=bilancio_mese_concluso)
            db.session.add(saldo)
        
        # Crea transazioni ricorrenti per il nuovo mese (6 mesi nel futuro)
        data_nuovo_mese = oggi + relativedelta(months=6)
        crea_transazioni_ricorrenti_per_mese(data_nuovo_mese)
        
        db.session.commit()

def crea_transazioni_ricorrenti_per_mese(data_mese):
    """Crea le transazioni ricorrenti per un mese specifico"""
    # Trova tutte le transazioni madri (ricorrenti)
    transazioni_madri = Transazione.query.filter(
        Transazione.ricorrente == True,
        Transazione.frequenza_giorni.in_([30, 365])  # Solo mensili e annuali
    ).all()
    
    for madre in transazioni_madri:
        if madre.frequenza_giorni == 30:  # Mensile
            # Gestione speciale per lo stipendio
            if madre.descrizione == 'Stipendio':
                if data_mese.month == 12:
                    # Per dicembre, crea lo stipendio speciale (ridotto, il 20)
                    crea_stipendio_dicembre_per_anno(data_mese.year)
                    continue  # Non creare lo stipendio normale
                else:
                    # Per gli altri mesi, crea lo stipendio normale
                    try:
                        nuova_data = data_mese.replace(day=madre.data.day)
                    except ValueError:
                        import calendar
                        ultimo_giorno = calendar.monthrange(data_mese.year, data_mese.month)[1]
                        nuova_data = data_mese.replace(day=min(madre.data.day, ultimo_giorno))
            else:
                # Per le altre transazioni mensili, mantieni lo stesso giorno del mese
                try:
                    nuova_data = data_mese.replace(day=madre.data.day)
                except ValueError:
                    import calendar
                    ultimo_giorno = calendar.monthrange(data_mese.year, data_mese.month)[1]
                    nuova_data = data_mese.replace(day=min(madre.data.day, ultimo_giorno))
        
        elif madre.frequenza_giorni == 365:  # Annuale (incluso stipendio dicembre)
            # Per transazioni annuali, controlla se è il momento di creare la prossima ricorrenza
            # Ma solo se è entro i prossimi 6 mesi dalla data corrente
            oggi = datetime.now().date()
            limite_sei_mesi = oggi + relativedelta(months=6)
            
            # Calcola la prossima data di questa transazione annuale
            anno_corrente = oggi.year
            
            # Prova prima con l'anno corrente
            try:
                data_anno_corrente = datetime(anno_corrente, madre.data.month, madre.data.day).date()
                
                # Se la data di quest'anno è già passata, prova l'anno prossimo
                if data_anno_corrente < oggi:
                    nuova_data = datetime(anno_corrente + 1, madre.data.month, madre.data.day).date()
                else:
                    nuova_data = data_anno_corrente
                    
                # Crea la transazione SOLO se è entro i prossimi 6 mesi
                if nuova_data > limite_sei_mesi:
                    continue  # Salta questa transazione, troppo lontana
                    
            except ValueError:
                # Se il giorno non esiste (es. 29 feb in anno non bisestile)
                continue
        else:
            continue
        
        # Verifica se la transazione esiste già
        esistente = Transazione.query.filter_by(
            descrizione=madre.descrizione,
            data=nuova_data,
            transazione_madre_id=madre.id
        ).first()
        
        if not esistente:
            nuova_transazione = Transazione(
                descrizione=madre.descrizione,
                importo=madre.importo,
                data=nuova_data,
                tipo=madre.tipo,
                categoria_id=madre.categoria_id,
                ricorrente=False,  # Le transazioni figlie non sono ricorrenti
                transazione_madre_id=madre.id
            )
            db.session.add(nuova_transazione)

def crea_stipendio_dicembre_per_anno(anno):
    """Crea lo stipendio speciale di dicembre per un anno specifico"""
    # Calcola l'importo dello stipendio di dicembre (ridotto del 20%)
    stipendio_normale = app.config['STIPENDIO_NORMALE_IMPORTO']
    riduzione_percentuale = app.config['STIPENDIO_DICEMBRE_RIDUZIONE_PERCENTUALE']
    stipendio_dicembre = stipendio_normale * (100 - riduzione_percentuale) / 100
    
    # Data del 20 dicembre
    data_stipendio_dicembre = datetime(anno, 12, app.config['STIPENDIO_DICEMBRE_GIORNO']).date()
    
    # Verifica se esiste già una transazione per questa data
    esistente = Transazione.query.filter_by(
        descrizione='Stipendio Dicembre',
        data=data_stipendio_dicembre
    ).first()
    
    if not esistente:
        # Trova la categoria Stipendio
        categoria_stipendio = Categoria.query.filter_by(nome='Stipendio').first()
        if categoria_stipendio:
            # Cerca se esiste già una transazione madre per Stipendio Dicembre
            # Verifica che esista una sola transazione madre
            madre_stipendio = Transazione.query.filter_by(
                descrizione='Stipendio Dicembre',
                ricorrente=True
            ).first()
            
            # Se non esiste una transazione madre, crea la prima come madre
            # Altrimenti crea come figlia della transazione madre esistente
            if not madre_stipendio:
                transazione = Transazione(
                    descrizione='Stipendio Dicembre',
                    importo=stipendio_dicembre,
                    data=data_stipendio_dicembre,
                    tipo='entrata',
                    categoria_id=categoria_stipendio.id,
                    ricorrente=True,
                    frequenza_giorni=365  # Trattato come annuale
                )
                print(f"Creata transazione MADRE stipendio dicembre per {anno}: €{stipendio_dicembre:.2f}")
            else:
                # Verifica che non esista già una figlia per questa data e madre
                figlia_esistente = Transazione.query.filter_by(
                    descrizione='Stipendio Dicembre',
                    data=data_stipendio_dicembre,
                    transazione_madre_id=madre_stipendio.id
                ).first()
                
                if not figlia_esistente:
                    transazione = Transazione(
                        descrizione='Stipendio Dicembre',
                        importo=stipendio_dicembre,
                        data=data_stipendio_dicembre,
                        tipo='entrata',
                        categoria_id=categoria_stipendio.id,
                        ricorrente=False,
                        transazione_madre_id=madre_stipendio.id
                    )
                    print(f"Creata transazione FIGLIA stipendio dicembre per {anno}: €{stipendio_dicembre:.2f}")
                else:
                    print(f"Transazione figlia stipendio dicembre per {anno} già esistente")
                    return
            
            db.session.add(transazione)

def verifica_e_crea_stipendi_dicembre():
    """Verifica e crea gli stipendi di dicembre SOLO se entro i prossimi 6 mesi"""
    oggi = datetime.now().date()
    limite_sei_mesi = oggi + relativedelta(months=6)
    
    # Calcola la prossima data di stipendio dicembre
    anno_corrente = oggi.year
    
    # Prova prima con l'anno corrente
    data_dicembre_corrente = datetime(anno_corrente, 12, app.config['STIPENDIO_DICEMBRE_GIORNO']).date()
    
    # Se dicembre di quest'anno è già passato, prova l'anno prossimo
    if data_dicembre_corrente < oggi:
        data_target = datetime(anno_corrente + 1, 12, app.config['STIPENDIO_DICEMBRE_GIORNO']).date()
    else:
        data_target = data_dicembre_corrente
    
    # Crea lo stipendio di dicembre SOLO se è entro i prossimi 6 mesi
    if data_target <= limite_sei_mesi:
        crea_stipendio_dicembre_per_anno(data_target.year)

@app.route('/')
def index():
    # Verifica se è necessario aggiornare il saldo (se è il 27 del mese)
    verifica_e_aggiorna_saldo()
    
    oggi = datetime.now().date()
    
    # Ottieni saldo iniziale (potrebbe essere stato aggiornato dalla funzione sopra)
    saldo_iniziale = SaldoIniziale.query.first()
    saldo_iniziale_importo = saldo_iniziale.importo if saldo_iniziale else 0.0
    
    # Calcola i prossimi N mesi con saldo progressivo
    mesi = []
    saldo_corrente = saldo_iniziale_importo
    
    for i in range(app.config['MESI_PROIEZIONE']):
        data_mese = oggi + relativedelta(months=i)
        start_date, end_date = get_month_boundaries(data_mese)
        
        # Calcola entrate e uscite per questo mese (logica corretta per madri/figlie)
        tutte_transazioni_mese = Transazione.query.filter(
            Transazione.data >= start_date,
            Transazione.data <= end_date,
            Transazione.categoria_id.isnot(None)  # Escludi transazioni PayPal (senza categoria)
        ).all()
        
        # Filtra per evitare duplicazioni
        entrate = 0
        uscite = 0
        for t in tutte_transazioni_mese:
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
                    entrate += t.importo
                else:
                    uscite += t.importo
        
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
            'entrate': entrate,
            'uscite': uscite,
            'bilancio': bilancio,
            'saldo_iniziale_mese': saldo_corrente,
            'saldo_finale_mese': saldo_finale_mese,
            'saldo_attuale_mese': saldo_attuale_mese,
            'mese_corrente': i == 0
        })
        
        # Il saldo finale di questo mese diventa il saldo iniziale del prossimo
        saldo_corrente = saldo_finale_mese
    
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
    
    # Ottieni saldo iniziale
    saldo_iniziale = SaldoIniziale.query.first()
    saldo_iniziale_importo = saldo_iniziale.importo if saldo_iniziale else 0.0
    
    # Ottieni categorie per il modal (escludi PayPal)
    categorie = Categoria.query.filter(Categoria.nome != 'PayPal').all()
    categorie_dict = [{'id': c.id, 'nome': c.nome, 'tipo': c.tipo} for c in categorie]
    
    return render_template('index.html', 
                         mesi=mesi, 
                         ultime_transazioni=ultime_transazioni,
                         saldo_iniziale=saldo_iniziale_importo,
                         categorie=categorie_dict)

@app.route('/transazioni')
def transazioni():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filtri
    tipo_filtro = request.args.get('tipo', '')
    ordine = request.args.get('ordine', 'data_desc')
    
    # Query base (mostra tutte le transazioni nella lista escluse PayPal)
    query = Transazione.query.filter(Transazione.categoria_id.isnot(None))
    
    # Applica filtro tipo se specificato
    if tipo_filtro in ['entrata', 'uscita']:
        query = query.filter(Transazione.tipo == tipo_filtro)
    
    # Applica ordinamento
    if ordine == 'data_asc':
        query = query.order_by(Transazione.data.asc(), Transazione.id.asc())
    elif ordine == 'data_desc':
        query = query.order_by(Transazione.data.desc(), Transazione.id.desc())
    elif ordine == 'importo_asc':
        query = query.order_by(Transazione.importo.asc(), Transazione.data.desc())
    elif ordine == 'importo_desc':
        query = query.order_by(Transazione.importo.desc(), Transazione.data.desc())
    else:
        # Default: data decrescente
        query = query.order_by(Transazione.data.desc(), Transazione.id.desc())
    
    transazioni = query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    categorie = Categoria.query.filter(Categoria.nome != 'PayPal').all()
    categorie_dict = [{'id': c.id, 'nome': c.nome, 'tipo': c.tipo} for c in categorie]
    
    return render_template('transazioni.html', transazioni=transazioni, categorie=categorie_dict)

@app.route('/aggiungi_transazione', methods=['POST'])
def aggiungi_transazione():
    try:
        data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        descrizione = request.form['descrizione']
        importo = float(request.form['importo'])
        categoria_id = int(request.form['categoria_id'])
        tipo = request.form['tipo']
        ricorrente = 'ricorrente' in request.form
        frequenza_giorni = int(request.form.get('frequenza_giorni', 0)) if ricorrente else 0
        
        # Gestisci data_effettiva: automaticamente effettuata se data <= oggi
        data_effettiva = None
        oggi = datetime.now().date()
        
        if data <= oggi:
            # Se la data è oggi o nel passato, la transazione è effettuata
            data_effettiva = data
        # Altrimenti lascia data_effettiva come NULL (transazione programmata per il futuro)
        
        transazione = Transazione(
            data=data,
            data_effettiva=data_effettiva,
            descrizione=descrizione,
            importo=importo,
            categoria_id=categoria_id,
            tipo=tipo,
            ricorrente=ricorrente,
            frequenza_giorni=frequenza_giorni
        )
        
        db.session.add(transazione)
        db.session.commit()  # Commit per ottenere l'ID della transazione madre
        
        # Gestione automatica del budget mensile per transazioni di uscita non ricorrenti
        # Nuova logica di budget (aggiornata settembre 2025):
        # - Categoria Sport (ID 8) → decurta dal budget "Sport" del 26 del mese
        # - Categoria Spese Casa (ID 5) → non decurta da nessun budget
        # - Qualsiasi altra categoria (eccetto Sport e Spese Casa) → decurta dal budget "Altre Spese" del 26 del mese
        if tipo == "uscita" and not ricorrente:
            if categoria_id == 8:  # Categoria "Sport" (ID 8) di tipo uscita
                # Trova la transazione budget "Sport" del 26 nello stesso mese
                inizio_mese, fine_mese = get_month_boundaries(data)
                
                transazione_sport = Transazione.query.filter(
                    Transazione.descrizione.in_([
                        "Sport",
                        "Sport (ricorrente)"
                    ]),
                    Transazione.data >= inizio_mese,
                    Transazione.data <= fine_mese,
                    Transazione.tipo == "uscita",
                    Transazione.categoria_id == 8  # Categoria Sport
                ).first()
                
                if transazione_sport:
                    # Riduci l'importo della transazione Sport
                    nuovo_importo = max(0, transazione_sport.importo - importo)
                    transazione_sport.importo = nuovo_importo
                    db.session.commit()
                    
                    # Aggiungi un messaggio informativo
                    flash(f'€{importo:.2f} sottratti dal budget "Sport". Nuovo budget: €{nuovo_importo:.2f}', 'info')
                else:
                    flash(f'Attenzione: Non trovata transazione budget "Sport" per questo mese', 'warning')
                    
            elif categoria_id != 5:  # Tutte le altre categorie di uscita (escluse Sport e Spese Casa)
                # Trova la transazione budget "Altre Spese" del 26 nello stesso mese
                inizio_mese, fine_mese = get_month_boundaries(data)
                
                transazione_spese_varie = Transazione.query.filter(
                    Transazione.descrizione.in_([
                        app.config['BUDGET_SPESE_VARIE_DESCRIZIONE'],
                        f"{app.config['BUDGET_SPESE_VARIE_DESCRIZIONE']} (ricorrente)"
                    ]),
                    Transazione.data >= inizio_mese,
                    Transazione.data <= fine_mese,
                    Transazione.tipo == "uscita",
                    Transazione.categoria_id == 6  # Categoria Spese Mensili
                ).first()
                
                if transazione_spese_varie:
                    # Riduci l'importo della transazione Spese varie
                    nuovo_importo = max(0, transazione_spese_varie.importo - importo)
                    transazione_spese_varie.importo = nuovo_importo
                    db.session.commit()
                    
                    # Aggiungi un messaggio informativo
                    flash(f'€{importo:.2f} sottratti dal budget "Altre Spese". Nuovo budget: €{nuovo_importo:.2f}', 'info')
                else:
                    flash(f'Attenzione: Non trovata transazione budget "Altre Spese" per questo mese', 'warning')
        
        # Se è ricorrente, crea le transazioni future per i prossimi 6 mesi
        if ricorrente and frequenza_giorni > 0:
            for i in range(1, 7):  # Prossimi 6 mesi
                if frequenza_giorni == 30:  # mensile
                    data_futura = data + relativedelta(months=i)
                elif frequenza_giorni == 365:  # annuale
                    data_futura = data + relativedelta(years=1)
                    if data_futura > datetime.now().date() + relativedelta(months=6):
                        break  # Non creare transazioni annuali troppo lontane
                else:
                    continue
                
                # Verifica che non esista già
                esiste_gia = Transazione.query.filter(
                    Transazione.transazione_madre_id == transazione.id,
                    Transazione.data == data_futura
                ).first()
                
                if not esiste_gia:
                    # Le transazioni ricorrenti future sono sempre programmate (data_effettiva = NULL)
                    transazione_ricorrente = Transazione(
                        data=data_futura,
                        data_effettiva=None,  # Sempre programmata per il futuro
                        descrizione=f"{descrizione} (ricorrente)",
                        importo=importo,
                        categoria_id=categoria_id,
                        tipo=tipo,
                        ricorrente=False,
                        frequenza_giorni=0,
                        transazione_madre_id=transazione.id
                    )
                    db.session.add(transazione_ricorrente)
        
        db.session.commit()
        
        # Export automatico del database dopo modifica
        export_database_to_backup()
        
        # Flash message di successo
        if ricorrente:
            flash(f'Transazione ricorrente "{descrizione}" aggiunta con successo!', 'success')
        else:
            flash(f'Transazione "{descrizione}" aggiunta con successo!', 'success')
        
        # Controlla se la richiesta arriva dal modal della dashboard, dalla pagina transazioni o dal dettaglio
        redirect_to = request.form.get('redirect_to', 'transazioni')
        if redirect_to == 'dashboard':
            return redirect(url_for('index'))
        elif redirect_to.startswith('dettaglio_periodo:'):
            # Formato: dettaglio_periodo:start_date:end_date
            _, start_date_str, end_date_str = redirect_to.split(':')
            return redirect(url_for('dettaglio_periodo', start_date=start_date_str, end_date=end_date_str))
        else:
            return redirect(url_for('transazioni'))
            
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'aggiunta della transazione: {str(e)}', 'error')
        redirect_to = request.form.get('redirect_to', 'transazioni')
        if redirect_to == 'dashboard':
            return redirect(url_for('index'))
        elif redirect_to.startswith('dettaglio_periodo:'):
            # Formato: dettaglio_periodo:start_date:end_date
            _, start_date_str, end_date_str = redirect_to.split(':')
            return redirect(url_for('dettaglio_periodo', start_date=start_date_str, end_date=end_date_str))
        else:
            return redirect(url_for('transazioni'))

@app.route('/elimina_transazione/<int:id>')
def elimina_transazione(id):
    transazione = Transazione.query.get_or_404(id)
    descrizione = transazione.descrizione
    importo = transazione.importo
    data = transazione.data
    tipo = transazione.tipo
    
    # Gestione automatica del ripristino budget per transazioni di uscita non ricorrenti
    # Nuova logica di budget (aggiornata settembre 2025):
    # - Categoria Sport (ID 8) → ripristina al budget "Sport" del 26 del mese
    # - Categoria Spese Casa (ID 5) → non ripristina a nessun budget
    # - Qualsiasi altra categoria (eccetto Sport e Spese Casa) → ripristina al budget "Altre Spese" del 26 del mese
    if tipo == "uscita" and not transazione.ricorrente:
        if transazione.categoria_id == 8:  # Categoria "Sport" (ID 8) di tipo uscita
            # Trova la transazione budget "Sport" del 26 nello stesso mese
            inizio_mese, fine_mese = get_month_boundaries(data)
            
            transazione_sport = Transazione.query.filter(
                Transazione.descrizione.in_([
                    "Sport",
                    "Sport (ricorrente)"
                ]),
                Transazione.data >= inizio_mese,
                Transazione.data <= fine_mese,
                Transazione.tipo == "uscita",
                Transazione.categoria_id == 8  # Categoria Sport
            ).first()
            
            if transazione_sport:
                # Ripristina l'importo della transazione Sport
                nuovo_importo = transazione_sport.importo + importo
                transazione_sport.importo = nuovo_importo
                flash(f'€{importo:.2f} ripristinati al budget "Sport". Nuovo budget: €{nuovo_importo:.2f}', 'info')
            else:
                flash(f'Attenzione: Non trovata transazione budget "Sport" per questo mese', 'warning')
                
        elif transazione.categoria_id != 5:  # Tutte le altre categorie di uscita (escluse Sport e Spese Casa)
            # Trova la transazione budget "Altre Spese" del 26 nello stesso mese
            inizio_mese, fine_mese = get_month_boundaries(data)
            
            transazione_spese_varie = Transazione.query.filter(
                Transazione.descrizione.in_([
                    app.config['BUDGET_SPESE_VARIE_DESCRIZIONE'],
                    f"{app.config['BUDGET_SPESE_VARIE_DESCRIZIONE']} (ricorrente)"
                ]),
                Transazione.data >= inizio_mese,
                Transazione.data <= fine_mese,
                Transazione.tipo == "uscita",
                Transazione.categoria_id == 6  # Categoria Spese Mensili
            ).first()
            
            if transazione_spese_varie:
                # Ripristina l'importo della transazione Spese varie
                nuovo_importo = transazione_spese_varie.importo + importo
                transazione_spese_varie.importo = nuovo_importo
                flash(f'€{importo:.2f} ripristinati al budget "Spese varie". Nuovo budget: €{nuovo_importo:.2f}', 'info')
            else:
                flash(f'Attenzione: Non trovata transazione budget "Altre Spese" per questo mese', 'warning')
    
    db.session.delete(transazione)
    db.session.commit()
    
    # Export automatico del database dopo modifica
    export_database_to_backup()
    
    flash(f'Transazione "{descrizione}" eliminata con successo!', 'success')
    
    # Controlla se viene passato un parametro per il redirect al dettaglio
    redirect_to = request.args.get('redirect_to')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if redirect_to == 'dettaglio_periodo' and start_date and end_date:
        return redirect(url_for('dettaglio_periodo', start_date=start_date, end_date=end_date))
    
    return redirect(url_for('transazioni'))

@app.route('/modifica_transazione/<int:id>', methods=['POST'])
def modifica_transazione(id):
    transazione = Transazione.query.get_or_404(id)
    
    # Salva i valori originali per la logica del budget
    importo_originale = transazione.importo
    data_originale = transazione.data
    tipo_originale = transazione.tipo
    categoria_id_originale = transazione.categoria_id
    ricorrente_originale = transazione.ricorrente
    
    # Aggiorna solo i campi modificati
    if 'descrizione' in request.form:
        transazione.descrizione = request.form['descrizione']
    if 'importo' in request.form:
        transazione.importo = float(request.form['importo'])
    if 'data' in request.form:
        transazione.data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
    if 'categoria_id' in request.form:
        transazione.categoria_id = int(request.form['categoria_id'])
    
    # Nuova logica di budget semplificata:
    # - Categoria Sport (ID 8) → decurta/ripristina dal budget "Sport"
    # - Categoria Spese Casa (ID 5) → non decurta/ripristina da nessun budget
    # - Tutte le altre categorie di uscita → decurtano/ripristinano dal budget "Spese Mensili"
    # Solo per transazioni di uscita non ricorrenti
    
    # Funzione helper per gestire budget "Altre Spese"
    def gestisci_budget_spese_mensili(data_ref, importo_delta, operazione):
        inizio_mese, fine_mese = get_month_boundaries(data_ref)
        transazione_spese_varie = Transazione.query.filter(
            Transazione.descrizione.in_([
                app.config['BUDGET_SPESE_VARIE_DESCRIZIONE'],
                f"{app.config['BUDGET_SPESE_VARIE_DESCRIZIONE']} (ricorrente)"
            ]),
            Transazione.data >= inizio_mese,
            Transazione.data <= fine_mese,
            Transazione.tipo == "uscita",
            Transazione.categoria_id == 6
        ).first()
        
        if transazione_spese_varie:
            if operazione == "ripristina":
                transazione_spese_varie.importo += importo_delta
                return f'€{importo_delta:.2f} ripristinati al budget "Altre Spese": €{transazione_spese_varie.importo:.2f}'
            elif operazione == "sottrai":
                nuovo_importo = max(0, transazione_spese_varie.importo - importo_delta)
                transazione_spese_varie.importo = nuovo_importo
                return f'€{importo_delta:.2f} sottratti dal budget "Altre Spese": €{nuovo_importo:.2f}'
        return None
    
    # Funzione helper per gestire budget "Sport"
    def gestisci_budget_sport(data_ref, importo_delta, operazione):
        inizio_mese, fine_mese = get_month_boundaries(data_ref)
        transazione_sport = Transazione.query.filter(
            Transazione.descrizione.in_([
                "Sport",
                "Sport (ricorrente)"
            ]),
            Transazione.data >= inizio_mese,
            Transazione.data <= fine_mese,
            Transazione.tipo == "uscita",
            Transazione.categoria_id == 8
        ).first()
        
        if transazione_sport:
            if operazione == "ripristina":
                transazione_sport.importo += importo_delta
                return f'€{importo_delta:.2f} ripristinati al budget "Sport": €{transazione_sport.importo:.2f}'
            elif operazione == "sottrai":
                nuovo_importo = max(0, transazione_sport.importo - importo_delta)
                transazione_sport.importo = nuovo_importo
                return f'€{importo_delta:.2f} sottratti dal budget "Sport": €{nuovo_importo:.2f}'
        return None
    
    # Gestione delle transizioni tra categorie
    era_uscita_non_ricorrente = (tipo_originale == "uscita" and not ricorrente_originale)
    e_uscita_non_ricorrente = (transazione.tipo == "uscita" and not transazione.ricorrente)
    
    if era_uscita_non_ricorrente:
        # Prima ripristina il budget originale
        if categoria_id_originale == 8:  # Era Sport
            gestisci_budget_sport(data_originale, importo_originale, "ripristina")
        elif categoria_id_originale != 5:  # Era qualsiasi altra categoria (escluse Sport e Spese Casa)
            gestisci_budget_spese_mensili(data_originale, importo_originale, "ripristina")
    
    if e_uscita_non_ricorrente:
        # Ora sottrai dal nuovo budget
        if transazione.categoria_id == 8:  # È Sport
            msg = gestisci_budget_sport(transazione.data, transazione.importo, "sottrai")
            if msg:
                flash(msg, 'info')
        elif transazione.categoria_id != 5:  # È qualsiasi altra categoria (escluse Sport e Spese Casa)
            msg = gestisci_budget_spese_mensili(transazione.data, transazione.importo, "sottrai")
            if msg:
                flash(msg, 'info')
    
    db.session.commit()
    
    # Export automatico del database dopo modifica
    export_database_to_backup()
    
    flash(f'Transazione "{transazione.descrizione}" modificata con successo!', 'success')
    
    # Determina dove reindirizzare in base alla provenienza
    if request.form.get('redirect_to') == 'dettaglio_periodo':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        if start_date and end_date:
            return redirect(url_for('dettaglio_periodo', start_date=start_date, end_date=end_date))
    
    # Default: torna alla lista transazioni
    return redirect(url_for('transazioni'))

@app.route('/conferma_transazione/<int:id>', methods=['POST'])
def conferma_transazione(id):
    """Segna una transazione come effettuata impostando data_effettiva a oggi"""
    transazione = Transazione.query.get_or_404(id)
    
    # Imposta la data effettiva a oggi
    transazione.data_effettiva = datetime.now().date()
    
    db.session.commit()
    
    # Export automatico del database dopo modifica
    export_database_to_backup()
    
    # Se è una richiesta JSON (da JavaScript), restituisci JSON
    if request.is_json:
        data = request.get_json()
        return jsonify({'success': True, 'message': f'Transazione "{transazione.descrizione}" confermata come effettuata!'})
    
    # Altrimenti gestisci come form normale
    flash(f'Transazione "{transazione.descrizione}" confermata come effettuata!', 'success')
    
    # Determina dove reindirizzare in base alla provenienza
    redirect_to = request.form.get('redirect_to')
    if redirect_to == 'dettaglio_periodo':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        if start_date and end_date:
            return redirect(url_for('dettaglio_periodo', start_date=start_date, end_date=end_date))
    
    # Default: torna alla lista transazioni
    return redirect(url_for('transazioni'))

@app.route('/categorie')
def categorie():
    categorie = Categoria.query.filter(Categoria.nome != 'PayPal').all()
    categorie_dict = [{'id': c.id, 'nome': c.nome, 'tipo': c.tipo} for c in categorie]
    return render_template('categorie.html', categorie=categorie_dict)

@app.route('/aggiungi_categoria', methods=['POST'])
def aggiungi_categoria():
    nome = request.form['nome']
    tipo = request.form['tipo']
    
    categoria = Categoria(nome=nome, tipo=tipo)
    db.session.add(categoria)
    db.session.commit()
    flash(f'Categoria "{nome}" aggiunta con successo!', 'success')
    
    return redirect(url_for('categorie'))

@app.route('/elimina_categoria/<int:id>')
def elimina_categoria(id):
    categoria = Categoria.query.get_or_404(id)
    nome = categoria.nome
    db.session.delete(categoria)
    db.session.commit()
    flash(f'Categoria "{nome}" eliminata con successo!', 'success')
    return redirect(url_for('categorie'))

@app.route('/dettaglio_mese/<int:anno>/<int:mese>')
def dettaglio_mese(anno, mese):
    """Mostra il dettaglio delle transazioni per un mese specifico (deprecato - usa dettaglio_periodo)"""
    data_mese = datetime(anno, mese, 1).date()
    start_date, end_date = get_month_boundaries(data_mese)
    return dettaglio_periodo_interno(start_date, end_date)

@app.route('/dettaglio_periodo/<start_date>/<end_date>')
def dettaglio_periodo(start_date, end_date):
    """Mostra il dettaglio delle transazioni per un periodo specifico"""
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        return dettaglio_periodo_interno(start_date, end_date)
    except ValueError:
        return "Date non valide", 400

def dettaglio_periodo_interno(start_date, end_date):
    """Funzione interna per gestire il dettaglio del periodo"""
    
    # Prendi tutte le transazioni del periodo (escluse PayPal)
    transazioni = Transazione.query.filter(
        Transazione.data >= start_date,
        Transazione.data <= end_date,
        Transazione.categoria_id.isnot(None)  # Escludi transazioni PayPal (senza categoria)
    ).order_by(Transazione.data.desc()).all()
    
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
    
    categorie = Categoria.query.filter(Categoria.nome != 'PayPal').all()
    categorie_dict = [{'id': c.id, 'nome': c.nome, 'tipo': c.tipo} for c in categorie]
    
    return render_template('dettaglio_mese.html', 
                         transazioni=transazioni_effettuate,
                         transazioni_in_attesa=transazioni_in_attesa,
                         nome_mese=nome_periodo,
                         entrate=entrate_totali_previste,
                         uscite=uscite_totali_previste,
                         bilancio=bilancio_totale_previsto,
                         entrate_effettuate=entrate_effettuate,
                         uscite_effettuate=uscite_effettuate,
                        
                         uscite_in_attesa=uscite_in_attesa,
                         saldo_iniziale_mese=saldo_iniziale_mese,
                         saldo_finale_mese=saldo_finale_mese,
                         saldo_attuale_mese=saldo_attuale_mese,
                         saldo_previsto_fine_mese=saldo_previsto_fine_mese,
                         mese_futuro=mese_futuro,
                         categorie=categorie_dict,
                         start_date=start_date,
                         end_date=end_date)

@app.route('/saldo_iniziale', methods=['GET', 'POST'])
def saldo_iniziale():
    if request.method == 'POST':
        importo = float(request.form['importo'])
        
        saldo = SaldoIniziale.query.first()
        if saldo:
            saldo.importo = importo
            saldo.data_aggiornamento = datetime.utcnow()
        else:
            saldo = SaldoIniziale(importo=importo)
            db.session.add(saldo)
        
        db.session.commit()
        export_database_to_backup()
        flash(f'Saldo iniziale aggiornato a €{importo:.2f}!', 'success')
        return redirect(url_for('index'))
    
    saldo = SaldoIniziale.query.first()
    return render_template('saldo_iniziale.html', saldo=saldo)

@app.route('/forza_rollover')
def forza_rollover():
    """Forza il roll-over mensile (per test o aggiornamento manuale)"""
    verifica_e_aggiorna_saldo()
    return redirect(url_for('index'))

@app.route('/api/bilancio/<int:mesi>')
def api_bilancio(mesi):
    """API per ottenere i dati del bilancio per i prossimi N mesi"""
    oggi = datetime.now().date()
    risultati = []
    
    for i in range(mesi):
        data_mese = oggi + relativedelta(months=i)
        start_date, end_date = get_month_boundaries(data_mese)
        
        tutte_transazioni_mese = Transazione.query.filter(
            Transazione.data >= start_date,
            Transazione.data <= end_date,
            Transazione.categoria_id.isnot(None)  # Escludi transazioni PayPal (senza categoria)
        ).all()
        
        # Filtra per evitare duplicazioni
        entrate = 0
        uscite = 0
        for t in tutte_transazioni_mese:
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
                    entrate += t.importo
                else:
                    uscite += t.importo
        
        risultati.append({
            'mese': get_month_name_for_chart(data_mese),
            'entrate': float(entrate),
            'uscite': float(uscite),
            'bilancio': float(entrate - uscite)
        })
    
    return jsonify(risultati)

# Routes per gestione piani PayPal
@app.route('/paypal')
def paypal_dashboard():
    """Dashboard per la gestione dei piani PayPal"""
    # Aggiorna gli importi rimanenti prima di visualizzare i dati
    aggiorna_importi_rimanenti_paypal()
    
    piani = PaypalPiano.query.order_by(PaypalPiano.data_creazione.desc()).all()
    
    # Calcola statistiche
    totale_piani = len(piani)
    piani_attivi = len([p for p in piani if p.stato == 'in_corso'])  # Solo piani in corso
    
    # Calcola importo rimanente: somma degli importi delle rate non pagate di tutti i piani
    importo_rimanente_totale = 0
    rate_non_pagate_totali = 0
    
    for piano in piani:
        for rata in piano.rate:
            if rata.stato == 'in_attesa':
                importo_rimanente_totale += rata.importo
                rate_non_pagate_totali += 1
    
    # Prossime rate in scadenza (prossimi 30 giorni)
    oggi = datetime.now().date()
    prossimo_mese = oggi + timedelta(days=30)
    
    rate_in_scadenza = PaypalRata.query.join(PaypalPiano).filter(
        PaypalRata.stato == 'in_attesa',
        PaypalRata.data_scadenza >= oggi,
        PaypalRata.data_scadenza <= prossimo_mese
    ).order_by(PaypalRata.data_scadenza).all()
    
    return render_template('paypal_dashboard.html', 
                         piani=piani, 
                         totale_piani=totale_piani,
                         piani_attivi=piani_attivi,
                         importo_rimanente_totale=importo_rimanente_totale,
                         rate_non_pagate_totali=rate_non_pagate_totali,
                         rate_in_scadenza=rate_in_scadenza)

@app.route('/paypal/nuovo', methods=['GET', 'POST'])
def nuovo_piano_paypal():
    """Crea un nuovo piano PayPal"""
    if request.method == 'POST':
        try:
            descrizione = request.form['descrizione']
            importo_totale = float(request.form['importo_totale'])
            data_prima_rata = datetime.strptime(request.form['data_prima_rata'], '%Y-%m-%d').date()
            
            # Calcola importo rata base (diviso per 3)
            importo_rata_base = round(importo_totale / 3, 2)
            resto = round(importo_totale - (importo_rata_base * 3), 2)
            
            # Distribuisci il resto: se positivo aggiungi alle prime rate, se negativo sottrai dalla terza
            if resto > 0:
                # Resto positivo: aggiungi centesimi alle prime 2 rate
                centesimi_resto = int(resto * 100)
                importo_rata1 = importo_rata_base
                importo_rata2 = importo_rata_base
                
                if centesimi_resto >= 1:
                    importo_rata1 += 0.01
                    centesimi_resto -= 1
                if centesimi_resto >= 1:
                    importo_rata2 += 0.01
                    centesimi_resto -= 1
                
                # Terza rata = totale - prime due rate
                importo_rata3 = round(importo_totale - importo_rata1 - importo_rata2, 2)
                
            elif resto < 0:
                # Resto negativo: mantieni le prime 2 rate al valore base, sottrai dalla terza
                importo_rata1 = importo_rata_base
                importo_rata2 = importo_rata_base
                # Terza rata = totale - prime due rate (automaticamente più bassa)
                importo_rata3 = round(importo_totale - importo_rata1 - importo_rata2, 2)
                
            else:
                # Resto = 0, tutte le rate uguali
                importo_rata1 = importo_rata_base
                importo_rata2 = importo_rata_base
                importo_rata3 = importo_rata_base
            
            # Calcola date delle rate (stesso giorno del mese per i 2 mesi successivi)
            anno1, mese1 = data_prima_rata.year, data_prima_rata.month
            giorno = data_prima_rata.day
            
            # Seconda rata: mese successivo
            mese2 = mese1 + 1
            anno2 = anno1
            if mese2 > 12:
                mese2 = 1
                anno2 += 1
            
            # Terza rata: 2 mesi dopo
            mese3 = mese1 + 2
            anno3 = anno1
            if mese3 > 12:
                mese3 -= 12
                anno3 += 1
            
            # Gestisci il caso in cui il giorno non esiste nel mese (es. 31 in febbraio)
            try:
                data_seconda_rata = date(anno2, mese2, giorno)
            except ValueError:
                # Se il giorno non esiste, usa l'ultimo giorno del mese
                import calendar
                ultimo_giorno = calendar.monthrange(anno2, mese2)[1]
                data_seconda_rata = date(anno2, mese2, min(giorno, ultimo_giorno))
            
            try:
                data_terza_rata = date(anno3, mese3, giorno)
            except ValueError:
                # Se il giorno non esiste, usa l'ultimo giorno del mese
                import calendar
                ultimo_giorno = calendar.monthrange(anno3, mese3)[1]
                data_terza_rata = date(anno3, mese3, min(giorno, ultimo_giorno))
            
            # Crea il piano (la rimanenza è sempre 0 con la nuova logica)
            piano = PaypalPiano(
                descrizione=descrizione,
                importo_totale=importo_totale,
                importo_rata=importo_rata1,  # Usa la prima rata come riferimento
                data_prima_rata=data_prima_rata,
                data_seconda_rata=data_seconda_rata,
                data_terza_rata=data_terza_rata,
                importo_rimanente=0.0,  # Sempre 0 perché tutto è distribuito
                note=request.form.get('note', '')
            )
            db.session.add(piano)
            db.session.flush()
            
            # Crea le rate con importi specifici
            rate_info = [
                (1, importo_rata1, data_prima_rata),
                (2, importo_rata2, data_seconda_rata),
                (3, importo_rata3, data_terza_rata)
            ]
            
            for numero, importo, data_scad in rate_info:
                rata = PaypalRata(
                    piano_id=piano.id,
                    numero_rata=numero,
                    importo=importo,
                    data_scadenza=data_scad
                )
                db.session.add(rata)
            
            db.session.commit()
            export_database_to_backup()
            flash(f'Piano PayPal "{descrizione}" creato con successo!', 'success')
            return redirect(url_for('paypal_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante la creazione del piano: {str(e)}', 'error')
    
    return render_template('paypal_nuovo.html')

@app.route('/paypal/piano/<int:id>')
def dettaglio_piano_paypal(id):
    """Mostra i dettagli di un piano PayPal"""
    # Aggiorna gli importi rimanenti prima di visualizzare i dettagli
    aggiorna_importi_rimanenti_paypal()
    
    piano = PaypalPiano.query.get_or_404(id)
    rate = PaypalRata.query.filter_by(piano_id=id).order_by(PaypalRata.numero_rata).all()
    return render_template('paypal_dettaglio.html', piano=piano, rate=rate)

@app.route('/paypal/piano/<int:id>/modifica', methods=['GET', 'POST'])
def modifica_piano_paypal(id):
    """Modifica un piano PayPal"""
    piano = PaypalPiano.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            piano.descrizione = request.form['descrizione']
            piano.note = request.form.get('note', '')
            piano.stato = request.form['stato']
            piano.data_aggiornamento = datetime.utcnow()
            
            db.session.commit()
            export_database_to_backup()
            flash(f'Piano "{piano.descrizione}" aggiornato con successo!', 'success')
            return redirect(url_for('dettaglio_piano_paypal', id=id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante la modifica: {str(e)}', 'error')
    
    return render_template('paypal_modifica.html', piano=piano)

@app.route('/paypal/piano/<int:id>/elimina')
def elimina_piano_paypal(id):
    """Elimina un piano PayPal"""
    piano = PaypalPiano.query.get_or_404(id)
    try:
        descrizione = piano.descrizione
        db.session.delete(piano)
        db.session.commit()
        export_database_to_backup()
        flash(f'Piano "{descrizione}" eliminato con successo!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'eliminazione: {str(e)}', 'error')
    
    return redirect(url_for('paypal_dashboard'))

@app.route('/paypal/rata/<int:id>/paga', methods=['POST'])
def paga_rata_paypal(id):
    """Segna una rata come pagata e crea la transazione corrispondente"""
    rata = PaypalRata.query.get_or_404(id)
    
    try:
        # Le transazioni PayPal non fanno parte del bilancio principale
        # quindi non hanno categoria
        
        # Crea transazione senza categoria
        transazione = Transazione(
            data=datetime.now().date(),
            descrizione=f"PayPal - {rata.piano.descrizione} (Rata {rata.numero_rata}/3)",
            importo=rata.importo,
            categoria_id=None,  # Nessuna categoria per transazioni PayPal
            tipo='uscita'
        )
        db.session.add(transazione)
        db.session.flush()
        
        # Aggiorna la rata
        rata.stato = 'pagata'
        rata.data_pagamento = datetime.now().date()
        rata.transazione_id = transazione.id
        
        # Controlla se tutte le rate sono pagate
        rate_rimanenti = PaypalRata.query.filter_by(
            piano_id=rata.piano_id, 
            stato='in_attesa'
        ).count()
        
        if rate_rimanenti == 0:
            rata.piano.stato = 'completato'
        
        db.session.commit()
        export_database_to_backup()
        flash(f'Rata {rata.numero_rata} del piano "{rata.piano.descrizione}" segnata come pagata!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante il pagamento della rata: {str(e)}', 'error')
    
    return redirect(url_for('paypal_dashboard'))

# Import/Export del database
@app.route('/database/export')
def export_database():
    """Esporta tutto il database in formato JSON"""
    try:
        import json
        from datetime import date, datetime
        
        def serialize_date(obj):
            """Serializzatore personalizzato per date e datetime"""
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            raise TypeError(f"Object {obj} is not JSON serializable")
        
        # Raccogli tutti i dati del database
        data = {
            'export_date': datetime.now().isoformat(),
            'version': '1.0',
            'data': {
                'categorie': [],
                'saldo_iniziale': [],
                'transazioni': [],
                'piani_paypal': [],
                'rate_paypal': [],
                'conti_personali': [],
                'versamenti_personali': [],
                'veicoli': [],
                'bolli_auto': [],
                'manutenzioni_auto': [],
                'postepay_evolution': [],
                'abbonamenti_postepay': [],
                'movimenti_postepay': [],
                'appunti': []
            }
        }
        
        # Esporta categorie
        for categoria in Categoria.query.all():
            data['data']['categorie'].append({
                'id': categoria.id,
                'nome': categoria.nome,
                'tipo': categoria.tipo
            })
        
        # Esporta saldo iniziale
        for saldo in SaldoIniziale.query.all():
            data['data']['saldo_iniziale'].append({
                'id': saldo.id,
                'importo': saldo.importo,
                'data_aggiornamento': saldo.data_aggiornamento.isoformat()
            })
        
        # Esporta transazioni
        for transazione in Transazione.query.all():
            data['data']['transazioni'].append({
                'id': transazione.id,
                'data': transazione.data.isoformat(),
                'descrizione': transazione.descrizione,
                'importo': transazione.importo,
                'categoria_id': transazione.categoria_id,
                'tipo': transazione.tipo,
                'ricorrente': transazione.ricorrente,
                'frequenza_giorni': transazione.frequenza_giorni,
                'transazione_madre_id': transazione.transazione_madre_id
            })
        
        # Esporta piani PayPal
        for piano in PaypalPiano.query.all():
            data['data']['piani_paypal'].append({
                'id': piano.id,
                'descrizione': piano.descrizione,
                'importo_totale': piano.importo_totale,
                'importo_rata': piano.importo_rata,
                'data_prima_rata': piano.data_prima_rata.isoformat(),
                'data_seconda_rata': piano.data_seconda_rata.isoformat(),
                'data_terza_rata': piano.data_terza_rata.isoformat(),
                'importo_rimanente': piano.importo_rimanente,
                'stato': piano.stato,
                'note': piano.note
            })
        
        # Esporta rate PayPal
        for rata in PaypalRata.query.all():
            data['data']['rate_paypal'].append({
                'id': rata.id,
                'piano_id': rata.piano_id,
                'numero_rata': rata.numero_rata,
                'importo': rata.importo,
                'data_scadenza': rata.data_scadenza.isoformat(),
                'stato': rata.stato,
                'data_pagamento': rata.data_pagamento.isoformat() if rata.data_pagamento else None
            })
        
        # Esporta conti personali
        for conto in ContoPersonale.query.all():
            data['data']['conti_personali'].append({
                'id': conto.id,
                'nome_conto': conto.nome_conto,
                'saldo_iniziale': conto.saldo_iniziale,
                'saldo_corrente': conto.saldo_corrente,
                'data_creazione': conto.data_creazione.isoformat(),
                'data_aggiornamento': conto.data_aggiornamento.isoformat()
            })
        
        # Esporta versamenti personali
        for versamento in VersamentoPersonale.query.all():
            data['data']['versamenti_personali'].append({
                'id': versamento.id,
                'conto_id': versamento.conto_id,
                'data': versamento.data.isoformat(),
                'descrizione': versamento.descrizione,
                'importo': versamento.importo,
                'saldo_dopo_versamento': versamento.saldo_dopo_versamento,
                'data_inserimento': versamento.data_inserimento.isoformat()
            })
        
        # Esporta veicoli
        for veicolo in Veicolo.query.all():
            data['data']['veicoli'].append({
                'id': veicolo.id,
                'marca': veicolo.marca,
                'modello': veicolo.modello,
                'mese_scadenza_bollo': veicolo.mese_scadenza_bollo,
                'costo_finanziamento': veicolo.costo_finanziamento,
                'prima_rata': veicolo.prima_rata.isoformat(),
                'numero_rate': veicolo.numero_rate,
                'rata_mensile': veicolo.rata_mensile,
                'data_creazione': veicolo.data_creazione.isoformat()
            })
        
        # Esporta bolli auto
        for bollo in BolloAuto.query.all():
            data['data']['bolli_auto'].append({
                'id': bollo.id,
                'veicolo_id': bollo.veicolo_id,
                'anno_riferimento': bollo.anno_riferimento,
                'data_pagamento': bollo.data_pagamento.isoformat(),
                'importo': bollo.importo
            })
        
        # Esporta manutenzioni auto
        for manutenzione in ManutenzioneAuto.query.all():
            data['data']['manutenzioni_auto'].append({
                'id': manutenzione.id,
                'veicolo_id': manutenzione.veicolo_id,
                'data_intervento': manutenzione.data_intervento.isoformat(),
                'tipo_intervento': manutenzione.tipo_intervento,
                'descrizione': manutenzione.descrizione,
                'costo': manutenzione.costo,
                'km_intervento': manutenzione.km_intervento,
                'officina': manutenzione.officina
            })

        # Esporta PostePay Evolution
        for postepay in PostePayEvolution.query.all():
            data['data']['postepay_evolution'].append({
                'id': postepay.id,
                'saldo_attuale': postepay.saldo_attuale,
                'data_ultimo_aggiornamento': postepay.data_ultimo_aggiornamento.isoformat()
            })

        # Esporta abbonamenti PostePay
        for abbonamento in AbbonamentoPostePay.query.all():
            data['data']['abbonamenti_postepay'].append({
                'id': abbonamento.id,
                'nome': abbonamento.nome,
                'descrizione': abbonamento.descrizione,
                'importo': abbonamento.importo,
                'giorno_addebito': abbonamento.giorno_addebito,
                'attivo': abbonamento.attivo,
                'data_creazione': abbonamento.data_creazione.isoformat(),
                'data_disattivazione': abbonamento.data_disattivazione.isoformat() if abbonamento.data_disattivazione else None
            })

        # Esporta movimenti PostePay
        for movimento in MovimentoPostePay.query.all():
            data['data']['movimenti_postepay'].append({
                'id': movimento.id,
                'data': movimento.data.isoformat(),
                'descrizione': movimento.descrizione,
                'importo': movimento.importo,
                'tipo': movimento.tipo,
                'abbonamento_id': movimento.abbonamento_id,
                'data_creazione': movimento.data_creazione.isoformat()
            })

        # Esporta appunti
        for appunto in Appunto.query.all():
            data['data']['appunti'].append({
                'id': appunto.id,
                'titolo': appunto.titolo,
                'tipo': appunto.tipo,
                'importo_stimato': appunto.importo_stimato,
                'categoria_id': appunto.categoria_id,
                'data_creazione': appunto.data_creazione.isoformat(),
                'data_aggiornamento': appunto.data_aggiornamento.isoformat(),
                'note': appunto.note
            })

        # Crea la risposta JSON
        json_data = json.dumps(data, default=serialize_date, indent=2, ensure_ascii=False)
        
        from flask import Response
        response = Response(
            json_data,
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename=bilancio_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            }
        )
        
        flash('Database esportato con successo!', 'success')
        return response
        
    except Exception as e:
        flash(f'Errore durante l\'esportazione: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/database/import', methods=['GET', 'POST'])
def import_database():
    """Importa i dati del database da un file JSON"""
    if request.method == 'POST':
        try:
            import json
            from datetime import datetime, date
            
            # Verifica che sia stato caricato un file
            if 'file' not in request.files:
                flash('Nessun file selezionato!', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('Nessun file selezionato!', 'error')
                return redirect(request.url)
            
            # Verifica che sia un file JSON
            if not file.filename.lower().endswith('.json'):
                flash('Il file deve essere in formato JSON!', 'error')
                return redirect(request.url)
            
            # Leggi e parsifica il JSON
            file_content = file.read().decode('utf-8')
            data = json.loads(file_content)
            
            # Verifica la struttura del file
            if 'data' not in data:
                flash('Formato file non valido!', 'error')
                return redirect(request.url)
            
            # Opzioni di import
            clear_existing = request.form.get('clear_existing') == 'on'
            import_categories = request.form.get('import_categories') == 'on'
            import_transactions = request.form.get('import_transactions') == 'on'
            import_paypal = request.form.get('import_paypal') == 'on'
            import_saldo = request.form.get('import_saldo') == 'on'
            import_conti_personali = request.form.get('import_conti_personali') == 'on'
            import_auto = request.form.get('import_auto') == 'on'
            import_postepay = request.form.get('import_postepay') == 'on'
            
            if clear_existing:
                # Cancella tutti i dati esistenti (con conferma)
                if request.form.get('confirm_clear') == 'on':
                    PaypalRata.query.delete()
                    PaypalPiano.query.delete()
                    Transazione.query.delete()
                    if import_conti_personali:
                        VersamentoPersonale.query.delete()
                        ContoPersonale.query.delete()
                    if import_auto:
                        ManutenzioneAuto.query.delete()
                        BolloAuto.query.delete()
                        Veicolo.query.delete()
                    if import_postepay:
                        MovimentoPostePay.query.delete()
                        AbbonamentoPostePay.query.delete()
                        PostePayEvolution.query.delete()
                    if import_categories:
                        Categoria.query.delete()
                    if import_saldo:
                        SaldoIniziale.query.delete()
                    db.session.commit()
                else:
                    flash('Devi confermare la cancellazione dei dati esistenti!', 'error')
                    return redirect(request.url)
            
            # Importa categorie
            if import_categories and 'categorie' in data['data']:
                for cat_data in data['data']['categorie']:
                    # Verifica se la categoria esiste già
                    existing = Categoria.query.filter_by(nome=cat_data['nome'], tipo=cat_data['tipo']).first()
                    if not existing:
                        categoria = Categoria(
                            nome=cat_data['nome'],
                            tipo=cat_data['tipo']
                        )
                        db.session.add(categoria)
            
            # Importa saldo iniziale
            if import_saldo and 'saldo_iniziale' in data['data']:
                for saldo_data in data['data']['saldo_iniziale']:
                    if not clear_existing:
                        # Se non stiamo cancellando, aggiorna il saldo esistente
                        saldo = SaldoIniziale.query.first()
                        if saldo:
                            saldo.importo = saldo_data['importo']
                            saldo.data_aggiornamento = datetime.fromisoformat(saldo_data['data_aggiornamento'])
                        else:
                            saldo = SaldoIniziale(
                                importo=saldo_data['importo'],
                                data_aggiornamento=datetime.fromisoformat(saldo_data['data_aggiornamento'])
                            )
                            db.session.add(saldo)
                    else:
                        saldo = SaldoIniziale(
                            importo=saldo_data['importo'],
                            data_aggiornamento=datetime.fromisoformat(saldo_data['data_aggiornamento'])
                        )
                        db.session.add(saldo)
            
            db.session.commit()  # Commit categorie e saldo prima delle transazioni
            
            # Importa transazioni
            if import_transactions and 'transazioni' in data['data']:
                for trans_data in data['data']['transazioni']:
                    # Trova la categoria corrispondente
                    categoria = Categoria.query.get(trans_data['categoria_id'])
                    if categoria:
                        transazione = Transazione(
                            data=date.fromisoformat(trans_data['data']),
                            descrizione=trans_data['descrizione'],
                            importo=trans_data['importo'],
                            categoria_id=categoria.id,
                            tipo=trans_data['tipo'],
                            ricorrente=trans_data.get('ricorrente', False),
                            frequenza_giorni=trans_data.get('frequenza_giorni', 0),
                            transazione_madre_id=trans_data.get('transazione_madre_id')
                        )
                        db.session.add(transazione)
            
            # Importa piani PayPal
            if import_paypal and 'piani_paypal' in data['data']:
                for piano_data in data['data']['piani_paypal']:
                    piano = PaypalPiano(
                        descrizione=piano_data['descrizione'],
                        importo_totale=piano_data['importo_totale'],
                        importo_rata=piano_data['importo_rata'],
                        data_prima_rata=date.fromisoformat(piano_data['data_prima_rata']),
                        data_seconda_rata=date.fromisoformat(piano_data['data_seconda_rata']),
                        data_terza_rata=date.fromisoformat(piano_data['data_terza_rata']),
                        importo_rimanente=piano_data['importo_rimanente'],
                        stato=piano_data['stato'],
                        note=piano_data.get('note', '')
                    )
                    db.session.add(piano)
                    db.session.flush()  # Per ottenere l'ID
                    
                    # Importa le rate corrispondenti
                    if 'rate_paypal' in data['data']:
                        for rata_data in data['data']['rate_paypal']:
                            if rata_data['piano_id'] == piano_data['id']:
                                rata = PaypalRata(
                                    piano_id=piano.id,  # Usa il nuovo ID
                                    numero_rata=rata_data['numero_rata'],
                                    importo=rata_data['importo'],
                                    data_scadenza=date.fromisoformat(rata_data['data_scadenza']),
                                    stato=rata_data['stato'],
                                    data_pagamento=date.fromisoformat(rata_data['data_pagamento']) if rata_data['data_pagamento'] else None
                                )
                                db.session.add(rata)
            
            # Importa conti personali
            if import_conti_personali and 'conti_personali' in data['data']:
                for conto_data in data['data']['conti_personali']:
                    # Verifica se il conto esiste già
                    existing_conto = ContoPersonale.query.filter_by(nome_conto=conto_data['nome_conto']).first()
                    if not existing_conto:
                        conto = ContoPersonale(
                            nome_conto=conto_data['nome_conto'],
                            saldo_iniziale=conto_data['saldo_iniziale'],
                            saldo_corrente=conto_data['saldo_corrente'],
                            data_creazione=datetime.fromisoformat(conto_data['data_creazione']),
                            data_aggiornamento=datetime.fromisoformat(conto_data['data_aggiornamento'])
                        )
                        db.session.add(conto)
                        db.session.flush()  # Per ottenere l'ID
                        
                        # Importa i versamenti corrispondenti
                        if 'versamenti_personali' in data['data']:
                            for versamento_data in data['data']['versamenti_personali']:
                                if versamento_data['conto_id'] == conto_data['id']:
                                    versamento = VersamentoPersonale(
                                        conto_id=conto.id,  # Usa il nuovo ID
                                        data=date.fromisoformat(versamento_data['data']),
                                        descrizione=versamento_data['descrizione'],
                                        importo=versamento_data['importo'],
                                        saldo_dopo_versamento=versamento_data['saldo_dopo_versamento'],
                                        data_inserimento=datetime.fromisoformat(versamento_data['data_inserimento'])
                                    )
                                    db.session.add(versamento)
                    else:
                        # Se il conto esiste già, aggiorna solo i dati
                        existing_conto.saldo_iniziale = conto_data['saldo_iniziale']
                        existing_conto.saldo_corrente = conto_data['saldo_corrente']
                        existing_conto.data_aggiornamento = datetime.fromisoformat(conto_data['data_aggiornamento'])
            
            # Importa dati auto (veicoli, bolli, manutenzioni)
            if import_auto:
                # Importa veicoli
                if 'veicoli' in data['data']:
                    for veicolo_data in data['data']['veicoli']:
                        existing_veicolo = Veicolo.query.filter_by(targa=veicolo_data['targa']).first()
                        if not existing_veicolo:
                            veicolo = Veicolo(
                                marca=veicolo_data['marca'],
                                modello=veicolo_data['modello'],
                                targa=veicolo_data['targa'],
                                anno_immatricolazione=veicolo_data['anno_immatricolazione'],
                                cilindrata=veicolo_data.get('cilindrata'),
                                km_iniziali=veicolo_data['km_iniziali'],
                                km_attuali=veicolo_data['km_attuali'],
                                data_acquisto=date.fromisoformat(veicolo_data['data_acquisto']),
                                costo_acquisto=veicolo_data['costo_acquisto'],
                                numero_rate=veicolo_data['numero_rate'],
                                rata_mensile=veicolo_data['rata_mensile'],
                                totale_versato=veicolo_data['totale_versato'],
                                attivo=veicolo_data['attivo'],
                                note=veicolo_data.get('note'),
                                data_inserimento=datetime.fromisoformat(veicolo_data['data_inserimento']),
                                data_aggiornamento=datetime.fromisoformat(veicolo_data['data_aggiornamento'])
                            )
                            db.session.add(veicolo)
                
                # Importa bolli auto
                if 'bolli_auto' in data['data']:
                    for bollo_data in data['data']['bolli_auto']:
                        # Trova il veicolo corrispondente
                        veicolo = Veicolo.query.filter_by(targa=data['data']['veicoli'][bollo_data['veicolo_id']-1]['targa']).first()
                        if veicolo:
                            bollo = BolloAuto(
                                veicolo_id=veicolo.id,
                                anno_riferimento=bollo_data['anno_riferimento'],
                                data_pagamento=date.fromisoformat(bollo_data['data_pagamento']),
                                importo=bollo_data['importo'],
                                data_scadenza=date.fromisoformat(bollo_data['data_scadenza']) if bollo_data.get('data_scadenza') else None,
                                note=bollo_data.get('note'),
                                data_inserimento=datetime.fromisoformat(bollo_data['data_inserimento'])
                            )
                            db.session.add(bollo)
                
                # Importa manutenzioni auto  
                if 'manutenzioni_auto' in data['data']:
                    for manutenzione_data in data['data']['manutenzioni_auto']:
                        # Trova il veicolo corrispondente
                        veicolo = Veicolo.query.filter_by(targa=data['data']['veicoli'][manutenzione_data['veicolo_id']-1]['targa']).first()
                        if veicolo:
                            manutenzione = ManutenzioneAuto(
                                veicolo_id=veicolo.id,
                                data_intervento=date.fromisoformat(manutenzione_data['data_intervento']),
                                km_intervento=manutenzione_data['km_intervento'],
                                officina=manutenzione_data['officina'],
                                tipo_intervento=manutenzione_data['tipo_intervento'],
                                costo=manutenzione_data['costo'],
                                dettaglio=manutenzione_data.get('dettaglio'),
                                prossimo_controllo_km=manutenzione_data.get('prossimo_controllo_km'),
                                prossimo_controllo_data=date.fromisoformat(manutenzione_data['prossimo_controllo_data']) if manutenzione_data.get('prossimo_controllo_data') else None,
                                data_inserimento=datetime.fromisoformat(manutenzione_data['data_inserimento'])
                            )
                            db.session.add(manutenzione)

            # Importa PostePay Evolution
            if import_postepay:
                # Importa saldo PostePay
                if 'postepay_evolution' in data['data']:
                    for postepay_data in data['data']['postepay_evolution']:
                        if not clear_existing:
                            # Se non stiamo cancellando, aggiorna il saldo esistente
                            postepay = PostePayEvolution.query.first()
                            if postepay:
                                postepay.saldo_attuale = postepay_data['saldo_attuale']
                                postepay.data_ultimo_aggiornamento = datetime.fromisoformat(postepay_data['data_ultimo_aggiornamento'])
                            else:
                                postepay = PostePayEvolution(
                                    saldo_attuale=postepay_data['saldo_attuale'],
                                    data_ultimo_aggiornamento=datetime.fromisoformat(postepay_data['data_ultimo_aggiornamento'])
                                )
                                db.session.add(postepay)
                        else:
                            postepay = PostePayEvolution(
                                saldo_attuale=postepay_data['saldo_attuale'],
                                data_ultimo_aggiornamento=datetime.fromisoformat(postepay_data['data_ultimo_aggiornamento'])
                            )
                            db.session.add(postepay)

                # Importa abbonamenti PostePay
                if 'abbonamenti_postepay' in data['data']:
                    for abbonamento_data in data['data']['abbonamenti_postepay']:
                        abbonamento = AbbonamentoPostePay(
                            nome=abbonamento_data['nome'],
                            descrizione=abbonamento_data.get('descrizione'),
                            importo=abbonamento_data['importo'],
                            giorno_addebito=abbonamento_data['giorno_addebito'],
                            attivo=abbonamento_data['attivo'],
                            data_creazione=datetime.fromisoformat(abbonamento_data['data_creazione']),
                            data_disattivazione=datetime.fromisoformat(abbonamento_data['data_disattivazione']) if abbonamento_data.get('data_disattivazione') else None
                        )
                        db.session.add(abbonamento)

                # Importa movimenti PostePay
                if 'movimenti_postepay' in data['data']:
                    for movimento_data in data['data']['movimenti_postepay']:
                        movimento = MovimentoPostePay(
                            data=date.fromisoformat(movimento_data['data']),
                            descrizione=movimento_data['descrizione'],
                            importo=movimento_data['importo'],
                            tipo=movimento_data['tipo'],
                            abbonamento_id=movimento_data.get('abbonamento_id'),
                            data_creazione=datetime.fromisoformat(movimento_data['data_creazione'])
                        )
                        db.session.add(movimento)

                # Importa appunti
                if 'appunti' in data['data']:
                    for appunto_data in data['data']['appunti']:
                        appunto = Appunto(
                            titolo=appunto_data['titolo'],
                            tipo=appunto_data.get('tipo', 'uscita'),
                            importo_stimato=appunto_data.get('importo_stimato'),
                            categoria_id=appunto_data.get('categoria_id'),
                            data_creazione=datetime.fromisoformat(appunto_data['data_creazione']),
                            data_aggiornamento=datetime.fromisoformat(appunto_data['data_aggiornamento']),
                            note=appunto_data.get('note')
                        )
                        db.session.add(appunto)

            db.session.commit()
            flash('Database importato con successo!', 'success')
            return redirect(url_for('index'))
            
        except json.JSONDecodeError:
            flash('Errore nel formato JSON del file!', 'error')
            return redirect(request.url)
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante l\'importazione: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('database_import.html')

# Funzione per export automatico dopo modifiche al DB
def cleanup_old_backups(backup_dir, keep_dates=2):
    """Pulisce i backup vecchi mantenendo solo quelli delle ultime N date"""
    try:
        import os
        import re
        from collections import defaultdict
        
        # Pattern per riconoscere i file di backup (esclude init-db.json)
        pattern = re.compile(r'bilancio_export_(\d{8})_\d{6}\.json')
        
        # File protetti che non devono mai essere eliminati
        protected_files = {'init-db.json'}
        
        # Raggruppa i file per data
        files_by_date = defaultdict(list)
        
        for filename in os.listdir(backup_dir):
            # Salta i file protetti
            if filename in protected_files:
                continue
                
            match = pattern.match(filename)
            if match:
                date_str = match.group(1)  # YYYYMMDD
                full_path = os.path.join(backup_dir, filename)
                files_by_date[date_str].append((filename, full_path))
        
        # Ordina le date (più recenti prima)
        sorted_dates = sorted(files_by_date.keys(), reverse=True)
        
        # Mantieni solo le ultime N date
        dates_to_keep = set(sorted_dates[:keep_dates])
        
        # Elimina i file delle date più vecchie
        files_deleted = 0
        for date_str in sorted_dates:
            if date_str not in dates_to_keep:
                for filename, full_path in files_by_date[date_str]:
                    try:
                        os.remove(full_path)
                        print(f"Backup eliminato: {filename}")
                        files_deleted += 1
                    except OSError as e:
                        print(f"Errore nell'eliminazione di {filename}: {e}")
        
        if files_deleted > 0:
            print(f"Pulizia backup completata: {files_deleted} file eliminati")
        else:
            print("Nessun backup da eliminare")
            
    except Exception as e:
        print(f"Errore durante la pulizia dei backup: {str(e)}")

def export_database_to_backup():
    """Esporta il database nella cartella backup dopo modifiche"""
    try:
        import json
        import os
        from datetime import date, datetime
        
        def serialize_date(obj):
            """Serializzatore personalizzato per date e datetime"""
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            raise TypeError(f"Object {obj} is not JSON serializable")
        
        # Raccogli tutti i dati del database
        data = {
            'export_date': datetime.now().isoformat(),
            'version': '1.0',
            'data': {
                'categorie': [],
                'saldo_iniziale': [],
                'transazioni': [],
                'piani_paypal': [],
                'rate_paypal': [],
                'conti_personali': [],
                'versamenti_personali': [],
                'veicoli': [],
                'bolli_auto': [],
                'manutenzioni_auto': [],
                'postepay_evolution': [],
                'abbonamenti_postepay': [],
                'movimenti_postepay': [],
                'appunti': []
            }
        }
        
        # Esporta categorie
        for categoria in Categoria.query.all():
            data['data']['categorie'].append({
                'id': categoria.id,
                'nome': categoria.nome,
                'tipo': categoria.tipo
            })
        
        # Esporta saldo iniziale
        for saldo in SaldoIniziale.query.all():
            data['data']['saldo_iniziale'].append({
                'id': saldo.id,
                'importo': saldo.importo,
                'data_aggiornamento': saldo.data_aggiornamento.isoformat()
            })
        
        # Esporta transazioni
        for transazione in Transazione.query.all():
            data['data']['transazioni'].append({
                'id': transazione.id,
                'data': transazione.data.isoformat(),
                'descrizione': transazione.descrizione,
                'importo': transazione.importo,
                'categoria_id': transazione.categoria_id,
                'tipo': transazione.tipo,
                'ricorrente': transazione.ricorrente,
                'frequenza_giorni': transazione.frequenza_giorni,
                'transazione_madre_id': transazione.transazione_madre_id
            })
        
        # Esporta piani PayPal
        for piano in PaypalPiano.query.all():
            data['data']['piani_paypal'].append({
                'id': piano.id,
                'descrizione': piano.descrizione,
                'importo_totale': piano.importo_totale,
                'importo_rata': piano.importo_rata,
                'data_prima_rata': piano.data_prima_rata.isoformat(),
                'data_seconda_rata': piano.data_seconda_rata.isoformat(),
                'data_terza_rata': piano.data_terza_rata.isoformat(),
                'importo_rimanente': piano.importo_rimanente,
                'stato': piano.stato,
                'note': piano.note
            })
        
        # Esporta rate PayPal
        for rata in PaypalRata.query.all():
            data['data']['rate_paypal'].append({
                'id': rata.id,
                'piano_id': rata.piano_id,
                'numero_rata': rata.numero_rata,
                'importo': rata.importo,
                'data_scadenza': rata.data_scadenza.isoformat(),
                'stato': rata.stato,
                'data_pagamento': rata.data_pagamento.isoformat() if rata.data_pagamento else None
            })
        
        # Esporta conti personali
        for conto in ContoPersonale.query.all():
            data['data']['conti_personali'].append({
                'id': conto.id,
                'nome_conto': conto.nome_conto,
                'saldo_iniziale': conto.saldo_iniziale,
                'saldo_corrente': conto.saldo_corrente,
                'data_creazione': conto.data_creazione.isoformat(),
                'data_aggiornamento': conto.data_aggiornamento.isoformat()
            })
        
        # Esporta versamenti personali
        for versamento in VersamentoPersonale.query.all():
            data['data']['versamenti_personali'].append({
                'id': versamento.id,
                'conto_id': versamento.conto_id,
                'data': versamento.data.isoformat(),
                'descrizione': versamento.descrizione,
                'importo': versamento.importo,
                'saldo_dopo_versamento': versamento.saldo_dopo_versamento,
                'data_inserimento': versamento.data_inserimento.isoformat()
            })
        
        # Esporta veicoli
        for veicolo in Veicolo.query.all():
            data['data']['veicoli'].append({
                'id': veicolo.id,
                'marca': veicolo.marca,
                'modello': veicolo.modello,
                'mese_scadenza_bollo': veicolo.mese_scadenza_bollo,
                'costo_finanziamento': veicolo.costo_finanziamento,
                'prima_rata': veicolo.prima_rata.isoformat(),
                'numero_rate': veicolo.numero_rate,
                'rata_mensile': veicolo.rata_mensile,
                'data_creazione': veicolo.data_creazione.isoformat()
            })
        
        # Esporta bolli auto
        for bollo in BolloAuto.query.all():
            data['data']['bolli_auto'].append({
                'id': bollo.id,
                'veicolo_id': bollo.veicolo_id,
                'anno_riferimento': bollo.anno_riferimento,
                'data_pagamento': bollo.data_pagamento.isoformat(),
                'importo': bollo.importo
            })
        
        # Esporta manutenzioni auto
        for manutenzione in ManutenzioneAuto.query.all():
            data['data']['manutenzioni_auto'].append({
                'id': manutenzione.id,
                'veicolo_id': manutenzione.veicolo_id,
                'data_intervento': manutenzione.data_intervento.isoformat(),
                'tipo_intervento': manutenzione.tipo_intervento,
                'descrizione': manutenzione.descrizione,
                'costo': manutenzione.costo,
                'km_intervento': manutenzione.km_intervento,
                'officina': manutenzione.officina
            })

        # Esporta PostePay Evolution
        for postepay in PostePayEvolution.query.all():
            data['data']['postepay_evolution'].append({
                'id': postepay.id,
                'saldo_attuale': postepay.saldo_attuale,
                'data_ultimo_aggiornamento': postepay.data_ultimo_aggiornamento.isoformat()
            })

        # Esporta abbonamenti PostePay
        for abbonamento in AbbonamentoPostePay.query.all():
            data['data']['abbonamenti_postepay'].append({
                'id': abbonamento.id,
                'nome': abbonamento.nome,
                'descrizione': abbonamento.descrizione,
                'importo': abbonamento.importo,
                'giorno_addebito': abbonamento.giorno_addebito,
                'attivo': abbonamento.attivo,
                'data_creazione': abbonamento.data_creazione.isoformat(),
                'data_disattivazione': abbonamento.data_disattivazione.isoformat() if abbonamento.data_disattivazione else None
            })

        # Esporta movimenti PostePay
        for movimento in MovimentoPostePay.query.all():
            data['data']['movimenti_postepay'].append({
                'id': movimento.id,
                'data': movimento.data.isoformat(),
                'descrizione': movimento.descrizione,
                'importo': movimento.importo,
                'tipo': movimento.tipo,
                'abbonamento_id': movimento.abbonamento_id,
                'data_creazione': movimento.data_creazione.isoformat()
            })

        # Esporta appunti
        for appunto in Appunto.query.all():
            data['data']['appunti'].append({
                'id': appunto.id,
                'titolo': appunto.titolo,
                'tipo': appunto.tipo,
                'importo_stimato': appunto.importo_stimato,
                'categoria_id': appunto.categoria_id,
                'data_creazione': appunto.data_creazione.isoformat(),
                'data_aggiornamento': appunto.data_aggiornamento.isoformat(),
                'note': appunto.note
            })

        # Salva il file JSON nella cartella backup
        backup_dir = '/app/backup'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        filename = f'bilancio_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        filepath = os.path.join(backup_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=serialize_date, indent=2, ensure_ascii=False)
        
        print(f"Database export salvato in: {filepath}")
        
        # Pulizia automatica: mantieni solo i backup delle ultime N date (configurabile)
        keep_dates = app.config.get('BACKUP_KEEP_DATES', 2)
        cleanup_old_backups(backup_dir, keep_dates)
        
        return True
        
    except Exception as e:
        print(f"Errore durante l'export del database: {str(e)}")
        return False

def find_latest_backup():
    """Trova l'ultimo file di backup JSON nella cartella backup"""
    try:
        import os
        import re
        
        backup_dir = '/app/backup'
        if not os.path.exists(backup_dir):
            return None
        
        # Pattern per riconoscere i file di backup
        pattern = re.compile(r'bilancio_export_(\d{8})_(\d{6})\.json')
        backup_files = []
        
        for filename in os.listdir(backup_dir):
            match = pattern.match(filename)
            if match:
                date_str = match.group(1)  # YYYYMMDD
                time_str = match.group(2)  # HHMMSS
                full_path = os.path.join(backup_dir, filename)
                backup_files.append((date_str, time_str, filename, full_path))
        
        if not backup_files:
            # Se non ci sono backup automatici, cerca init-db.json come fallback
            init_file = os.path.join(backup_dir, 'init-db.json')
            if os.path.exists(init_file):
                print("Nessun backup automatico trovato, usando init-db.json")
                return init_file
            return None
        
        # Ordina per data e ora (più recente prima)
        backup_files.sort(key=lambda x: (x[0], x[1]), reverse=True)
        latest_backup = backup_files[0]
        
        print(f"Backup più recente trovato: {latest_backup[2]}")
        return latest_backup[3]  # Ritorna il path completo
        
    except Exception as e:
        print(f"Errore durante la ricerca del backup: {e}")
        return None

def import_backup_data(backup_file_path):
    """Importa i dati da un file di backup JSON"""
    try:
        import json
        from datetime import datetime, date
        
        print(f"Importando backup da: {backup_file_path}")
        
        with open(backup_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Importa categorie
        if 'categorie' in data['data']:
            for cat_data in data['data']['categorie']:
                if not Categoria.query.filter_by(nome=cat_data['nome'], tipo=cat_data['tipo']).first():
                    categoria = Categoria(nome=cat_data['nome'], tipo=cat_data['tipo'])
                    db.session.add(categoria)
        
        # Importa saldo iniziale
        if 'saldo_iniziale' in data['data'] and data['data']['saldo_iniziale']:
            saldo_data = data['data']['saldo_iniziale'][0]  # Prendi il primo (dovrebbe essere unico)
            if not SaldoIniziale.query.first():
                saldo = SaldoIniziale(
                    importo=saldo_data['importo'],
                    data_aggiornamento=datetime.fromisoformat(saldo_data['data_aggiornamento'])
                )
                db.session.add(saldo)
        
        db.session.commit()
        
        # Importa transazioni
        if 'transazioni' in data['data']:
            for trans_data in data['data']['transazioni']:
                if not Transazione.query.filter_by(id=trans_data['id']).first():
                    transazione = Transazione(
                        data=datetime.fromisoformat(trans_data['data']).date(),
                        descrizione=trans_data['descrizione'],
                        importo=trans_data['importo'],
                        categoria_id=trans_data['categoria_id'],
                        tipo=trans_data['tipo'],
                        ricorrente=trans_data.get('ricorrente', False),
                        frequenza_giorni=trans_data.get('frequenza_giorni'),
                        transazione_madre_id=trans_data.get('transazione_madre_id')
                    )
                    db.session.add(transazione)
        
        # Importa piani PayPal
        if 'piani_paypal' in data['data']:
            for piano_data in data['data']['piani_paypal']:
                if not PaypalPiano.query.filter_by(id=piano_data['id']).first():
                    piano = PaypalPiano(
                        descrizione=piano_data['descrizione'],
                        importo_totale=piano_data['importo_totale'],
                        importo_rata=piano_data['importo_rata'],
                        data_prima_rata=datetime.fromisoformat(piano_data['data_prima_rata']).date(),
                        data_seconda_rata=datetime.fromisoformat(piano_data['data_seconda_rata']).date(),
                        data_terza_rata=datetime.fromisoformat(piano_data['data_terza_rata']).date(),
                        importo_rimanente=piano_data['importo_rimanente'],
                        stato=piano_data['stato'],
                        note=piano_data.get('note', '')
                    )
                    db.session.add(piano)
        
        # Importa rate PayPal
        if 'rate_paypal' in data['data']:
            for rata_data in data['data']['rate_paypal']:
                if not PaypalRata.query.filter_by(id=rata_data['id']).first():
                    rata = PaypalRata(
                        piano_id=rata_data['piano_id'],
                        numero_rata=rata_data['numero_rata'],
                        importo=rata_data['importo'],
                        data_scadenza=datetime.fromisoformat(rata_data['data_scadenza']).date(),
                        stato=rata_data['stato'],
                        data_pagamento=datetime.fromisoformat(rata_data['data_pagamento']).date() if rata_data['data_pagamento'] else None
                    )
                    db.session.add(rata)

        # Importa appunti
        if 'appunti' in data['data']:
            for appunto_data in data['data']['appunti']:
                if not Appunto.query.filter_by(id=appunto_data['id']).first():
                    appunto = Appunto(
                        titolo=appunto_data['titolo'],
                        tipo=appunto_data.get('tipo', 'uscita'),
                        importo_stimato=appunto_data.get('importo_stimato'),
                        categoria_id=appunto_data.get('categoria_id'),
                        data_creazione=datetime.fromisoformat(appunto_data['data_creazione']),
                        data_aggiornamento=datetime.fromisoformat(appunto_data['data_aggiornamento']),
                        note=appunto_data.get('note')
                    )
                    db.session.add(appunto)
        
        db.session.commit()
        print("✅ Backup importato con successo!")
        return True
        
    except Exception as e:
        print(f"❌ Errore durante l'importazione del backup: {e}")
        db.session.rollback()
        return False

def is_database_empty():
    """Controlla se il database è vuoto (nessuna categoria, transazione o saldo)"""
    return (Categoria.query.count() == 0 and 
            Transazione.query.count() == 0 and 
            SaldoIniziale.query.count() == 0)

def init_db():
    """Inizializza il database solo se vuoto, ripristinando dall'ultimo backup"""
    print("🚀 Controllo stato database...")
    
    # Crea le tabelle se non esistono
    db.create_all()
    
    # Controlla se il database è vuoto
    if is_database_empty():
        print("📂 Database vuoto rilevato. Cercando backup da ripristinare...")
        
        # Prova a trovare e importare l'ultimo backup
        latest_backup = find_latest_backup()
        if latest_backup:
            print(f"📦 Trovato backup: {latest_backup}")
            if import_backup_data(latest_backup):
                print("✅ Database ripristinato da backup!")
                return
            else:
                print("❌ Fallito ripristino da backup.")
                exit(1)
        else:
            print("❌ Nessun backup trovato. Impossibile procedere.")
            print("💡 Suggerimento: Posiziona un file di backup nella cartella backup/")
            exit(1)
    else:
        print("✅ Database esistente trovato, nessuna inizializzazione necessaria")

def crea_transazioni_predefinite():
    """
    Logica SEMPLICE: 
    1. Identifica i tipi UNICI di transazione
    2. Crea UNA SOLA madre per ogni tipo unico
    3. Crea figlie per i prossimi 6 mesi
    """
    try:
        from datetime import datetime
        import calendar
        
        oggi = datetime.now().date()
        limite_6_mesi = oggi + relativedelta(months=6)
        
        print(f"=== CREAZIONE TRANSAZIONI - Data: {oggi} ===")
        
        # Ottieni le categorie dal database
        categorie_map = {}
        for categoria in Categoria.query.all():
            categorie_map[categoria.nome] = categoria.id
        
        print(f"Categorie trovate: {len(categorie_map)}")
        
        # STEP 1: Identifica i tipi UNICI di transazione
        transazioni_uniche = {}
        
        print(f"Scansione delle {len(app.config['TRANSAZIONI_DEFAULT'])} transazioni di default...")
        
        for transazione_def in app.config['TRANSAZIONI_DEFAULT']:
            if isinstance(transazione_def[0], str):  # Data completa (formato DD/MM/YYYY)
                data_str, descrizione, tipo, categoria_nome, importo, ricorrenza = transazione_def
                print(f"Esaminando con data: {descrizione} ({data_str})")
                
                # Estrai il giorno dalla data
                try:
                    data_obj = datetime.strptime(data_str, '%d/%m/%Y').date()
                    giorno = data_obj.day
                except ValueError:
                    print(f"  -> Errore nel parsing della data {data_str}")
                    continue
                
                if ricorrenza == 'Mensile' and categoria_nome in categorie_map:
                    # Usa la descrizione come chiave unica
                    if descrizione not in transazioni_uniche:
                        transazioni_uniche[descrizione] = {
                            'giorno': giorno,
                            'data_iniziale': data_obj,
                            'tipo': tipo,
                            'categoria_nome': categoria_nome,
                            'importo': importo,
                            'frequenza': 'mensile'
                        }
                        print(f"  -> Aggiunta come unica: {descrizione} (giorno {giorno})")
            
            elif isinstance(transazione_def[0], int):  # Legacy: solo giorno
                giorno, descrizione, tipo, categoria_nome, importo, ricorrenza = transazione_def
                print(f"Esaminando mensile legacy: {descrizione}")
                if ricorrenza == 'Mensile' and categoria_nome in categorie_map:
                    # Usa la descrizione come chiave unica
                    if descrizione not in transazioni_uniche:
                        transazioni_uniche[descrizione] = {
                            'giorno': giorno,
                            'tipo': tipo,
                            'categoria_nome': categoria_nome,
                            'importo': importo,
                            'frequenza': 'mensile'
                        }
                        print(f"  -> Aggiunta come unica: {descrizione}")
            
            elif isinstance(transazione_def[0], tuple):  # Annuale
                (giorno, mese), descrizione, tipo, categoria_nome, importo, ricorrenza = transazione_def
                print(f"Esaminando annuale: {descrizione}")
                if ricorrenza in ['Annuale', 'StipendioSpeciale'] and categoria_nome in categorie_map:
                    if descrizione not in transazioni_uniche:
                        transazioni_uniche[descrizione] = {
                            'giorno': giorno,
                            'mese': mese,
                            'tipo': tipo,
                            'categoria_nome': categoria_nome,
                            'importo': importo,
                            'frequenza': 'annuale'
                        }
                        print(f"  -> Aggiunta come unica: {descrizione}")
        
        print(f"Transazioni uniche identificate: {len(transazioni_uniche)}")
        for desc in transazioni_uniche.keys():
            print(f"  - {desc}")
        
        # STEP 2: Crea UNA SOLA madre per ogni tipo unico
        madri_create = []
        
        for descrizione, info in transazioni_uniche.items():
            print(f"Creando madre per: {descrizione}")
            if info['frequenza'] == 'mensile':
                # Calcola la prima data disponibile
                if 'data_iniziale' in info:
                    # Usa la data iniziale specificata nel config
                    data_madre = info['data_iniziale']
                    print(f"Usando data iniziale specificata: {data_madre}")
                else:
                    # Calcola in base al giorno (logica legacy)
                    try:
                        data_madre = oggi.replace(day=info['giorno'])
                        if data_madre < oggi:
                            data_madre = (oggi + relativedelta(months=1)).replace(day=info['giorno'])
                    except ValueError:
                        ultimo_giorno = calendar.monthrange(oggi.year, oggi.month)[1]
                        data_madre = oggi.replace(day=min(info['giorno'], ultimo_giorno))
                
                madre = Transazione(
                    descrizione=descrizione,
                    importo=info['importo'],
                    data=data_madre,
                    tipo=info['tipo'].lower(),
                    categoria_id=categorie_map[info['categoria_nome']],
                    ricorrente=True,
                    frequenza_giorni=30
                )
                db.session.add(madre)
                madri_create.append({
                    'madre': madre,
                    'info': info,
                    'descrizione': descrizione
                })
                print(f"Madre mensile creata: {descrizione} -> {data_madre}")
            
            elif info['frequenza'] == 'annuale':
                # Calcola la prossima data annuale
                try:
                    data_questo_anno = datetime(oggi.year, info['mese'], info['giorno']).date()
                    if data_questo_anno < oggi:
                        data_madre = datetime(oggi.year + 1, info['mese'], info['giorno']).date()
                    else:
                        data_madre = data_questo_anno
                    
                    # Crea solo se entro 6 mesi
                    if data_madre <= limite_6_mesi:
                        madre = Transazione(
                            descrizione=descrizione,
                            importo=info['importo'],
                            data=data_madre,
                            tipo=info['tipo'].lower(),
                            categoria_id=categorie_map[info['categoria_nome']],
                            ricorrente=True,
                            frequenza_giorni=365
                        )
                        db.session.add(madre)
                        madri_create.append({
                            'madre': madre,
                            'info': info,
                            'descrizione': descrizione
                        })
                        print(f"Madre annuale creata: {descrizione} -> {data_madre}")
                    else:
                        print(f"Annuale {descrizione} saltata: oltre 6 mesi")
                except ValueError:
                    print(f"Data non valida per {descrizione}")
        
        # Salva le madri
        db.session.commit()
        print(f"\nMadri salvate: {len(madri_create)}")
        
        # STEP 3: Crea figlie per i prossimi 6 mesi
        for madre_info in madri_create:
            madre = madre_info['madre']
            info = madre_info['info']
            descrizione = madre_info['descrizione']
            
            db.session.refresh(madre)  # Ricarica per avere l'ID
            
            if info['frequenza'] == 'mensile':
                print(f"Creando figlie per {descrizione}:")
                
                for mese in range(1, 7):  # 6 mesi dopo la madre
                    data_figlia = madre.data + relativedelta(months=mese)
                    
                    # Salta stipendio normale a dicembre
                    if descrizione == 'Stipendio' and data_figlia.month == 12:
                        print(f"  Mese {mese}: Saltato (stipendio dicembre)")
                        continue
                    
                    try:
                        data_figlia = data_figlia.replace(day=info['giorno'])
                    except ValueError:
                        ultimo_giorno = calendar.monthrange(data_figlia.year, data_figlia.month)[1]
                        data_figlia = data_figlia.replace(day=min(info['giorno'], ultimo_giorno))
                    
                    figlia = Transazione(
                        descrizione=descrizione,
                        importo=info['importo'],
                        data=data_figlia,
                        tipo=info['tipo'].lower(),
                        categoria_id=categorie_map[info['categoria_nome']],
                        ricorrente=False,
                        transazione_madre_id=madre.id
                    )
                    db.session.add(figlia)
                    print(f"  Mese {mese}: {data_figlia}")
            
            elif info['frequenza'] == 'annuale':
                print(f"{descrizione}: figlie annuali create al runtime")
        
        # Salva tutte le figlie
        db.session.commit()
        
        # Statistiche finali
        totale = Transazione.query.count()
        madri = Transazione.query.filter_by(ricorrente=True).count()
        figlie = Transazione.query.filter_by(ricorrente=False).filter(Transazione.transazione_madre_id.isnot(None)).count()
        
        print(f"\n=== COMPLETATO ===")
        print(f"Totale: {totale}, Madri: {madri}, Figlie: {figlie}")
        print("Transazioni predefinite create!")
        
    except Exception as e:
        print(f"ERRORE in crea_transazioni_predefinite: {e}")
        import traceback
        traceback.print_exc()
def crea_piani_paypal_predefiniti():
    """Crea i piani PayPal predefiniti dal file di configurazione"""
    
    # Controlla se ci sono già piani PayPal
    if PaypalPiano.query.count() > 0:
        return
        
    # I piani PayPal non necessitano più di categoria
    # perché le transazioni PayPal non fanno parte del bilancio principale
    
    piani_creati = 0
    for piano_data in app.config['PIANI_PAYPAL_DEFAULT']:
        descrizione, rata1_importo, rata1_data_str, rata2_importo, rata2_data_str, rata3_importo, rata3_data_str = piano_data
        
        # Converti le date stringa in date Python
        try:
            rata1_data = datetime.strptime(rata1_data_str, '%d/%m/%Y').date() if rata1_data_str else None
            rata2_data = datetime.strptime(rata2_data_str, '%d/%m/%Y').date() if rata2_data_str else None
            rata3_data = datetime.strptime(rata3_data_str, '%d/%m/%Y').date() if rata3_data_str else None
        except ValueError:
            print(f"Errore nel parsing delle date per il piano {descrizione}")
            continue
        
        if rata1_data and rata2_data and rata3_data:
            # Calcola importo totale dalle tre rate (la rimanenza è calcolata dinamicamente)
            importo_totale = rata1_importo + rata2_importo + rata3_importo
            
            # Calcola la rimanenza dinamicamente (somma delle rate future)
            oggi = datetime.now().date()
            importo_rimanente_calcolato = 0
            if rata1_data > oggi:
                importo_rimanente_calcolato += rata1_importo
            if rata2_data > oggi:
                importo_rimanente_calcolato += rata2_importo
            if rata3_data > oggi:
                importo_rimanente_calcolato += rata3_importo
            
            # Crea il piano con stato iniziale "in_corso"
            piano = PaypalPiano(
                descrizione=descrizione,
                importo_totale=importo_totale,
                importo_rata=rata1_importo,  # Usa l'importo della prima rata come riferimento
                data_prima_rata=rata1_data,
                data_seconda_rata=rata2_data,
                data_terza_rata=rata3_data,
                importo_rimanente=importo_rimanente_calcolato,
                stato='in_corso'  # Sempre in_corso all'inizio
            )
            db.session.add(piano)
            db.session.flush()  # Per ottenere l'ID
            
            # Crea le rate individuali
            rate_info = [
                (1, rata1_importo, rata1_data),
                (2, rata2_importo, rata2_data),
                (3, rata3_importo, rata3_data)
            ]
            
            for numero, importo, data_scad in rate_info:
                if importo > 0:
                    # La prima rata è sempre pagata alla creazione del piano
                    if numero == 1:
                        stato = 'pagata'
                        data_pagamento = data_scad
                    else:
                        # Le altre rate seguono la logica normale
                        oggi = datetime.now().date()
                        if data_scad <= oggi:
                            stato = 'pagata'
                            data_pagamento = data_scad
                        else:
                            stato = 'in_attesa'
                            data_pagamento = None
                    
                    rata = PaypalRata(
                        piano_id=piano.id,
                        numero_rata=numero,
                        importo=importo,
                        data_scadenza=data_scad,
                        stato=stato,
                        data_pagamento=data_pagamento
                    )
                    db.session.add(rata)
                    
                    # Se la rata è marcata come pagata, crea anche la transazione
                    if stato == 'pagata':
                        transazione = Transazione(
                            data=data_pagamento,
                            descrizione=f"PayPal - {descrizione} (Rata {numero}/3)",
                            importo=importo,
                            categoria_id=None,  # Nessuna categoria per transazioni PayPal
                            tipo='uscita'
                        )
                        db.session.add(transazione)
                        db.session.flush()
                        rata.transazione_id = transazione.id
            
            piani_creati += 1
    
    db.session.commit()
    print(f"Piani PayPal predefiniti creati con successo! ({piani_creati} piani)")

def aggiorna_importi_rimanenti_paypal():
    """Aggiorna dinamicamente l'importo rimanente di tutti i piani PayPal"""
    oggi = datetime.now().date()
    
    for piano in PaypalPiano.query.all():
        # Prima aggiorna automaticamente lo stato delle rate in base alla data
        for rata in piano.rate:
            if rata.data_scadenza <= oggi and rata.stato == 'in_attesa':
                # Marca come pagata le rate scadute
                rata.stato = 'pagata'
                rata.data_pagamento = rata.data_scadenza
                
                # Crea la transazione se non esiste
                if not rata.transazione_id:
                    categoria_paypal = Categoria.query.filter_by(nome='PayPal', tipo='uscita').first()
                    if categoria_paypal:
                        transazione = Transazione(
                            data=rata.data_scadenza,
                            descrizione=f"PayPal - {piano.descrizione} (Rata {rata.numero_rata}/3)",
                            importo=rata.importo,
                            categoria_id=categoria_paypal.id,
                            tipo='uscita'
                        )
                        db.session.add(transazione)
                        db.session.flush()
                        rata.transazione_id = transazione.id
        
        # Il totale è la somma delle 3 rate
        importo_totale = sum(rata.importo for rata in piano.rate)
        
        # La rimanenza è il totale meno la somma delle rate effettivamente pagate
        importo_pagato = 0
        for rata in piano.rate:
            if rata.stato == 'pagata':
                importo_pagato += rata.importo
        
        importo_rimanente = importo_totale - importo_pagato
        
        # Aggiorna i valori del piano
        piano.importo_totale = importo_totale
        piano.importo_rimanente = max(0, importo_rimanente)
        
        # Aggiorna lo stato del piano in base alle rate effettivamente pagate
        rate_totali = len(piano.rate)
        rate_pagate = len([r for r in piano.rate if r.stato == 'pagata'])
        
        if rate_pagate == rate_totali:
            piano.stato = 'completato'
        else:
            piano.stato = 'in_corso'
    
    db.session.commit()

@app.route('/database/backup_export')
def backup_export():
    """Endpoint per export automatico nella cartella backup"""
    if export_database_to_backup():
        flash('Database esportato con successo nella cartella backup!', 'success')
    else:
        flash('Errore durante l\'export del database!', 'error')
    return redirect(url_for('index'))

# =============================================
# CONTI PERSONALI - MAURIZIO E ANTONIETTA
# =============================================

def inizializza_conto_personale(nome_conto):
    """Inizializza un conto personale se non esiste"""
    conto = ContoPersonale.query.filter_by(nome_conto=nome_conto).first()
    if not conto:
        if nome_conto == 'Maurizio':
            saldo_iniziale = app.config['CONTO_MAURIZIO_SALDO_INIZIALE']
        else:
            saldo_iniziale = app.config['CONTO_ANTONIETTA_SALDO_INIZIALE']
        
        conto = ContoPersonale(
            nome_conto=nome_conto,
            saldo_iniziale=saldo_iniziale,
            saldo_corrente=saldo_iniziale
        )
        db.session.add(conto)
        db.session.commit()
    return conto

@app.route('/maurizio')
def maurizio():
    """Dashboard per il conto di Maurizio"""
    conto = inizializza_conto_personale('Maurizio')
    versamenti = VersamentoPersonale.query.filter_by(conto_id=conto.id).order_by(VersamentoPersonale.data.desc()).all()
    return render_template('conto_personale.html', 
                         conto=conto, 
                         versamenti=versamenti,
                         nome_persona='Maurizio',
                         config=app.config)

@app.route('/antonietta')
def antonietta():
    """Dashboard per il conto di Antonietta"""
    conto = inizializza_conto_personale('Antonietta')
    versamenti = VersamentoPersonale.query.filter_by(conto_id=conto.id).order_by(VersamentoPersonale.data.desc()).all()
    return render_template('conto_personale.html', 
                         conto=conto, 
                         versamenti=versamenti,
                         nome_persona='Antonietta',
                         config=app.config)

@app.route('/auto')
def auto_garage():
    """Dashboard del garage auto"""
    veicoli = Veicolo.query.order_by(Veicolo.marca, Veicolo.modello).all()
    
    # Statistiche generali (gestisce valori None)
    totale_costo_finanziamento = sum(v.costo_finanziamento or 0 for v in veicoli)
    totale_versato = sum(v.totale_versato for v in veicoli)
    totale_saldo_rimanente = sum(v.saldo_rimanente for v in veicoli)
    
    # Ultimi bolli e manutenzioni
    ultimi_bolli = BolloAuto.query.join(Veicolo).order_by(BolloAuto.data_pagamento.desc()).limit(5).all()
    ultime_manutenzioni = ManutenzioneAuto.query.join(Veicolo).order_by(ManutenzioneAuto.data_intervento.desc()).limit(5).all()
    
    # Veicoli con bolli in attesa di pagamento
    bolli_in_attesa = []
    
    # Mappa per convertire numero mese in nome
    nomi_mesi = {
        1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile',
        5: 'Maggio', 6: 'Giugno', 7: 'Luglio', 8: 'Agosto',
        9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
    }
    
    for veicolo in veicoli:
        # Controlla bolli scaduti/in scadenza se ha il campo mese_scadenza_bollo
        if veicolo.mese_scadenza_bollo and veicolo.prima_rata:
            oggi = datetime.now()
            anno_corrente = oggi.year
            mese_corrente = oggi.month
            
            # Nome del mese di scadenza
            nome_mese_scadenza = nomi_mesi.get(veicolo.mese_scadenza_bollo, f'Mese {veicolo.mese_scadenza_bollo}')
            
            # Calcola il primo anno per cui il veicolo doveva pagare il bollo
            # (dal secondo anno della prima rata)
            primo_anno_bollo = veicolo.prima_rata.year + 1
            
            # Controlla tutti gli anni dal primo anno del bollo fino all'anno corrente
            for anno in range(primo_anno_bollo, anno_corrente + 1):
                bollo_pagato = BolloAuto.query.filter_by(
                    veicolo_id=veicolo.id,
                    anno_riferimento=anno
                ).first()
                
                if not bollo_pagato:
                    # Se è l'anno corrente, controlla se siamo già oltre il mese di scadenza
                    if anno == anno_corrente:
                        if mese_corrente > veicolo.mese_scadenza_bollo:
                            bolli_in_attesa.append({
                                'veicolo': veicolo,
                                'tipo': 'Bollo Auto Scaduto',
                                'scadenza': None,
                                'giorni': -999,  # Priorità massima per scaduti
                                'dettaglio': f'Bollo {anno} non pagato (scadenza {nome_mese_scadenza})',
                                'anno': anno
                            })
                        elif mese_corrente == veicolo.mese_scadenza_bollo:
                            # In scadenza questo mese
                            bolli_in_attesa.append({
                                'veicolo': veicolo,
                                'tipo': 'Bollo Auto in Scadenza',
                                'scadenza': None,
                                'giorni': 0,
                                'dettaglio': f'Bollo {anno} in scadenza questo mese ({nome_mese_scadenza})',
                                'anno': anno
                            })
                        else:
                            # Futuro (non ancora in scadenza)
                            bolli_in_attesa.append({
                                'veicolo': veicolo,
                                'tipo': 'Bollo Auto da Pagare',
                                'scadenza': None,
                                'giorni': (veicolo.mese_scadenza_bollo - mese_corrente) * 30,  # Stima giorni
                                'dettaglio': f'Bollo {anno} da pagare (scadenza {nome_mese_scadenza})',
                                'anno': anno
                            })
                    else:
                        # Per gli anni passati, il bollo è sempre scaduto
                        bolli_in_attesa.append({
                            'veicolo': veicolo,
                            'tipo': 'Bollo Auto Scaduto',
                            'scadenza': None,
                            'giorni': -1000 - (anno_corrente - anno),  # Più vecchio = priorità più alta
                            'dettaglio': f'Bollo {anno} non pagato (scadenza {nome_mese_scadenza})',
                            'anno': anno
                        })
    
    # Ordina per urgenza (scaduti prima, poi per anno)
    bolli_in_attesa.sort(key=lambda x: (x['giorni'], x['anno']))
    
    return render_template('auto_garage.html',
                         veicoli=veicoli,
                         totale_costo_finanziamento=totale_costo_finanziamento,
                         totale_versato=totale_versato,
                         totale_saldo_rimanente=totale_saldo_rimanente,
                         ultimi_bolli=ultimi_bolli,
                         ultime_manutenzioni=ultime_manutenzioni,
                         bolli_in_attesa=bolli_in_attesa,
                         formato_valuta=app.config['FORMATO_VALUTA'])

@app.route('/aggiungi_versamento/<nome_conto>', methods=['POST'])
def aggiungi_versamento(nome_conto):
    """Aggiunge un versamento al conto personale"""
    try:
        conto = inizializza_conto_personale(nome_conto)
        
        data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        descrizione = request.form['descrizione'].strip()
        importo = float(request.form['importo'])
        
        if not descrizione:
            flash('La descrizione è obbligatoria!', 'error')
            return redirect(url_for(nome_conto.lower()))
        
        if importo <= 0:
            flash('L\'importo deve essere positivo!', 'error')
            return redirect(url_for(nome_conto.lower()))
        
        if importo > conto.saldo_corrente:
            flash('Importo superiore al saldo disponibile!', 'error')
            return redirect(url_for(nome_conto.lower()))
        
        # Calcola il nuovo saldo
        nuovo_saldo = conto.saldo_corrente - importo
        
        # Crea il versamento
        versamento = VersamentoPersonale(
            conto_id=conto.id,
            data=data,
            descrizione=descrizione,
            importo=importo,
            saldo_dopo_versamento=nuovo_saldo
        )
        
        # Aggiorna il saldo del conto
        conto.saldo_corrente = nuovo_saldo
        
        db.session.add(versamento)
        db.session.commit()
        
        flash(f'Versamento di {app.config["CONTO_PERSONALE_FORMATO_VALUTA"].format(importo)} aggiunto con successo!', 'success')
        
    except ValueError:
        flash('Errore nei dati inseriti!', 'error')
    except Exception as e:
        flash(f'Errore durante l\'aggiunta del versamento: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for(nome_conto.lower()))

@app.route('/elimina_versamento/<int:versamento_id>')
def elimina_versamento(versamento_id):
    """Elimina un versamento e ripristina il saldo"""
    try:
        versamento = VersamentoPersonale.query.get_or_404(versamento_id)
        conto = versamento.conto
        nome_conto = conto.nome_conto
        
        # Ripristina il saldo
        conto.saldo_corrente += versamento.importo
        
        # Elimina il versamento
        db.session.delete(versamento)
        db.session.commit()
        
        flash(f'Versamento eliminato e saldo ripristinato!', 'success')
        
    except Exception as e:
        flash(f'Errore durante l\'eliminazione: {str(e)}', 'error')
        db.session.rollback()
        nome_conto = 'maurizio'  # fallback
    
    return redirect(url_for(nome_conto.lower()))

@app.route('/reset_conto/<nome_conto>')
def reset_conto(nome_conto):
    """Reset del conto al saldo iniziale"""
    try:
        conto = ContoPersonale.query.filter_by(nome_conto=nome_conto).first()
        if conto:
            # Elimina tutti i versamenti
            VersamentoPersonale.query.filter_by(conto_id=conto.id).delete()
            
            # Ripristina il saldo iniziale
            conto.saldo_corrente = conto.saldo_iniziale
            
            db.session.commit()
            flash(f'Conto di {nome_conto} resettato al saldo iniziale!', 'success')
        else:
            flash('Conto non trovato!', 'error')
            
    except Exception as e:
        flash(f'Errore durante il reset: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for(nome_conto.lower()))

@app.route('/aggiorna_saldo_iniziale/<nome_conto>', methods=['POST'])
def aggiorna_saldo_iniziale(nome_conto):
    """Aggiorna il saldo iniziale del conto"""
    try:
        conto = ContoPersonale.query.filter_by(nome_conto=nome_conto).first()
        if not conto:
            flash('Conto non trovato!', 'error')
            return redirect(url_for(nome_conto.lower()))
        
        nuovo_saldo_iniziale = float(request.form['nuovo_saldo_iniziale'])
        
        if nuovo_saldo_iniziale <= 0:
            flash('Il saldo iniziale deve essere positivo!', 'error')
            return redirect(url_for(nome_conto.lower()))
        
        # Calcola la differenza
        differenza = nuovo_saldo_iniziale - conto.saldo_iniziale
        
        # Aggiorna sia il saldo iniziale che quello corrente
        conto.saldo_iniziale = nuovo_saldo_iniziale
        conto.saldo_corrente += differenza
        
        db.session.commit()
        
        if differenza > 0:
            flash(f'Saldo iniziale aumentato di {app.config["CONTO_PERSONALE_FORMATO_VALUTA"].format(differenza)}. '
                  f'Nuovo saldo corrente: {app.config["CONTO_PERSONALE_FORMATO_VALUTA"].format(conto.saldo_corrente)}', 'success')
        else:
            flash(f'Saldo iniziale ridotto di {app.config["CONTO_PERSONALE_FORMATO_VALUTA"].format(abs(differenza))}. '
                  f'Nuovo saldo corrente: {app.config["CONTO_PERSONALE_FORMATO_VALUTA"].format(conto.saldo_corrente)}', 'success')
        
    except ValueError:
        flash('Errore: inserire un valore numerico valido!', 'error')
    except Exception as e:
        flash(f'Errore durante l\'aggiornamento: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for(nome_conto.lower()))

# Routes per la gestione del garage auto

@app.route('/veicolo/<int:veicolo_id>')
def veicolo_dettaglio(veicolo_id):
    """Dettaglio di un veicolo specifico"""
    veicolo = Veicolo.query.get_or_404(veicolo_id)
    
    # Storia bolli
    bolli = BolloAuto.query.filter_by(veicolo_id=veicolo_id).order_by(BolloAuto.anno_riferimento.desc()).all()
    
    # Storia manutenzioni
    manutenzioni = ManutenzioneAuto.query.filter_by(veicolo_id=veicolo_id).order_by(ManutenzioneAuto.data_intervento.desc()).all()
    
    # Statistiche
    totale_bolli = sum(b.importo for b in bolli)
    totale_manutenzioni = sum(m.costo for m in manutenzioni)
    costo_totale = (veicolo.costo_finanziamento or 0) + totale_bolli + totale_manutenzioni
    
    return render_template('auto_dettaglio.html',
                         veicolo=veicolo,
                         bolli=bolli,
                         manutenzioni=manutenzioni,
                         totale_bolli=totale_bolli,
                         totale_manutenzioni=totale_manutenzioni,
                         costo_totale=costo_totale,
                         formato_valuta=app.config['FORMATO_VALUTA'])

@app.route('/aggiungi_veicolo', methods=['POST'])
def aggiungi_veicolo():
    """Aggiunge un nuovo veicolo al garage (versione semplificata)"""
    try:
        # Conversione del mese di scadenza bollo
        mese_scadenza = request.form.get('mese_scadenza_bollo')
        if mese_scadenza:
            mese_scadenza = int(mese_scadenza)
        
        # Conversione della prima rata
        prima_rata = None
        if request.form.get('prima_rata'):
            prima_rata = datetime.strptime(request.form['prima_rata'], '%Y-%m-%d').date()
        
        veicolo = Veicolo(
            marca=request.form['marca'].strip(),
            modello=request.form['modello'].strip(),
            mese_scadenza_bollo=mese_scadenza,
            costo_finanziamento=float(request.form['costo_finanziamento']) if request.form.get('costo_finanziamento') else None,
            prima_rata=prima_rata,
            numero_rate=int(request.form['numero_rate']) if request.form.get('numero_rate') else None,
            rata_mensile=float(request.form['rata_mensile']) if request.form.get('rata_mensile') else None
        )
        
        db.session.add(veicolo)
        db.session.commit()
        
        flash(f'Veicolo {veicolo.nome_completo} aggiunto con successo!', 'success')
        
    except Exception as e:
        flash(f'Errore nell\'aggiunta del veicolo: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('auto_garage'))

@app.route('/aggiorna_veicolo/<int:veicolo_id>', methods=['POST'])
def aggiorna_veicolo(veicolo_id):
    """Aggiorna i dati di un veicolo (versione semplificata)"""
    try:
        veicolo = Veicolo.query.get_or_404(veicolo_id)
        
        # Aggiorna solo i campi della struttura semplificata
        veicolo.marca = request.form['marca'].strip()
        veicolo.modello = request.form['modello'].strip()
        
        # Conversione del mese di scadenza bollo
        mese_scadenza = request.form.get('mese_scadenza_bollo')
        if mese_scadenza:
            veicolo.mese_scadenza_bollo = int(mese_scadenza)
        
        # Aggiorna dati finanziamento se presenti
        if request.form.get('costo_finanziamento'):
            veicolo.costo_finanziamento = float(request.form['costo_finanziamento'])
        
        if request.form.get('prima_rata'):
            veicolo.prima_rata = datetime.strptime(request.form['prima_rata'], '%Y-%m-%d').date()
        
        if request.form.get('numero_rate'):
            veicolo.numero_rate = int(request.form['numero_rate'])
        
        if request.form.get('rata_mensile'):
            veicolo.rata_mensile = float(request.form['rata_mensile'])
        
        db.session.commit()
        
        flash(f'Veicolo {veicolo.nome_completo} aggiornato con successo!', 'success')
        
    except Exception as e:
        flash(f'Errore nell\'aggiornamento del veicolo: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('veicolo_dettaglio', veicolo_id=veicolo_id))

@app.route('/aggiungi_bollo', methods=['POST'])
def aggiungi_bollo():
    """Aggiunge un pagamento del bollo auto (versione semplificata)"""
    try:
        bollo = BolloAuto(
            veicolo_id=int(request.form['veicolo_id']),
            anno_riferimento=int(request.form['anno_riferimento']),
            data_pagamento=datetime.strptime(request.form['data_pagamento'], '%Y-%m-%d').date(),
            importo=float(request.form['importo'])
        )
        
        db.session.add(bollo)
        db.session.commit()
        
        veicolo = Veicolo.query.get(bollo.veicolo_id)
        flash(f'Bollo per {veicolo.nome_completo} aggiunto con successo!', 'success')
        
        # Redirect al dettaglio del veicolo se specificato, altrimenti alla dashboard
        if request.form.get('redirect_to_veicolo'):
            return redirect(url_for('veicolo_dettaglio', veicolo_id=bollo.veicolo_id))
        
    except Exception as e:
        flash(f'Errore nell\'aggiunta del bollo: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('auto_garage'))

@app.route('/aggiungi_manutenzione', methods=['POST'])
def aggiungi_manutenzione():
    """Aggiunge un intervento di manutenzione (versione semplificata)"""
    try:
        veicolo_id = int(request.form['veicolo_id'])
        
        manutenzione = ManutenzioneAuto(
            veicolo_id=veicolo_id,
            data_intervento=datetime.strptime(request.form['data_intervento'], '%Y-%m-%d').date(),
            tipo_intervento=request.form['tipo_intervento'].strip(),
            descrizione=request.form.get('descrizione', '').strip(),
            costo=float(request.form['costo']),
            km_intervento=int(request.form['km_intervento']) if request.form.get('km_intervento') else None,
            officina=request.form.get('officina', '').strip()
        )
        
        db.session.add(manutenzione)
        db.session.commit()
        
        veicolo = Veicolo.query.get(veicolo_id)
        flash(f'Manutenzione per {veicolo.nome_completo} aggiunta con successo!', 'success')
        
        # Redirect al dettaglio del veicolo se specificato, altrimenti alla dashboard
        if request.form.get('redirect_to_veicolo'):
            return redirect(url_for('veicolo_dettaglio', veicolo_id=veicolo_id))
        
    except Exception as e:
        flash(f'Errore nell\'aggiunta della manutenzione: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('auto_garage'))

@app.route('/elimina_veicolo/<int:veicolo_id>', methods=['POST'])
def elimina_veicolo(veicolo_id):
    """Elimina definitivamente un veicolo e tutti i suoi dati associati"""
    try:
        veicolo = Veicolo.query.get_or_404(veicolo_id)
        nome_completo = veicolo.nome_completo
        
        # Elimina tutti i bolli associati
        BolloAuto.query.filter_by(veicolo_id=veicolo_id).delete()
        
        # Elimina tutte le manutenzioni associate
        ManutenzioneAuto.query.filter_by(veicolo_id=veicolo_id).delete()
        
        # Elimina il veicolo
        db.session.delete(veicolo)
        db.session.commit()
        
        flash(f'Veicolo {nome_completo} eliminato definitivamente dal garage!', 'success')
        
    except Exception as e:
        flash(f'Errore nella rimozione del veicolo: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('auto_garage'))

# Route PostePay Evolution (settembre 2025)
@app.route('/ppay_evolution')
def ppay_evolution():
    """Dashboard PostePay Evolution"""
    try:
        # Inizializza il sistema PostePay se necessario
        inizializza_postepay()
        
        # Recupera dati
        postepay = PostePayEvolution.query.first()
        abbonamenti = AbbonamentoPostePay.query.order_by(AbbonamentoPostePay.nome).all()
        movimenti = MovimentoPostePay.query.order_by(MovimentoPostePay.data.desc()).limit(10).all()
        
        # Calcola statistiche
        abbonamenti_attivi = [a for a in abbonamenti if a.attivo]
        spesa_mensile = sum(a.importo for a in abbonamenti_attivi)
        
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
        
        # Controllo saldo insufficiente per prossimi addebiti
        saldo_corrente = postepay.saldo_attuale if postepay else 0
        addebiti_problematici = []
        
        for addebito in prossimi_addebiti:
            if saldo_corrente < addebito['abbonamento'].importo:
                addebiti_problematici.append({
                    'abbonamento': addebito['abbonamento'],
                    'data': addebito['data'],
                    'giorni': addebito['giorni'],
                    'importo_mancante': addebito['abbonamento'].importo - saldo_corrente,
                    'saldo_attuale': saldo_corrente
                })
            else:
                saldo_corrente -= addebito['abbonamento'].importo
        
        return render_template('ppay_evolution.html',
                             postepay=postepay,
                             abbonamenti=abbonamenti,
                             movimenti=movimenti,
                             spesa_mensile=spesa_mensile,
                             prossimi_addebiti=prossimi_addebiti,
                             abbonamenti_attivi=abbonamenti_attivi,
                             addebiti_problematici=addebiti_problematici)
                             
    except Exception as e:
        flash(f'Errore nel caricamento PostePay Evolution: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/aggiungi_abbonamento_postepay', methods=['POST'])
def aggiungi_abbonamento_postepay():
    """Aggiunge un nuovo abbonamento PostePay"""
    try:
        abbonamento = AbbonamentoPostePay(
            nome=request.form['nome'],
            descrizione=request.form.get('descrizione', ''),
            importo=float(request.form['importo']),
            giorno_addebito=int(request.form['giorno_addebito']),
            attivo=True
        )
        
        db.session.add(abbonamento)
        db.session.commit()
        
        flash(f'Abbonamento {abbonamento.nome} aggiunto con successo!', 'success')
        
    except Exception as e:
        flash(f'Errore nell\'aggiunta dell\'abbonamento: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay_evolution'))

@app.route('/modifica_abbonamento_postepay/<int:abbonamento_id>', methods=['POST'])
def modifica_abbonamento_postepay(abbonamento_id):
    """Modifica un abbonamento PostePay esistente"""
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
    
    return redirect(url_for('ppay_evolution'))

@app.route('/toggle_abbonamento_postepay/<int:abbonamento_id>', methods=['POST'])
def toggle_abbonamento_postepay(abbonamento_id):
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
        flash(f'Errore nel cambio stato abbonamento: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay_evolution'))

@app.route('/elimina_abbonamento_postepay/<int:abbonamento_id>', methods=['POST'])
def elimina_abbonamento_postepay(abbonamento_id):
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
    
    return redirect(url_for('ppay_evolution'))

@app.route('/aggiungi_movimento_postepay', methods=['POST'])
def aggiungi_movimento_postepay():
    """Aggiunge un movimento PostePay manuale"""
    try:
        importo = float(request.form['importo'])
        tipo = request.form['tipo']
        
        # Se è un'uscita, rendi l'importo negativo
        if tipo == 'uscita':
            importo = -abs(importo)
        else:
            importo = abs(importo)
        
        movimento = MovimentoPostePay(
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
            descrizione=request.form['descrizione'],
            importo=importo,
            tipo=request.form['tipo_movimento']
        )
        
        db.session.add(movimento)
        
        # Aggiorna saldo PostePay
        postepay = PostePayEvolution.query.first()
        if postepay:
            postepay.saldo_attuale += importo
            postepay.data_ultimo_aggiornamento = datetime.utcnow()
        
        db.session.commit()
        
        flash('Movimento aggiunto con successo!', 'success')
        
    except Exception as e:
        flash(f'Errore nell\'aggiunta del movimento: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay_evolution'))

@app.route('/modifica_saldo_postepay', methods=['POST'])
def modifica_saldo_postepay():
    """Modifica il saldo PostePay Evolution"""
    try:
        nuovo_saldo = float(request.form['nuovo_saldo'])
        motivo = request.form.get('motivo', 'Modifica manuale saldo')
        
        postepay = PostePayEvolution.query.first()
        if not postepay:
            flash('Errore: Sistema PostePay non inizializzato!', 'error')
            return redirect(url_for('ppay_evolution'))
        
        # Calcola la differenza per il movimento
        saldo_precedente = postepay.saldo_attuale
        differenza = nuovo_saldo - saldo_precedente
        
        # Aggiorna il saldo
        postepay.saldo_attuale = nuovo_saldo
        postepay.data_ultimo_aggiornamento = datetime.utcnow()
        
        # Crea un movimento per tracciare la modifica
        if differenza != 0:
            movimento = MovimentoPostePay(
                data=date.today(),
                descrizione=f"{motivo} (da €{saldo_precedente:.2f} a €{nuovo_saldo:.2f})",
                importo=differenza,
                tipo='correzione'
            )
            db.session.add(movimento)
        
        db.session.commit()
        
        if differenza > 0:
            flash(f'Saldo aggiornato! Aggiunta di €{differenza:.2f}', 'success')
        elif differenza < 0:
            flash(f'Saldo aggiornato! Riduzione di €{abs(differenza):.2f}', 'success')
        else:
            flash('Saldo confermato (nessuna modifica)', 'info')
        
    except Exception as e:
        flash(f'Errore nella modifica del saldo: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay_evolution'))

@app.route('/reset_postepay', methods=['POST'])
def reset_postepay():
    """Reset completo sistema PostePay Evolution"""
    try:
        # Elimina tutti i dati
        MovimentoPostePay.query.delete()
        AbbonamentoPostePay.query.delete()
        PostePayEvolution.query.delete()
        
        db.session.commit()
        
        # Reinizializza
        inizializza_postepay()
        
        flash('Sistema PostePay Evolution resettato e reinizializzato!', 'success')
        
    except Exception as e:
        flash(f'Errore nel reset PostePay: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('ppay_evolution'))

def inizializza_postepay():
    """Inizializza il sistema PostePay Evolution con dati predefiniti"""
    try:
        # Controlla se esiste già
        if PostePayEvolution.query.first():
            return
        
        # Crea saldo iniziale
        postepay = PostePayEvolution(
            saldo_attuale=app.config['POSTEPAY_SALDO_INIZIALE']
        )
        db.session.add(postepay)
        
        # Crea abbonamenti predefiniti
        for abbonamento_config in app.config['POSTEPAY_ABBONAMENTI_DEFAULT']:
            abbonamento = AbbonamentoPostePay(
                nome=abbonamento_config['nome'],
                descrizione=abbonamento_config['descrizione'],
                importo=abbonamento_config['importo'],
                giorno_addebito=abbonamento_config['giorno_addebito'],
                attivo=abbonamento_config['attivo']
            )
            db.session.add(abbonamento)
        
        # Movimento iniziale di ricarica
        movimento_iniziale = MovimentoPostePay(
            data=date.today(),
            descrizione='Saldo iniziale PostePay Evolution',
            importo=app.config['POSTEPAY_SALDO_INIZIALE'],
            tipo='ricarica'
        )
        db.session.add(movimento_iniziale)
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        raise e

# Routes per gestione appunti
@app.route('/appunti')
def appunti():
    """Visualizza tutti gli appunti"""
    try:
        # Debug: conta appunti
        count = Appunto.query.count()
        print(f"DEBUG: Trovati {count} appunti nel database")
        
        # Ordina gli appunti per data creazione (più recenti prima)
        appunti = Appunto.query.order_by(
            Appunto.data_creazione.desc()
        ).all()
        
        print(f"DEBUG: Query restituisce {len(appunti)} appunti")
        for a in appunti:
            print(f"DEBUG: Appunto - {a.titolo}: {a.importo_stimato}")
        
        categorie = Categoria.query.filter(Categoria.nome != 'PayPal').all()
        print(f"DEBUG: Trovate {len(categorie)} categorie")
        
        return render_template('appunti.html', appunti=appunti, categorie=categorie)
    except Exception as e:
        print(f"DEBUG: Errore nella route appunti: {e}")
        import traceback
        traceback.print_exc()
        return f"Errore: {e}", 500

@app.route('/appunti/nuovo', methods=['POST'])
def nuovo_appunto():
    """Crea un nuovo appunto"""
    try:
        titolo = request.form['titolo']
        tipo = request.form.get('tipo', 'uscita')
        importo_stimato = float(request.form['importo_stimato']) if request.form.get('importo_stimato') else None
        categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        note = request.form.get('note', '')
        
        appunto = Appunto(
            titolo=titolo,
            tipo=tipo,
            importo_stimato=importo_stimato,
            categoria_id=categoria_id,
            note=note
        )
        
        db.session.add(appunto)
        db.session.commit()
        
        flash(f'Appunto "{titolo}" aggiunto con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'aggiunta dell\'appunto: {str(e)}', 'error')
    
    return redirect(url_for('appunti'))

@app.route('/appunti/<int:id>/modifica', methods=['POST'])
def modifica_appunto(id):
    """Modifica un appunto esistente"""
    appunto = Appunto.query.get_or_404(id)
    
    try:
        if 'titolo' in request.form:
            appunto.titolo = request.form['titolo']
        if 'tipo' in request.form:
            appunto.tipo = request.form['tipo']
        if 'importo_stimato' in request.form:
            appunto.importo_stimato = float(request.form['importo_stimato']) if request.form['importo_stimato'] else None
        if 'categoria_id' in request.form:
            appunto.categoria_id = int(request.form['categoria_id']) if request.form['categoria_id'] else None
        if 'note' in request.form:
            appunto.note = request.form['note']
        
        db.session.commit()
        flash(f'Appunto "{appunto.titolo}" modificato con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la modifica dell\'appunto: {str(e)}', 'error')
    
    return redirect(url_for('appunti'))

@app.route('/appunti/<int:id>/completa', methods=['POST'])
def completa_appunto(id):
    """Segna un appunto come completato"""
    appunto = Appunto.query.get_or_404(id)
    
    try:
        appunto.completato = True
        db.session.commit()
        flash(f'Appunto "{appunto.titolo}" segnato come completato!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante il completamento dell\'appunto: {str(e)}', 'error')
    
    return redirect(url_for('appunti'))

@app.route('/appunti/<int:id>/riapri', methods=['POST'])
def riapri_appunto(id):
    """Riapre un appunto completato"""
    appunto = Appunto.query.get_or_404(id)
    
    try:
        appunto.completato = False
        db.session.commit()
        flash(f'Appunto "{appunto.titolo}" riaperto!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la riapertura dell\'appunto: {str(e)}', 'error')
    
    return redirect(url_for('appunti'))

@app.route('/appunti/elimina/<int:id>', methods=['POST'])
def elimina_appunto(id):
    """Elimina un appunto"""
    appunto = Appunto.query.get_or_404(id)
    titolo = appunto.titolo
    
    try:
        db.session.delete(appunto)
        db.session.commit()
        return jsonify({'success': True, 'message': f'Appunto "{titolo}" eliminato con successo!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Errore durante l\'eliminazione: {str(e)}'}), 500

@app.route('/appunti/trasferisci', methods=['POST'])
def trasferisci_appunto():
    """Trasferisce un appunto nelle transazioni mensili e lo elimina"""
    try:
        appunto_id = int(request.form['appunto_id'])
        data_transazione = datetime.strptime(request.form['data_transazione'], '%Y-%m-%d').date()
        
        # Recupera l'appunto
        appunto = Appunto.query.get_or_404(appunto_id)
        
        # Crea la transazione usando i dati dell'appunto
        transazione = Transazione(
            data=data_transazione,
            data_effettiva=data_transazione if data_transazione <= datetime.now().date() else None,
            descrizione=appunto.titolo,
            importo=appunto.importo_stimato or 0.0,
            categoria_id=appunto.categoria_id,
            tipo=appunto.tipo
        )
        
        # Salva la transazione
        db.session.add(transazione)
        
        # Elimina l'appunto
        db.session.delete(appunto)
        
        db.session.commit()
        
        flash(f'Appunto "{appunto.titolo}" trasferito con successo nelle transazioni!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante il trasferimento: {str(e)}', 'error')
    
    return redirect(url_for('appunti'))

@app.route('/appunti/<int:id>/dati')
def dati_appunto(id):
    """Restituisce i dati di un appunto in formato JSON"""
    try:
        appunto = Appunto.query.get_or_404(id)
        return jsonify({
            'success': True,
            'appunto': {
                'id': appunto.id,
                'titolo': appunto.titolo,
                'tipo': appunto.tipo,
                'importo_stimato': appunto.importo_stimato,
                'categoria_id': appunto.categoria_id,
                'note': appunto.note
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/appunti/modifica', methods=['POST'])
def modifica_appunto_form():
    """Modifica un appunto tramite form"""
    try:
        appunto_id = int(request.form['appunto_id'])
        appunto = Appunto.query.get_or_404(appunto_id)
        
        # Aggiorna i campi
        appunto.titolo = request.form['titolo']
        appunto.tipo = request.form.get('tipo', 'uscita')
        appunto.importo_stimato = float(request.form['importo_stimato']) if request.form.get('importo_stimato') else None
        appunto.categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        appunto.note = request.form.get('note', '')
        appunto.data_aggiornamento = datetime.utcnow()
        
        db.session.commit()
        flash(f'Appunto "{appunto.titolo}" modificato con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la modifica: {str(e)}', 'error')
    
    return redirect(url_for('appunti'))

@app.route('/appunti/<int:id>/converti', methods=['POST'])
def converti_appunto_transazione(id):
    """Converte un appunto in una transazione reale"""
    appunto = Appunto.query.get_or_404(id)
    
    try:
        data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        importo = float(request.form['importo'])
        descrizione = request.form.get('descrizione', appunto.titolo)
        
        # Crea la transazione
        transazione = Transazione(
            data=data,
            data_effettiva=data if data <= datetime.now().date() else None,
            descrizione=descrizione,
            importo=importo,
            categoria_id=appunto.categoria_id or int(request.form['categoria_id']),
            tipo='uscita',  # Assumiamo che sia una spesa
            ricorrente=False
        )
        
        db.session.add(transazione)
        db.session.flush()  # Per ottenere l'ID della transazione
        
        # Segna l'appunto come completato
        appunto.completato = True
        
        db.session.commit()
        
        # Gestione automatica del budget se necessario
        # (La logica esistente nella funzione aggiungi_transazione si applicherà automaticamente)
        
        flash(f'Appunto "{appunto.titolo}" convertito in transazione con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la conversione dell\'appunto: {str(e)}', 'error')
    
    return redirect(url_for('appunti'))

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(
        host=app.config['HOST'], 
        port=app.config['PORT'], 
        debug=app.config['DEBUG']
    )
