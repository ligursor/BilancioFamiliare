"""Service per la gestione degli strumenti (conti, carte, ecc.)

Fornisce operazioni minime: recupero, creazione se mancante e aggiornamento saldo.
"""
from app import db
from app.models.ContiFinanziari import Strumento
from sqlalchemy.exc import SQLAlchemyError


class StrumentiService:
    """Service semplice per la tabella `strumento`."""

    def get_all(self):
        return db.session.query(Strumento).order_by(Strumento.descrizione).all()

    def get_by_descrizione(self, descrizione):
        return db.session.query(Strumento).filter(Strumento.descrizione == descrizione).first()

    def get_by_id(self, id_conto):
        return db.session.query(Strumento).filter(Strumento.id_conto == id_conto).first()

    def ensure_strumento(self, descrizione, tipologia, saldo_iniziale=0.0):
        """Crea lo strumento se non esiste e ritorna l'istanza."""
        try:
            s = self.get_by_descrizione(descrizione)
            if s:
                return s
            s = Strumento(descrizione=descrizione, tipologia=tipologia, saldo_iniziale=saldo_iniziale, saldo_corrente=saldo_iniziale)
            db.session.add(s)
            db.session.commit()
            return s
        except SQLAlchemyError:
            db.session.rollback()
            raise

    def update_saldo(self, descrizione, nuovo_saldo):
        """Aggiorna il saldo_corrente (e crea lo strumento se mancante)."""
        try:
            s = self.get_by_descrizione(descrizione)
            if not s:
                # non conosciamo la tipologia: usiamo 'conto' generico
                s = Strumento(descrizione=descrizione, tipologia='conto', saldo_iniziale=0.0, saldo_corrente=nuovo_saldo)
                db.session.add(s)
            else:
                s.saldo_corrente = nuovo_saldo
            db.session.commit()
            return s
        except SQLAlchemyError:
            db.session.rollback()
            raise

    def update_saldo_by_id(self, id_conto, nuovo_saldo):
        try:
            s = self.get_by_id(id_conto)
            if not s:
                s = Strumento(id_conto=id_conto, descrizione=f'Conto {id_conto}', tipologia='conto', saldo_iniziale=0.0, saldo_corrente=nuovo_saldo)
                db.session.add(s)
            else:
                s.saldo_corrente = nuovo_saldo
            db.session.commit()
            return s
        except SQLAlchemyError:
            db.session.rollback()
            raise

    def update_saldo_iniziale_by_id(self, id_conto, nuovo_saldo_iniziale):
        try:
            s = self.get_by_id(id_conto)
            if not s:
                s = Strumento(id_conto=id_conto, descrizione=f'Conto {id_conto}', tipologia='conto', saldo_iniziale=nuovo_saldo_iniziale, saldo_corrente=nuovo_saldo_iniziale)
                db.session.add(s)
            else:
                differenza = nuovo_saldo_iniziale - (s.saldo_iniziale or 0.0)
                s.saldo_iniziale = nuovo_saldo_iniziale
                s.saldo_corrente = (s.saldo_corrente or 0.0) + differenza
            db.session.commit()
            return s
        except SQLAlchemyError:
            db.session.rollback()
            raise
