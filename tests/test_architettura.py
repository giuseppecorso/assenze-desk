"""Regola di architettura: il core è logica pura.

`src/assenze_desk/core` non importa librerie grafiche, di Office, di PDF, di OCR
o di database, non legge né scrive file e non legge l'orologio di sistema (la
data di riferimento arriva sempre come argomento). Così i test del core girano
ovunque, anche nella CI su Linux, e danno sempre lo stesso risultato.

Il controllo legge il sorgente con `ast` senza eseguirlo: trova anche gli import
dentro le funzioni, che a runtime non verrebbero mai eseguiti dai test.
"""

import ast
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "src" / "assenze_desk" / "core"

# Librerie vietate nel core (si confronta il primo nome del modulo)
LIBRERIE_VIETATE = {
    "PySide6",
    "PyQt5",
    "PyQt6",
    "win32com",
    "pythoncom",
    "pywintypes",
    "openpyxl",
    "pypdf",
    "pytesseract",
    "PIL",
    "sqlite3",
}
# pywin32 ha molti moduli che iniziano così: win32api, win32gui, win32clipboard...
PREFISSI_VIETATI = ("win32",)

# Metodi di pathlib che leggono o scrivono file
METODI_FILE_VIETATI = {"read_text", "read_bytes", "write_text", "write_bytes"}

# Metodi che leggono l'orologio: date.today(), datetime.now(), datetime.utcnow(), time.time()
METODI_OROLOGIO_VIETATI = {"today", "now", "utcnow"}


def _libreria_vietata(modulo: str) -> bool:
    radice = modulo.split(".")[0]
    return radice in LIBRERIE_VIETATE or radice.startswith(PREFISSI_VIETATI)


def violazioni(sorgente: str, nome_file: str = "<test>") -> list[str]:
    """Elenca le violazioni della regola di architettura in un sorgente Python."""
    trovate = []
    for nodo in ast.walk(ast.parse(sorgente, filename=nome_file)):
        if isinstance(nodo, ast.Import):
            moduli = [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            moduli = [nodo.module]
        else:
            moduli = []
        trovate += [
            f"{nome_file}:{nodo.lineno}: import di {m}" for m in moduli if _libreria_vietata(m)
        ]

        if isinstance(nodo, ast.Call) and _legge_o_scrive_file(nodo.func):
            nome = nodo.func.id if isinstance(nodo.func, ast.Name) else nodo.func.attr
            trovate.append(f"{nome_file}:{nodo.lineno}: chiamata a {nome}()")

        if isinstance(nodo, ast.Call) and _legge_l_orologio(nodo.func):
            trovate.append(
                f"{nome_file}:{nodo.lineno}: lettura dell'orologio con {nodo.func.attr}()"
            )
    return trovate


def _legge_l_orologio(funzione: ast.expr) -> bool:
    if not isinstance(funzione, ast.Attribute):
        return False
    e_time_time = (
        funzione.attr == "time"
        and isinstance(funzione.value, ast.Name)
        and funzione.value.id == "time"
    )
    return funzione.attr in METODI_OROLOGIO_VIETATI or e_time_time


def _legge_o_scrive_file(funzione: ast.expr) -> bool:
    if isinstance(funzione, ast.Name):  # open(...)
        return funzione.id == "open"
    if isinstance(funzione, ast.Attribute):  # percorso.read_text(...), io.open(...)
        e_io_open = (
            funzione.attr == "open"
            and isinstance(funzione.value, ast.Name)
            and funzione.value.id == "io"
        )
        return funzione.attr in METODI_FILE_VIETATI or e_io_open
    return False


def test_il_pacchetto_core_esiste():
    assert (CORE / "__init__.py").is_file()


def test_il_core_non_usa_librerie_di_io_ne_legge_file():
    trovate = []
    for file in sorted(CORE.rglob("*.py")):
        # utf-8-sig: accetta anche i file salvati con BOM (comune su Windows)
        sorgente = file.read_text(encoding="utf-8-sig")
        trovate += violazioni(sorgente, file.relative_to(CORE).as_posix())
    assert trovate == []


# --- Il controllo stesso funziona? Si prova su sorgenti inventati. ---


def test_trova_gli_import_vietati():
    sorgente = (
        "import openpyxl\n"
        "from PySide6.QtWidgets import QWidget\n"
        "import win32api\n"
        "def f():\n"
        "    import sqlite3\n"
    )
    assert violazioni(sorgente) == [
        "<test>:1: import di openpyxl",
        "<test>:2: import di PySide6.QtWidgets",
        "<test>:3: import di win32api",
        "<test>:5: import di sqlite3",
    ]


def test_trova_la_lettura_e_la_scrittura_di_file():
    sorgente = "open('a.txt')\nio.open('b.txt')\npercorso.read_text()\npercorso.write_bytes(b'')\n"
    assert violazioni(sorgente) == [
        "<test>:1: chiamata a open()",
        "<test>:2: chiamata a open()",
        "<test>:3: chiamata a read_text()",
        "<test>:4: chiamata a write_bytes()",
    ]


def test_trova_la_lettura_dell_orologio_di_sistema():
    sorgente = "date.today()\ndatetime.now()\ndatetime.utcnow()\ntime.time()\n"
    assert violazioni(sorgente) == [
        "<test>:1: lettura dell'orologio con today()",
        "<test>:2: lettura dell'orologio con now()",
        "<test>:3: lettura dell'orologio con utcnow()",
        "<test>:4: lettura dell'orologio con time()",
    ]


def test_ammette_librerie_standard_e_import_relativi():
    sorgente = (
        "import re\n"
        "from datetime import date\n"
        "from . import episodio\n"
        "from .testo import estrai_protocollo\n"
        "win32_finto = 1\n"
        "documento.open_bozza()\n"
        "date(2026, 1, 5)\n"
        "riferimento + timedelta(days=1)\n"
    )
    assert violazioni(sorgente) == []
