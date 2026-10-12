"""Copie di sicurezza e integrità dell'archivio SQLite.

- All'apertura dell'app si fa una copia al giorno, `archivio-AAAA-MM-GG.db`, nella
  cartella scelta nelle impostazioni (anche una cartella sincronizzata o di rete:
  la copia è un file chiuso, che l'app non usa). Si tengono le ultime 14.
- La copia usa l'API di backup di SQLite: è coerente anche mentre l'archivio è aperto.
- Se l'archivio è danneggiato si mette da parte (mai cancellato) e si riparte
  dall'ultima copia; senza copie si riparte da un archivio vuoto. L'utente viene
  sempre avvisato con la data della copia usata.
"""

import re
import shutil
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from assenze_desk.core import formati

COPIE_DA_TENERE = 14
_NOME_COPIA = re.compile(r"archivio-(\d{4}-\d{2}-\d{2})\.db")


def copia_di_sicurezza(archivio, cartella: Path, oggi: date) -> Path | None:
    """La copia di oggi, se non c'è ancora; poi via le copie più vecchie."""
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    destinazione = cartella / f"archivio-{oggi:%Y-%m-%d}.db"
    if destinazione.exists():
        return None
    provvisoria = destinazione.with_suffix(".tmp")
    archivio.copia_in(provvisoria)
    provvisoria.replace(destinazione)  # niente copie a metà se il PC si spegne
    for vecchia in _copie(cartella)[:-COPIE_DA_TENERE]:
        vecchia.unlink()
    return destinazione


def integro(percorso: Path) -> bool:
    """Un archivio che non esiste ancora è integro: verrà creato."""
    if not Path(percorso).exists():
        return True
    try:
        with closing(sqlite3.connect(percorso)) as db:
            return db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except sqlite3.DatabaseError:
        return False


def ripristina(percorso: Path, cartella: Path, adesso: datetime) -> str:
    """Archivio danneggiato: lo mette da parte e usa l'ultima copia integra.
    Restituisce l'avviso per l'utente."""
    percorso = Path(percorso)
    da_parte = percorso.with_name(f"archivio-danneggiato-{adesso:%Y-%m-%d-%H%M%S}.db")
    percorso.replace(da_parte)
    for copia in reversed(_copie(Path(cartella))):
        if integro(copia):
            shutil.copy2(copia, percorso)
            giorno = date.fromisoformat(_NOME_COPIA.fullmatch(copia.name).group(1))
            return (
                f"L'archivio era danneggiato: ho ripreso la copia di sicurezza del "
                f"{formati.data(giorno)}. Ricontrolla le pratiche gestite dopo quel giorno. "
                f"Il file danneggiato è in {da_parte}."
            )
    return (
        "L'archivio era danneggiato e non c'è nessuna copia di sicurezza: riparto da un "
        f"archivio vuoto. Il file danneggiato è in {da_parte}."
    )


def _copie(cartella: Path) -> list[Path]:
    if not cartella.is_dir():
        return []
    return sorted(f for f in cartella.iterdir() if _NOME_COPIA.fullmatch(f.name))
