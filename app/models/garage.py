"""
Modelli per la gestione del garage auto
"""
from app import db
from datetime import datetime, date
import calendar

class Veicolo(db.Model):
    """Modello per i veicoli nel garage"""
    __tablename__ = 'veicolo'
    
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
    def giorni_alla_scadenza_bollo(self):
        """Calcola i giorni alla prossima scadenza bollo"""
        oggi = date.today()
        
        # Data di scadenza per l'anno corrente (ultimo giorno del mese di scadenza)
        ultimo_giorno = calendar.monthrange(oggi.year, self.mese_scadenza_bollo)[1]
        data_scadenza = date(oggi.year, self.mese_scadenza_bollo, ultimo_giorno)
        
        return (data_scadenza - oggi).days
    
    def __repr__(self):
        return f'<Veicolo {self.nome_completo}>'

class BolloAuto(db.Model):
    """Modello per i pagamenti del bollo auto"""
    __tablename__ = 'bollo_auto'
    
    id = db.Column(db.Integer, primary_key=True)
    veicolo_id = db.Column(db.Integer, db.ForeignKey('veicolo.id'), nullable=False)
    veicolo = db.relationship('Veicolo', backref=db.backref('bolli', lazy=True, cascade='all, delete-orphan'))
    anno_riferimento = db.Column(db.Integer, nullable=False)
    importo = db.Column(db.Float, nullable=False)
    data_pagamento = db.Column(db.Date, nullable=False)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<BolloAuto {self.veicolo.nome_completo} {self.anno_riferimento}: {self.importo}>'

class ManutenzioneAuto(db.Model):
    """Modello per gli interventi di manutenzione"""
    __tablename__ = 'manutenzione_auto'
    
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
    
    def __repr__(self):
        return f'<ManutenzioneAuto {self.veicolo.nome_completo} - {self.tipo_intervento}: {self.costo}>'
