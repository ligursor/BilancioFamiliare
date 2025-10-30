"""Re-export delle view principali per compatibilità con i nuovi namespace.

Questo package espone i moduli principali e prova a reindirizzare le importazioni
verso i nuovi package `app.views.bilancio` quando presenti.
"""

from . import main

from app.views.bilancio import dashboard as dashboard
from app.views.bilancio import dettaglio_periodo as dettaglio_periodo
from app.views.bilancio import transazioni as transazioni
from app.views.bilancio import categorie as categorie

from app.views.paypal import paypal as paypal
