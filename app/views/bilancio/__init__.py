"""Package per le view del bilancio (shim).

Questo package espone i moduli esistenti tramite import re-export in modo da
introdurre il namespace `app.views.bilancio` senza muovere i file originali.
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
