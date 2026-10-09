"""Regola di architettura: il core è logica pura.

`src/assenze_desk/core` non importa librerie grafiche, di Office, di PDF, di OCR
o di database e non legge né scrive file. Così i test del core girano ovunque,
anche nella CI su Linux.

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
            f"{nome_file}:{nodo.lineno}: import di {m}"
            for m in moduli
            if _libreria_vietata(m)
        ]

        if isinstance(nodo, ast.Call) and _legge_o_scrive_file(nodo.func):
            nome = nodo.func.id if isinstance(nodo.func, ast.Name) else nodo.func.attr
            trovate.append(f"{nome_file}:{nodo.lineno}: chiamata a {nome}()")
    return trovate


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
    sorgente = (
        "open('a.txt')\n"
        "io.open('b.txt')\n"
        "percorso.read_text()\n"
        "percorso.write_bytes(b'')\n"
    )
    assert violazioni(sorgente) == [
        "<test>:1: chiamata a open()",
        "<test>:2: chiamata a open()",
        "<test>:3: chiamata a read_text()",
        "<test>:4: chiamata a write_bytes()",
    ]


def test_ammette_librerie_standard_e_import_relativi():
    sorgente = (
        "import re\n"
        "from datetime import date\n"
        "from . import episodio\n"
        "from .testo import estrai_protocollo\n"
        "win32_finto = 1\n"
        "documento.open_bozza()\n"
    )
    assert violazioni(sorgente) == []
