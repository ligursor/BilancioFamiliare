"""
Placeholder: the backup utility was archived to `_backup/obsolete/app_utils_backup.py`.
This module intentionally provides no functions to avoid accidental usage.
Restore from the backup file to re-enable the feature.
"""

# inert stub

def get_backup_dir(app_config=None):
    """Restituisce la directory di backup corretta in base all'ambiente."""
    # Se è configurata una variabile d'ambiente DOCKER, usa /app/backup
    # Altrimenti usa ./backup
    if app_config and app_config.get('DOCKER', False):
        return '/app/backup'
    # Oppure se la cartella /app/ esiste, presumiamo Docker
    if os.path.exists('/app/'):
        return '/app/backup'
    return os.path.abspath('./backup')

def export_database_to_backup(db, Categoria, SaldoIniziale, Transazione, PaypalPiano, PaypalRata, ContoPersonale, VersamentoPersonale, Veicolo, BolloAuto, ManutenzioneAuto, PostePayEvolution, AbbonamentoPostePay, MovimentoPostePay, Appunto, app_config=None):
    """Esporta il database nella cartella backup dopo modifiche"""
    try:
        from datetime import datetime, date
        def serialize_date(obj):
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            raise TypeError(f"Object {obj} is not JSON serializable")
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
                'abbonamenti_poste_pay': [],
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
        try:
            abbonamenti = AbbonamentoPostePay.query.all()
            data['data'].setdefault('abbonamenti_postepay', [])
            for abbonamento in abbonamenti:
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
        except Exception as e:
            print(f"Errore export abbonamenti_postepay: {e}")
            data['data']['abbonamenti_postepay'] = []
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
        backup_dir = get_backup_dir(app_config)
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        filename = f'bilancio_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        filepath = os.path.join(backup_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=serialize_date, indent=2, ensure_ascii=False)
        print(f"Database export salvato in: {filepath}")
        # Pulizia automatica: mantieni solo i backup delle ultime N date (configurabile)
        keep_dates = 2
        if app_config and 'BACKUP_KEEP_DATES' in app_config:
            keep_dates = app_config['BACKUP_KEEP_DATES']
        cleanup_old_backups(backup_dir, keep_dates)
        return True
    except Exception as e:
        print(f"Errore durante l'export del database: {str(e)}")
        return False
