"""Re-export delle view principali per compatibilità con i nuovi namespace.

Questo package espone i moduli principali e prova a reindirizzare le importazioni
verso i nuovi package `app.views.transazioni` quando presenti.
"""

from . import main

from app.views.transazioni import dashboard as dashboard
from app.views.transazioni import dettaglio_periodo as dettaglio_periodo
from app.views.transazioni import transazioni as transazioni
from app.views.transazioni import categorie as categorie

from app.views.paypal import paypal as paypal

from app.views.ppay_evolution import ppay_evolution as ppay_evolution
