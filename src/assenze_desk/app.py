"""Avvio dell'app: `assenze-desk` oppure `python -m assenze_desk`.

Con `--demo` l'app parte su una cartella temporanea piena di dati finti, senza
Outlook, e la cancella alla chiusura. Senza, usa la cartella dati dell'utente
(%LOCALAPPDATA%\\AssenzeDesk) o quella indicata con `--cartella-dati`.
"""

import argparse
import logging
import shutil
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from assenze_desk.config import cartella_dati_predefinita
from assenze_desk.gui import tema
from assenze_desk.gui.finestra import FinestraPrincipale
from assenze_desk.registro import chiudi_log
from assenze_desk.servizi import apri_contesto

log = logging.getLogger(__name__)


def argomenti(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="assenze-desk", description="Assenze Desk")
    parser.add_argument("--demo", action="store_true", help="parte con dati finti, senza Outlook")
    parser.add_argument("--cartella-dati", type=Path, help="cartella di archivio e impostazioni")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    scelte = argomenti(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Assenze Desk")
    cartella_demo = Path(tempfile.mkdtemp(prefix="assenze-desk-demo-")) if scelte.demo else None
    cartella = cartella_demo or scelte.cartella_dati or cartella_dati_predefinita()
    try:
        contesto, avvisi = apri_contesto(cartella, demo=scelte.demo)
    except ValueError as errore:
        tema.applica_tema(app, "sistema")
        QMessageBox.critical(
            None,
            "Assenze Desk",
            f"Il file delle impostazioni non è valido: {errore}.\nCartella: {cartella}",
        )
        return 1

    finestra = FinestraPrincipale(contesto, avvisi)
    precedente = sys.excepthook
    sys.excepthook = finestra.errore_imprevisto
    finestra.show()
    try:
        return app.exec()
    finally:
        sys.excepthook = precedente
        contesto.chiudi()
        chiudi_log()
        if cartella_demo is not None:
            shutil.rmtree(cartella_demo, ignore_errors=True)
