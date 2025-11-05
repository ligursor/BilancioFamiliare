"""Modelli per la gestione del garage auto"""
from app import db
from datetime import datetime, date
import calendar

class Veicoli(db.Model):
    """Modello per i veicoli nel garage"""
    __tablename__ = 'veicoli'
    
    id = db.Column(db.Integer, primary_key=True)
    modello = db.Column(db.String(100), nullable=False)
    # Tipo di veicolo: 'auto', 'moto', 'bici' - usiamo stringa per semplicità
    tipo = db.Column(db.String(20), nullable=False, default='auto')

    mese_scadenza_bollo = db.Column(db.Integer, nullable=True)  # 1-12 (gennaio-dicembre); solo per auto/moto

    # I campi di finanziamento sono opzionali: non tutti i veicoli hanno un finanziamento
    costo_finanziamento = db.Column(db.Float, nullable=True)
    prima_rata = db.Column(db.Date, nullable=True)
    numero_rate = db.Column(db.Integer, nullable=True)
    rata_mensile = db.Column(db.Float, nullable=True)
    # 'marca' field removed by request — use only 'modello' as display name
    
    @property
    def totale_versato(self):
        """Calcola il totale versato in base alla data odierna e alla prima rata"""
        oggi = date.today()
        # Se non c'è finanziamento dichiarato, nessun versamento
        if not self.prima_rata or not self.numero_rate or not self.rata_mensile:
            return 0.0

        if oggi < self.prima_rata:
            return 0.0

        # Calcola quanti mesi sono passati dalla prima rata
        mesi_trascorsi = (oggi.year - self.prima_rata.year) * 12 + (oggi.month - self.prima_rata.month)

        # Se siamo oltre il giorno della rata nel mese corrente, conta anche questo mese
        if oggi.day >= self.prima_rata.day:
            mesi_trascorsi += 1

        # Non può superare il numero totale di rate
        rate_pagate = min(mesi_trascorsi, self.numero_rate or 0)

        return max(0, rate_pagate * (self.rata_mensile or 0))
    
    @property
    def rate_rimanenti(self):
        """Calcola le rate rimanenti"""
        oggi = date.today()
        # Se non c'è finanziamento dichiarato, non ci sono rate
        if not self.prima_rata or not self.numero_rate or not self.rata_mensile:
            return 0

        if oggi < self.prima_rata:
            return self.numero_rate

        # Calcola quanti mesi sono passati dalla prima rata
        mesi_trascorsi = (oggi.year - self.prima_rata.year) * 12 + (oggi.month - self.prima_rata.month)

        # Se siamo oltre il giorno della rata nel mese corrente, conta anche questo mese
        if oggi.day >= self.prima_rata.day:
            mesi_trascorsi += 1

        rate_pagate = min(mesi_trascorsi, self.numero_rate or 0)
        return max(0, (self.numero_rate or 0) - rate_pagate)
    
    @property
    def saldo_rimanente(self):
        """Calcola il saldo rimanente"""
        return max(0, (self.costo_finanziamento or 0) - self.totale_versato)
    
    @property
    def nome_completo(self):
        """Restituisce nome completo del veicoli"""
        # Prima era 'marca + modello'. Dopo la rimozione del campo 'marca' mostriamo solo il modello
        return f"{self.modello}"

    @property
    def bollo_scaduto(self):
        """Indica se esiste un bollo non pagato per l'anno corrente."""
        try:
            current_year = date.today().year
            # AutoBolli è definito più sotto nel file; la query viene eseguita a runtime
            unpaid = AutoBolli.query.filter_by(veicolo_id=self.id, anno_riferimento=current_year).filter(AutoBolli.data_pagamento.is_(None)).first()
            return bool(unpaid)
        except Exception:
            # In caso di problemi (es. sessione non inizializzata), consideriamo non scaduto
            return False
    
    def __repr__(self):
        return f'<Veicoli {self.nome_completo}>'

class AutoBolli(db.Model):
    """Modello per i pagamenti del bollo auto"""
    # Renamed table to follow new naming convention
    __tablename__ = 'auto_bolli'

    # Use autoincrement=False to avoid creating an AUTOINCREMENT sqlite sequence
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    veicolo_id = db.Column(db.Integer, db.ForeignKey('veicoli.id'), nullable=False)
    veicolo = db.relationship('Veicoli', backref=db.backref('bolli', lazy=True, cascade='all, delete-orphan'))
    anno_riferimento = db.Column(db.Integer, nullable=False)
    importo = db.Column(db.Float, nullable=False)
    data_pagamento = db.Column(db.Date, nullable=False)
    # data_creazione removed — not needed for bolli records
    
    def __repr__(self):
        return f'<AutoBolli {self.veicolo.nome_completo} {self.anno_riferimento}: {self.importo}>'

class AutoManutenzioni(db.Model):
    """Modello per gli interventi di manutenzione"""
    # Renamed table to follow new naming convention
    __tablename__ = 'auto_manutenzioni'

    # Use autoincrement=False to avoid creating an AUTOINCREMENT sqlite sequence
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    veicolo_id = db.Column(db.Integer, db.ForeignKey('veicoli.id'), nullable=False)
    veicolo = db.relationship('Veicoli', backref=db.backref('manutenzioni', lazy=True, cascade='all, delete-orphan'))
    data_intervento = db.Column(db.Date, nullable=False)
    tipo_intervento = db.Column(db.String(200), nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    costo = db.Column(db.Float, nullable=False)
    km_intervento = db.Column(db.Integer, nullable=True)
    officina = db.Column(db.String(200), nullable=True)
    # data_creazione removed — not needed for manutenzioni records
    
    def __repr__(self):
        return f'<AutoManutenzioni {self.veicolo.nome_completo} - {self.tipo_intervento}: {self.costo}>'


class Assicurazioni(db.Model):
    """Modello per i pagamenti assicurativi (solo per auto e moto)"""
    __tablename__ = 'assicurazioni'

    # allow the database to assign autoincrementing ids
    id = db.Column(db.Integer, primary_key=True)
    veicolo_id = db.Column(db.Integer, db.ForeignKey('veicoli.id'), nullable=False)
    veicolo = db.relationship('Veicoli', backref=db.backref('assicurazioni', lazy=True, cascade='all, delete-orphan'))
    anno_riferimento = db.Column(db.Integer, nullable=False)
    importo = db.Column(db.Float, nullable=False)
    compagnia = db.Column(db.String(200), nullable=True)
    data_pagamento = db.Column(db.Date, nullable=False)
    # data_creazione removed — not needed for assicurazioni records

    def __repr__(self):
        return f'<Assicurazioni {self.veicolo.nome_completo} {self.anno_riferimento}: {self.importo}>'
