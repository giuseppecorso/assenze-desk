"""Assenze Desk: gestione di malattie e giustificativi a partire dalle mail."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("assenze-desk")
except PackageNotFoundError:  # codice usato senza installare il pacchetto
    __version__ = "0.0.0"
