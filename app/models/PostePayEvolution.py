"""
Modelli per PostePay Evolution
"""
from app import db
from datetime import datetime, date
import calendar

class PostePayEvolution(db.Model):
    """Modello per il saldo PostePay Evolution"""
    __tablename__ = 'poste_pay_evolution'
    
    id = db.Column(db.Integer, primary_key=True)
    saldo_attuale = db.Column(db.Float, nullable=False, default=0.0)
    data_ultimo_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PostePayEvolution saldo: {self.saldo_attuale}>'

class AbbonamentoPostePay(db.Model):
    """Modello per gli abbonamenti PostePay Evolution"""
    # Renamed table to use 'ppay_evolution_abbonamenti' for clarity
    __tablename__ = 'ppay_evolution_abbonamenti'
    
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
            ultimo_giorno = calendar.monthrange(prossimo_anno, prossimo_mese)[1]
            return date(prossimo_anno, prossimo_mese, min(self.giorno_addebito, ultimo_giorno))
    
    def __repr__(self):
        return f'<AbbonamentoPostePay {self.nome}: {self.importo}>'

class MovimentoPostePay(db.Model):
    """Modello per i movimenti PostePay Evolution"""
    # Renamed to match new naming convention
    __tablename__ = 'ppay_evolution_movimenti'
    
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    descrizione = db.Column(db.String(200), nullable=False)
    importo = db.Column(db.Float, nullable=False)  # Positivo per entrate, negativo per uscite
    tipo = db.Column(db.String(50), nullable=False)  # 'ricarica', 'abbonamento', 'altro'
    # FK updated to match renamed abbonamenti table
    abbonamento_id = db.Column(db.Integer, db.ForeignKey('ppay_evolution_abbonamenti.id'), nullable=True)
    abbonamento = db.relationship('AbbonamentoPostePay', backref=db.backref('movimenti', lazy=True))
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<MovimentoPostePay {self.descrizione}: {self.importo}>'
    
    def __repr__(self):
        return f'<MovimentoPostePay {self.descrizione}: {self.importo}>'


class DeletedGeneration(db.Model):
    """Tombstone for automatically generated movements that were manually deleted.

    This prevents the auto-generation logic from immediately recreating a
    movement for the same abbonamento in the same month/year.
    """
    __tablename__ = 'ppay_deleted_generations'

    id = db.Column(db.Integer, primary_key=True)
    abbonamento_id = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<DeletedGeneration abbonamento={self.abbonamento_id} {self.month}/{self.year}>'
