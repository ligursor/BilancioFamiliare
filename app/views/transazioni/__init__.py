"""Package per le view delle transazioni.

Questo package espone i moduli per la gestione delle transazioni, categorie,
dashboard e dettaglio periodo.
"""

# re-export module symbols from the bilancio package modules
try:
    from .dashboard import *  # noqa: F401,F403
except Exception:
    pass

try:
    from .dettaglio_periodo import *  # noqa: F401,F403
except Exception:
    pass

try:
    from .transazioni import *  # noqa: F401,F403
except Exception:
    pass

try:
    from .categorie import *  # noqa: F401,F403
except Exception:
    pass
