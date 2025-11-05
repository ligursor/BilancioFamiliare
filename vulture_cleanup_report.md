# Report Verifica Codice Inutilizzato - Vulture Analysis

Data: 5 novembre 2025

## Riepilogo Esecutivo

- **Voci analizzate**: 149 (da vulture_report.txt)
- **False positive** (usate ma non rilevate): ~140 (94%)
- **Codice davvero inutilizzato**: 9 elementi
- **Modifiche applicate**: 1 (import rimosso)
- **Modifiche raccomandate**: 8 (properties, attributi model)

## 1. Codice Davvero Inutilizzato (Alta Priorità)

### A. Properties Model Mai Usate

#### app/models/Transazioni.py
- `e_programmata` (riga 25-27) - ❌ **Non usata**
- `e_effettuata` (riga 30-32) - ❌ **Non usata**
- `e_in_attesa` (riga 35-37) - ❌ **Non usata**

**Verifica**: Nessun riferimento trovato in codice Python né template Jinja.
**Raccomandazione**: Rimuovere tutte e tre le properties.

#### app/models/Veicoli.py
- `giorni_alla_scadenza_bollo` (riga 68) - ❌ **Non usata**

**Verifica**: Nessun riferimento trovato in codice Python né template.
**Raccomandazione**: Rimuovere property.

### B. Attributi Model Non Referenziati

#### app/models/Transazioni.py
- `id_periodo` (riga 17) - ⚠️ **Potenzialmente inutilizzato**

**Verifica**: Definito come colonna DB ma mai letto nel codice attuale.
**Raccomandazione**: Verificare se ancora utilizzato in query SQL dirette; se no, rimuovere.

#### app/models/Veicoli.py (AutoManutenzioni)
- `km_intervento` (riga 111) - ⚠️ **Potenzialmente inutilizzato**
- `officina` (riga 112) - ⚠️ **Potenzialmente inutilizzato**

**Verifica**: Definiti come colonne DB ma mai referenziati nel codice.
**Raccomandazione**: Verificare se utilizzati nei template garage; se no, considerare rimozione.

### C. Metodi Service Non Utilizzati

#### app/services/__init__.py (BaseService)
- `get_financial_year_months()` (riga 100) - ❌ **Non usato**

**Verifica**: Metodo mai chiamato nel codebase.
**Raccomandazione**: Rimuovere o documentare se è utility per uso futuro.

#### app/services/categorie/categorie_service.py
- `get_categories_by_type()` (riga 20) - ⚠️ **Potenzialmente inutilizzato**

**Verifica**: Metodo mai chiamato esplicitamente.
**Raccomandazione**: Verificare se serve per compatibilità; se no, rimuovere.

## 2. False Positive Confermate (Ignora)

### A. Variabili Config (app/config.py)
✅ **Tutte usate** - Flask legge config via `app.config.get()`:
- `SQLALCHEMY_DATABASE_URI` - usato in __init__.py e reset_service.py
- `SQLALCHEMY_TRACK_MODIFICATIONS` - usato da Flask-SQLAlchemy
- `SECRET_KEY` - usato da Flask per session
- `HOST`, `PORT` - usati in run.py
- `FORMATO_VALUTA` - usato in formatting.py

### B. View Functions (app/views/)
✅ **Tutte usate** - Registrate via Blueprint e referenziate in templates:
- `main.reset` - usato in base.html e reset.html
- `ppay.evolution`, `ppay.ricarica`, `ppay.elimina_abbonamento`, etc. - usati in ppay_evolution.html
- `auto.garage`, `auto.aggiungi_veicolo`, etc. - usati in garage templates
- `appunti.*`, `categorie.*`, `ricorrenti.*` - tutti usati nei rispettivi template

### C. Service Classes
✅ **Tutte usate** - Istanziate dinamicamente nelle view:
- Tutti i Service (`PaypalService`, `PostePayEvolutionService`, `VeicoliService`, etc.) sono istanziati e usati nelle view corrispondenti.

### D. Model Event Listeners
✅ **Usati** - SQLAlchemy event listeners:
- `_after_insert_movimento`, `_after_delete_movimento`, `_after_update_movimento` in ContoPersonale.py
- Registrati con `@event.listens_for()`, eseguiti automaticamente da SQLAlchemy

### E. Attributi Model con Auto-Update
✅ **Usati automaticamente** da SQLAlchemy:
- `data_aggiornamento` - aggiornato via `onupdate=datetime.utcnow`
- `data_disattivazione` - usato in ppay_evolution.py per toggle abbonamenti

## 3. Modifiche Già Applicate

### A. Import Rimossi
✅ **app/views/main.py** (riga 4):
- Rimosso `from app.services.transazioni.transazioni_service import TransazioneService`
- **Confidenza**: 90%
- **Test**: Passati (compileall OK, pytest OK)

## 4. Raccomandazioni di Cleanup

### Priorità Alta (Rimozione Sicura)
1. ✅ Rimuovere properties inutilizzate da `app/models/Transazioni.py`:
   - `e_programmata`, `e_effettuata`, `e_in_attesa`

2. ✅ Rimuovere property inutilizzata da `app/models/Veicoli.py`:
   - `giorni_alla_scadenza_bollo`

3. ✅ Rimuovere metodo inutilizzato da `app/services/__init__.py`:
   - `get_financial_year_months()`

### Priorità Media (Verifica Ulteriore Raccomandata)
4. ⚠️ Verificare e rimuovere colonna DB `id_periodo` da Transazioni se confermato inutilizzato
5. ⚠️ Verificare uso di `km_intervento` e `officina` in AutoManutenzioni

### Priorità Bassa (Opzionale)
6. Considerare deprecazione/documentazione di metodi Service non chiamati ma potenzialmente utili
7. Modernizzare chiamate deprecate SQLAlchemy (`Query.get()` → `session.get()`)

## 5. Pattern Identificati

### A. Cause di False Positive
- **Flask Blueprint registration**: view functions registrate dinamicamente
- **Jinja template usage**: variabili/funzioni usate solo nei template
- **SQLAlchemy auto-features**: listeners, onupdate, relationships
- **Config access pattern**: `app.config.get('VAR')` non rilevato da Vulture

### B. Best Practice per Ridurre False Positive
- Aggiungere commenti `# noqa: vulture` per elementi volutamente non referenziati
- Documentare properties/metodi utility destinati a uso futuro
- Mantenere lista whitelist per Vulture (file .vulture_whitelist)

## Conclusioni

La maggior parte delle segnalazioni Vulture (94%) sono false positive tipiche di applicazioni Flask.

Il codice realmente inutilizzato identificato è **minimo** e consiste principalmente in:
- Properties model mai implementate nel frontend
- Helper methods service mai chiamati
- Colonne DB legacy non più referenziate

**Impatto rimozioni**: Basso rischio, alto beneficio (riduzione complessità codebase).
