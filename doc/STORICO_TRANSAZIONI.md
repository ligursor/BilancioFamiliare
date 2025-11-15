# Storico Transazioni Archiviate

## Descrizione
Sistema di archiviazione automatica delle transazioni durante il rollover mensile.

## Funzionalità Implementate

### 1. Modello TransazioniArchivio
- Nuovo modello `TransazioniArchivio` in `app/models/TransazioniArchivio.py`
- Tabella `transazioni_archivio` con tutti i campi delle transazioni originali
- Campo `categoria_nome` denormalizzato per preservare il nome categoria
- Campo `data_archiviazione` per tracciare quando è stata archiviata
- Indice su `id_periodo` per query veloci

### 2. Archiviazione Automatica nel Rollover
- Modificato `app/services/transazioni/monthly_rollover_service.py`
- Prima di eliminare le transazioni del mese precedente, vengono archiviate
- Preserva tutti i dati originali incluso il nome della categoria

### 3. Pagina Storico Transazioni
- Nuovo blueprint `storico_bp` in `app/views/transazioni/storico.py`
- Route `/storico` per visualizzare le transazioni archiviate
- Filtro dropdown per selezionare il periodo (formato YYYYMM)
- Lista periodi ordinata in ordine crescente
- Statistiche del periodo: entrate, uscite, bilancio, numero transazioni

### 4. Template Storico
- Nuovo template `app/templates/transazioni/storico.html`
- Card statistiche con riepilogo entrate/uscite/bilancio
- Tabella transazioni con data, descrizione, categoria, tipo, importo
- Dropdown per filtrare per periodo
- Design responsive e coerente con il resto dell'applicazione

### 5. Pulsante Storico nella Dashboard
- Aggiunto pulsante "Storico" nell'header della dashboard principale
- Posizionato sulla destra accanto al titolo "Panoramica Bilancio - Prossimi 6 Mesi"
- Icona archivio per identificazione visiva

## Installazione

### Creare la tabella nel database
Eseguire lo script di migrazione:

```bash
cd /home/pi/BilancioFamiliare  # o /home/roberto/personal/BilancioFamiliare
/home/pi/BilancioFamiliare/.venv/bin/python scripts/create_archivio_table.py
```

### Riavviare l'applicazione
```bash
# Se usi systemd
sudo systemctl restart bilancio.service

# Se usi Docker
docker-compose restart

# Se usi manualmente
# Termina il processo corrente e riavvia run.py
```

## Utilizzo

1. **Accesso allo Storico**
   - Dalla dashboard principale, cliccare sul pulsante "Storico" in alto a destra
   - Oppure navigare direttamente a `/storico`

2. **Filtrare per Periodo**
   - Selezionare il periodo desiderato dal menu a tendina
   - I periodi sono elencati in ordine crescente (dal più vecchio al più recente)
   - Di default viene visualizzato l'ultimo periodo archiviato

3. **Visualizzazione Transazioni**
   - Le transazioni sono ordinate per data decrescente
   - Ogni transazione mostra: data, descrizione, categoria, tipo (entrata/uscita), importo
   - Le statistiche del periodo sono visualizzate in card nella parte superiore

## Note Tecniche

### Formato id_periodo
- L'`id_periodo` è nel formato YYYYMM (es. 202411 per Novembre 2024)
- Usato come chiave per raggruppare e filtrare le transazioni archiviate

### Archiviazione
- L'archiviazione avviene automaticamente durante il rollover mensile
- Solo le transazioni con `data < current_month_start` vengono archiviate
- Il nome della categoria viene denormalizzato per preservarlo anche se la categoria viene modificata/eliminata

### Performance
- Indice su `id_periodo` per query veloci
- Query ottimizzate per recuperare solo il periodo selezionato

## File Modificati/Creati

### Nuovi File
- `app/models/TransazioniArchivio.py`
- `app/views/transazioni/storico.py`
- `app/templates/transazioni/storico.html`
- `scripts/create_archivio_table.py`
- `doc/STORICO_TRANSAZIONI.md` (questo file)

### File Modificati
- `app/services/transazioni/monthly_rollover_service.py`
- `app/views/__init__.py`
- `app/__init__.py`
- `app/templates/bilancio/index.html`
