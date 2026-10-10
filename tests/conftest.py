"""Impostazioni comuni ai test."""

import os

# Le finestre dei test dell'interfaccia non compaiono sullo schermo e girano
# anche nella CI su Linux, che non ha uno schermo.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
