"""Package per le view dei veicoli: re-export dai moduli interni."""
# The legacy `auto` module was removed and replaced by `veicoli.py`.
# Re-export the blueprint from the new module so imports like
# `from app.views.veicoli.veicoli import veicoli_bp` continue to work
from .veicoli import *  # noqa: F401,F403
