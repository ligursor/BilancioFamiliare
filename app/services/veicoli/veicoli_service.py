"""Servizio per la gestione dei veicoli (auto, moto, bici, bolli, assicurazioni, manutenzioni)"""
from app.services import BaseService
from app.models.Veicoli import Veicoli, AutoBolli, AutoManutenzioni, Assicurazioni
from app import db
from datetime import date
from sqlalchemy import desc, and_


class VeicoliService(BaseService):
    """Servizio per la gestione dei veicoli e relative operazioni"""

    # === Gestione Veicoli ===

    def get_all_veicoli(self, solo_attivi=False):
        """Recupera tutti i veicoli, ordinati per marca/modello"""
        query = Veicoli.query
        if solo_attivi and hasattr(Veicoli, 'attivo'):
            query = query.filter(Veicoli.attivo == True)
        # Order by modello only
        return query.order_by(Veicoli.modello).all()

    def get_veicolo_by_id(self, veicolo_id):
        """Recupera un veicolo specifico"""
        return Veicoli.query.filter(Veicoli.id == veicolo_id).first()

    def create_veicolo(self, modello, tipo='auto', mese_scadenza_bollo=None,
                       costo_finanziamento=None, prima_rata=None, numero_rate=None, rata_mensile=None):
        """Crea un nuovo veicolo"""
        veicolo = Veicoli(
            modello=modello,
            tipo=tipo,
            mese_scadenza_bollo=mese_scadenza_bollo,
            costo_finanziamento=costo_finanziamento,
            prima_rata=prima_rata,
            numero_rate=numero_rate,
            rata_mensile=rata_mensile
        )
        db.session.add(veicolo)
        db.session.commit()
        return veicolo

    def update_veicolo(self, veicolo_id, **kwargs):
        """Aggiorna un veicolo"""
        veicolo = self.get_veicolo_by_id(veicolo_id)
        if not veicolo:
            return None

        for key, value in kwargs.items():
            if hasattr(veicolo, key):
                setattr(veicolo, key, value)

        db.session.commit()
        return veicolo

    def delete_veicolo(self, veicolo_id):
        """Elimina un veicolo (delete definitivo)"""
        veicolo = self.get_veicolo_by_id(veicolo_id)
        if not veicolo:
            return False

        db.session.delete(veicolo)
        db.session.commit()
        return True

    # === Gestione Bolli ===

    def get_bolli_by_veicolo(self, veicolo_id):
        """Recupera tutti i bolli per un veicolo"""
        return AutoBolli.query.filter(
            AutoBolli.veicolo_id == veicolo_id
        ).order_by(AutoBolli.anno_riferimento.desc()).all()

    def get_bollo_by_id(self, bollo_id):
        """Recupera un bollo specifico"""
        return AutoBolli.query.filter(AutoBolli.id == bollo_id).first()

    def create_bollo(self, veicolo_id, anno_riferimento, importo, data_pagamento=None):
        """Crea un nuovo bollo (anno_riferimento)"""
        bollo = AutoBolli(
            veicolo_id=veicolo_id,
            anno_riferimento=anno_riferimento,
            importo=importo,
            data_pagamento=data_pagamento
        )
        db.session.add(bollo)
        db.session.commit()
        return bollo

    def update_bollo(self, bollo_id, **kwargs):
        """Aggiorna un bollo"""
        bollo = self.get_bollo_by_id(bollo_id)
        if not bollo:
            return None

        for key, value in kwargs.items():
            if hasattr(bollo, key):
                setattr(bollo, key, value)

        db.session.commit()
        return bollo

    def delete_bollo(self, bollo_id):
        """Elimina un bollo"""
        bollo = self.get_bollo_by_id(bollo_id)
        if not bollo:
            return False

        db.session.delete(bollo)
        db.session.commit()
        return True

    def get_bolli_scaduti(self, data_riferimento=None):
        """Recupera bolli (per anno) senza pagamento fino all'anno di riferimento"""
        if data_riferimento is None:
            data_riferimento = date.today()

        current_year = data_riferimento.year
        return AutoBolli.query.filter(
            and_(
                AutoBolli.anno_riferimento <= current_year,
                AutoBolli.data_pagamento.is_(None)
            )
        ).all()

    # === Gestione Manutenzioni ===

    def get_manutenzioni_by_veicolo(self, veicolo_id):
        """Recupera tutte le manutenzioni per un veicolo"""
        return AutoManutenzioni.query.filter(
            AutoManutenzioni.veicolo_id == veicolo_id
        ).order_by(AutoManutenzioni.data_intervento.desc()).all()

    def get_manutenzione_by_id(self, manutenzione_id):
        """Recupera una manutenzione specifica"""
        return AutoManutenzioni.query.filter(AutoManutenzioni.id == manutenzione_id).first()

    def create_manutenzione(self, veicolo_id, data_intervento, tipo_intervento, descrizione=None,
                            costo=0.0, km_intervento=None, officina=None):
        """Crea una nuova manutenzione"""
        manutenzione = AutoManutenzioni(
            veicolo_id=veicolo_id,
            data_intervento=data_intervento,
            tipo_intervento=tipo_intervento,
            descrizione=descrizione,
            costo=costo,
            km_intervento=km_intervento,
            officina=officina
        )
        db.session.add(manutenzione)
        db.session.commit()
        return manutenzione

    def update_manutenzione(self, manutenzione_id, **kwargs):
        """Aggiorna una manutenzione"""
        manutenzione = self.get_manutenzione_by_id(manutenzione_id)
        if not manutenzione:
            return None

        for key, value in kwargs.items():
            if hasattr(manutenzione, key):
                setattr(manutenzione, key, value)

        db.session.commit()
        return manutenzione

    def delete_manutenzione(self, manutenzione_id):
        """Elimina una manutenzione"""
        manutenzione = self.get_manutenzione_by_id(manutenzione_id)
        if not manutenzione:
            return False

        db.session.delete(manutenzione)
        db.session.commit()
        return True

    # === Gestione Assicurazioni ===

    def get_assicurazioni_by_veicolo(self, veicolo_id):
        """Recupera tutte le assicurazioni per un veicolo"""
        return Assicurazioni.query.filter(
            Assicurazioni.veicolo_id == veicolo_id
        ).order_by(Assicurazioni.anno_riferimento.desc()).all()

    def get_assicurazione_by_id(self, assicurazione_id):
        return Assicurazioni.query.filter(Assicurazioni.id == assicurazione_id).first()

    def create_assicurazione(self, veicolo_id, anno_riferimento, importo, data_pagamento, compagnia=None):
        """Crea un record di assicurazione"""
        assicurazione = Assicurazioni(
            veicolo_id=veicolo_id,
            anno_riferimento=anno_riferimento,
            importo=importo,
            data_pagamento=data_pagamento,
            compagnia=compagnia,
        )
        db.session.add(assicurazione)
        db.session.commit()
        return assicurazione

    def update_assicurazione(self, assicurazione_id, **kwargs):
        assicurazione = self.get_assicurazione_by_id(assicurazione_id)
        if not assicurazione:
            return None
        for key, value in kwargs.items():
            if hasattr(assicurazione, key):
                setattr(assicurazione, key, value)
        db.session.commit()
        return assicurazione

    def delete_assicurazione(self, assicurazione_id):
        assicurazione = self.get_assicurazione_by_id(assicurazione_id)
        if not assicurazione:
            return False
        db.session.delete(assicurazione)
        db.session.commit()
        return True

    def calculate_total_cost_veicolo(self, veicolo_id):
        """Calcola il costo totale di un veicolo (finanziamento + bolli + assicurazioni + manutenzioni)"""
        veicolo = self.get_veicolo_by_id(veicolo_id)
        if not veicolo:
            return 0

        total = float(veicolo.costo_finanziamento or 0)

        # Somma bolli pagati
        bolli = self.get_bolli_by_veicolo(veicolo_id)
        total += sum(float(b.importo or 0) for b in bolli if b.data_pagamento)

        # Somma assicurazioni
        assicurazioni = self.get_assicurazioni_by_veicolo(veicolo_id)
        total += sum(float(a.importo or 0) for a in assicurazioni if a.data_pagamento)

        # Somma manutenzioni
        manutenzioni = self.get_manutenzioni_by_veicolo(veicolo_id)
        total += sum(float(m.costo or 0) for m in manutenzioni)

        return total
