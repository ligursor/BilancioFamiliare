"""
Modelli per i conti personali
"""
from app import db
from datetime import datetime, date

class ContoPersonale(db.Model):
    """Modello per i conti personali di Maurizio e Antonietta"""
    __tablename__ = 'conto_personale'
    
    id = db.Column(db.Integer, primary_key=True)
    nome_conto = db.Column(db.String(50), nullable=False)  # 'Maurizio' o 'Antonietta'
    # I saldi sono delegati alla tabella `strumento` (sorgente di verità).
    # Manteniamo comunque i campi storici per retrocompatibilità fino alla migrazione completa.
    # Rimosso: saldo_iniziale, saldo_corrente (ora gestiti da Strumento).
    # FK verso la tabella `conti_finanziari` per collegare il conto personale al record strumento
    id_strumento = db.Column(db.Integer, db.ForeignKey('conti_finanziari.id_conto'), nullable=True)
    # relazione per accedere allo strumento associato (lazy loading)
    strumento = db.relationship('Strumento', backref=db.backref('conti_personali', lazy=True))
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_aggiornamento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        if self.strumento:
            return f'<ContoPersonale {self.nome_conto}: {self.strumento.saldo_corrente}>'
        return f'<ContoPersonale {self.nome_conto} (no strumento)>'


class ContoPersonaleMovimento(db.Model):
    """Movimenti (ex-versamenti) sui conti personali.

    Nota: questa tabella sostituisce `versamento_personale`.
    Campo `saldo_dopo_versamento` rimosso: il saldo corrente viene calcolato aggregando
    `importo` su tutti i movimenti e applicandolo allo `strumento` (sorgente di verità).
    """
    __tablename__ = 'conto_personale_movimenti'
    
    id = db.Column(db.Integer, primary_key=True)
    conto_id = db.Column(db.Integer, db.ForeignKey('conto_personale.id'), nullable=False)
    # Manteniamo il backref 'versamenti' per compatibilità con templates esistenti
    conto = db.relationship('ContoPersonale', backref=db.backref('versamenti', lazy=True, cascade='all, delete-orphan'))
    data = db.Column(db.Date, nullable=False, default=datetime.now().date)
    descrizione = db.Column(db.String(200), nullable=False)
    importo = db.Column(db.Float, nullable=False)
    data_inserimento = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ContoPersonaleMovimento {self.conto.nome_conto}: {self.importo}>"

# SQLAlchemy event listeners to keep `strumento.saldo_corrente` in sync with movimenti
from sqlalchemy import event, text


def _recompute_and_update_strumento(connection, conto_id):
    """Ricalcola il saldo corrente per il conto `conto_id` e aggiorna la tabella `strumento`.

    Formula: nuovo_saldo = saldo_iniziale (da strumento) - sum(importo dei movimenti)
    """
    # Recupera id_strumento per il conto
    row = connection.execute(text("SELECT id_strumento FROM conto_personale WHERE id = :cid"), {'cid': conto_id}).fetchone()
    if not row:
        return
    id_str = row[0]
    if not id_str:
        return

    # Somma degli importi (tutti positivi)
    total = connection.execute(text("SELECT coalesce(sum(importo),0) FROM conto_personale_movimenti WHERE conto_id = :cid"), {'cid': conto_id}).scalar() or 0.0
    saldo_iniziale = connection.execute(text("SELECT saldo_iniziale FROM conti_finanziari WHERE id_conto = :id"), {'id': id_str}).scalar() or 0.0
    nuovo = float(saldo_iniziale) - float(total)
    connection.execute(text("UPDATE conti_finanziari SET saldo_corrente = :s WHERE id_conto = :id"), {'s': nuovo, 'id': id_str})


@event.listens_for(ContoPersonaleMovimento, 'after_insert')
def _after_insert_movimento(mapper, connection, target):
    try:
        _recompute_and_update_strumento(connection, target.conto_id)
    except Exception:
        # non vogliamo fallire l'operazione principale per problemi di sincronizzazione
        pass


@event.listens_for(ContoPersonaleMovimento, 'after_delete')
def _after_delete_movimento(mapper, connection, target):
    try:
        _recompute_and_update_strumento(connection, target.conto_id)
    except Exception:
        pass


@event.listens_for(ContoPersonaleMovimento, 'after_update')
def _after_update_movimento(mapper, connection, target):
    try:
        _recompute_and_update_strumento(connection, target.conto_id)
    except Exception:
        pass
