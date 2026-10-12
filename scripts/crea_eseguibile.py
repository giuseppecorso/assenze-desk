"""Crea la versione per Windows che non richiede Python: dist/AssenzeDesk/AssenzeDesk.exe.

Una cartella e non un file unico: si avvia più in fretta e le librerie Qt (LGPL)
restano file separati e sostituibili, come chiede la licenza.

Uso (con l'ambiente attivo e `pip install -e ".[exe]"`):
    python scripts/crea_eseguibile.py
Nella cartella finiscono anche Installa.cmd, Disinstalla.cmd e LEGGIMI.txt
(scripts/installatore): chi riceve lo zip lo estrae e fa doppio clic su Installa.cmd.
Poi si comprime la cartella dist/AssenzeDesk e la si allega alla release.
"""

import shutil
import sys
from pathlib import Path

import PyInstaller.__main__
from PySide6.QtGui import QGuiApplication

from assenze_desk.gui.icone import scrivi_ico

RADICE = Path(__file__).resolve().parents[1]
INSTALLATORE = RADICE / "scripts" / "installatore"


def main() -> int:
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # per disegnare l'icona
    (RADICE / "build").mkdir(exist_ok=True)
    icona = scrivi_ico(RADICE / "build" / "AssenzeDesk.ico")
    PyInstaller.__main__.run(
        [
            "--noconfirm",
            "--clean",
            "--windowed",  # niente finestra del terminale
            "--name",
            "AssenzeDesk",
            "--icon",
            str(icona),
            "--paths",
            str(RADICE / "src"),
            "--distpath",
            str(RADICE / "dist"),
            "--workpath",
            str(RADICE / "build"),
            "--specpath",
            str(RADICE / "build"),
            str(RADICE / "src" / "assenze_desk" / "__main__.py"),
        ]
    )
    cartella = RADICE / "dist" / "AssenzeDesk"
    for file in INSTALLATORE.iterdir():
        shutil.copy2(file, cartella / file.name)
    eseguibile = cartella / "AssenzeDesk.exe"
    print(f"Creato: {eseguibile.relative_to(RADICE)}")
    print("Prova: dist\\AssenzeDesk\\AssenzeDesk.exe --demo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
