"""
Compatibilità modello Transazione

Ora l'app usa `GeneratedTransaction` come tabella principale per le transazioni;
manteniamo il nome `Transazione` come alias per non dover cambiare il resto del codice.
"""
from app.models.generated_transaction import GeneratedTransaction as Transazione

# Alias: manteniamo il nome `Transazione` per compatibilità con il codice esistente.
