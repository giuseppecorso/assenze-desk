"""Piccoli aiuti sui file, comuni agli adapter."""

from pathlib import Path


def nome_libero(percorso: Path) -> Path:
    """Il percorso, oppure "nome (2).pdf", "nome (3).pdf"... se esiste già."""
    numero = 2
    libero = percorso
    while libero.exists():
        libero = percorso.with_name(f"{percorso.stem} ({numero}){percorso.suffix}")
        numero += 1
    return libero
