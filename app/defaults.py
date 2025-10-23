"""
Default data values separated from operational configuration.

Questo modulo contiene valori di 'contenuto' usati dall'app (liste di categorie,
liste di piani/abbonamenti di esempio) che non dovrebbero essere miscelati con
le impostazioni operative del runtime (DB, SECRET_KEY, flags, ecc.).

Viene usato come sorgente unica per i valori predefiniti e può essere sovrascritto
da configurazioni runtime o dal database.
"""

# Categorie predefinite (nome, tipo)
CATEGORIE_DEFAULT = [
    # Entrate
    ('Stipendio', 'entrata'),
    ('Extra', 'entrata'),
    ('Altro', 'entrata'),

    # Uscite
    ('Trasporti', 'uscita'),
    ('Spese Casa', 'uscita'),
    ('Spese Mensili', 'uscita'),
    ('Sport', 'uscita'),  # Aggiunta settembre 2025
    ('Altro', 'uscita')
]

# Placeholder per piani PayPal predefiniti (vuoto per default; configurabile)
PIANI_PAYPAL_DEFAULT = []

# Placeholder per abbonamenti PostePay predefiniti (vuoto per default; configurabile)
POSTEPAY_ABBONAMENTI_DEFAULT = []
