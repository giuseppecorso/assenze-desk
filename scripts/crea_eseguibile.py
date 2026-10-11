"""Crea la versione per Windows che non richiede Python: dist/AssenzeDesk/AssenzeDesk.exe.

Una cartella e non un file unico: si avvia più in fretta e le librerie Qt (LGPL)
restano file separati e sostituibili, come chiede la licenza.

Uso (con l'ambiente attivo e `pip install -e ".[exe]"`):
    python scripts/crea_eseguibile.py
Poi si comprime la cartella dist/AssenzeDesk e la si allega alla release.
"""

import sys
from pathlib import Path

import PyInstaller.__main__

RADICE = Path(__file__).resolve().parents[1]


def main() -> int:
    PyInstaller.__main__.run(
        [
            "--noconfirm",
            "--clean",
            "--windowed",  # niente finestra del terminale
            "--name",
            "AssenzeDesk",
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
    eseguibile = RADICE / "dist" / "AssenzeDesk" / "AssenzeDesk.exe"
    print(f"Creato: {eseguibile.relative_to(RADICE)}")
    print("Prova: dist\\AssenzeDesk\\AssenzeDesk.exe --demo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
