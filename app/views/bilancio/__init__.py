"""Package per le view del bilancio (shim).

Questo package espone i moduli esistenti tramite import re-export in modo da
introdurre il namespace `app.views.bilancio` senza muovere i file originali.
"""

# re-export module symbols when possibile
try:
    from app.views.dashboard import *  # noqa: F401,F403
except Exception:
    pass

try:
    from app.views.dettaglio_periodo import *  # noqa: F401,F403
except Exception:
    pass

try:
    from app.views.transazioni import *  # noqa: F401,F403
except Exception:
    pass

try:
    from app.views.categorie import *  # noqa: F401,F403
except Exception:
    pass
