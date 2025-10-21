"""
Servizio per la gestione del database e backup
"""
from app.services import BaseService
from app.models.base import Categoria, SaldoIniziale
from app.models.transazioni import Transazione
from app.models.paypal import PaypalPiano, PaypalRata
from app.models.conti_personali import ContoPersonale
from app.models.garage import Veicolo
from app.models.postepay import PostePayEvolution, AbbonamentoPostePay
from app.models.appunti import Appunto
from app.models.budget import Budget
from datetime import datetime
import json
import os
from flask import current_app

class DatabaseService(BaseService):
    """Servizio per operazioni sul database"""
    
    def initialize_default_categories(self):
        """Inizializza le categorie predefinite"""
        try:
            # Controlla se esistono già categorie
            if Categoria.query.count() > 0:
                return True, "Categorie già esistenti"
            
            for nome, tipo in current_app.config['CATEGORIE_DEFAULT']:
                categoria = Categoria(nome=nome, tipo=tipo)
                self.db.session.add(categoria)
            
            self.db.session.commit()
            return True, f"Create {len(current_app.config['CATEGORIE_DEFAULT'])} categorie predefinite"
        except Exception as e:
            self.db.session.rollback()
            return False, str(e)
    
    def initialize_saldo_iniziale(self, importo=0.0):
        """Inizializza il saldo iniziale"""
        try:
            saldo = SaldoIniziale.query.first()
            if not saldo:
                saldo = SaldoIniziale(importo=importo)
                self.db.session.add(saldo)
                self.db.session.commit()
            return True, "Saldo iniziale impostato"
        except Exception as e:
            self.db.session.rollback()
            return False, str(e)
    
    def initialize_conti_personali(self):
        """Inizializza i conti personali predefiniti"""
        try:
            from app.services.conti_personali_service import ContiPersonaliService
            service = ContiPersonaliService()
            return service.initialize_default_conti()
        except Exception as e:
            print(f"Errore nell'inizializzazione conti personali: {e}")
            return False

    def initialize_budget_defaults(self):
        """Inizializza i budget di default (Sport e Spese Mensili)"""
        try:
            # Se esistono già budget, non fare nulla
            if Budget.query.count() > 0:
                return True, "Budget già inizializzati"

            # Assumi che le categorie abbiano gli id presenti in config
            from flask import current_app
            sport_id = current_app.config.get('CATEGORIA_SPORT_ID', 8)
            spese_id = current_app.config.get('CATEGORIA_SPESE_MENSILI_ID', 6)

            budget_sport = Budget(categoria_id=sport_id, importo=100.0)
            budget_spese = Budget(categoria_id=spese_id, importo=600.0)

            self.db.session.add(budget_sport)
            self.db.session.add(budget_spese)
            self.db.session.commit()
            return True, "Budget di default creati"
        except Exception as e:
            self.db.session.rollback()
            return False, str(e)
    
    def export_database(self, filepath=None):
        """Esporta tutto il database in formato JSON"""
        try:
            if filepath is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filepath = f"backup/bilancio_export_{timestamp}.json"
            
            # Assicurati che la directory esista
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            data = {
                'export_date': datetime.now().isoformat(),
                'categorie': self._export_table(Categoria),
                'saldo_iniziale': self._export_table(SaldoIniziale),
                'transazioni': self._export_table(Transazione),
                'budget': self._export_table(Budget),
                'paypal_piani': self._export_table(PaypalPiano),
                'paypal_rate': self._export_table(PaypalRata),
                'conti_personali': self._export_table(ContoPersonale),
                'veicoli': self._export_table(Veicolo),
                'postepay': self._export_table(PostePayEvolution),
                'abbonamenti_postepay': self._export_table(AbbonamentoPostePay),
                'appunti': self._export_table(Appunto)
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            return True, f"Database esportato in: {filepath}"
        except Exception as e:
            return False, str(e)
    
    def _export_table(self, model_class):
        """Esporta una singola tabella"""
        try:
            items = model_class.query.all()
            result = []
            
            for item in items:
                item_dict = {}
                for column in model_class.__table__.columns:
                    value = getattr(item, column.name)
                    # Converte date e datetime in stringhe
                    if isinstance(value, (datetime, datetime.date)):
                        value = value.isoformat()
                    item_dict[column.name] = value
                result.append(item_dict)
            
            return result
        except Exception:
            return []
    
    def import_database(self, filepath):
        """Importa database da file JSON"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Importa nell'ordine corretto per rispettare le foreign key
            tables_order = [
                ('categorie', Categoria),
                ('saldo_iniziale', SaldoIniziale),
                ('transazioni', Transazione),
                ('budget', Budget),
                ('paypal_piani', PaypalPiano),
                ('paypal_rate', PaypalRata),
                ('conti_personali', ContoPersonale),
                ('veicoli', Veicolo),
                ('postepay', PostePayEvolution),
                ('abbonamenti_postepay', AbbonamentoPostePay),
                ('appunti', Appunto)
            ]
            
            imported_count = 0
            for table_name, model_class in tables_order:
                if table_name in data:
                    count = self._import_table(model_class, data[table_name])
                    imported_count += count
            
            self.db.session.commit()
            return True, f"Importati {imported_count} record dal file {filepath}"
        except Exception as e:
            self.db.session.rollback()
            return False, str(e)
    
    def _import_table(self, model_class, items):
        """Importa una singola tabella"""
        count = 0
        for item_data in items:
            try:
                # Converte stringhe in date dove necessario
                for key, value in item_data.items():
                    if isinstance(value, str) and ('data' in key.lower() or key.endswith('_at')):
                        try:
                            if 'T' in value:
                                item_data[key] = datetime.fromisoformat(value)
                            else:
                                item_data[key] = datetime.strptime(value, '%Y-%m-%d').date()
                        except ValueError:
                            pass
                
                # Crea l'oggetto
                obj = model_class(**item_data)
                self.db.session.add(obj)
                count += 1
            except Exception:
                continue
        
        return count
    
    def cleanup_old_backups(self, backup_dir='backup', keep_recent=5, keep_dates=2):
        """Pulisce i backup vecchi mantenendo solo i più recenti"""
        try:
            if not os.path.exists(backup_dir):
                return True, "Directory backup non esistente"
            
            files = [f for f in os.listdir(backup_dir) if f.startswith('bilancio_export_') and f.endswith('.json')]
            
            if len(files) <= keep_recent:
                return True, "Nessun backup da eliminare"
            
            # Ordina per data di modifica (più recenti prima)
            files.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)), reverse=True)
            
            # Elimina i file più vecchi
            for file_to_delete in files[keep_recent:]:
                os.remove(os.path.join(backup_dir, file_to_delete))
            
            deleted_count = len(files) - keep_recent
            return True, f"Eliminati {deleted_count} backup vecchi"
        except Exception as e:
            return False, str(e)
