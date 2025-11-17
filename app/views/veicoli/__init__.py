"""Package per le view dei veicoli: re-export dai moduli interni."""
"""Re-export the veicoli blueprint from the module implementation."""
# Re-export the blueprint from the module so imports like
# `from app.views.veicoli.veicoli import veicoli_bp` continue to work
from .veicoli import *  # noqa: F401,F403
