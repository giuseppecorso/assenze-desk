"""Assistente per il portale INPS di consultazione degli attestati di malattia.

L'utente apre il portale, inserisce CF e protocollo (copiati negli appunti
dall'interfaccia), completa il codice di controllo e scarica il PDF. Qui si
trova il PDF appena scaricato e lo si archivia come "<protocollo>.pdf", senza
mai sovrascrivere un file diverso. Nessun tasto viene premuto al posto
dell'utente nel browser: incollare alla cieca dopo qualche secondo è fragile
(pagina non ancora pronta, cursore in un altro campo o in un'altra finestra).
"""

import shutil
import webbrowser
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from assenze_desk.adapters.file import nome_libero

URL_PORTALE_INPS = "https://serviziweb2.inps.it/AS0207/AttestatiMalCittadino/"


class ErroreInps(Exception):
    """Problema con l'archiviazione del certificato: messaggio per l'utente."""


def apri_portale(
    url: str = URL_PORTALE_INPS, apri: Callable[[str], object] = webbrowser.open
) -> None:
    apri(url)


def pdf_scaricati_dopo(cartella: Path, dopo: datetime, margine_secondi: float = 5) -> list[Path]:
    """PDF comparsi nella cartella dei download dopo l'apertura del portale, recenti prima."""
    cartella = Path(cartella)
    if not cartella.is_dir():
        return []
    limite = dopo.timestamp() - margine_secondi
    recenti = [
        file
        for file in cartella.iterdir()
        if file.is_file() and file.suffix.lower() == ".pdf" and file.stat().st_mtime >= limite
    ]
    return sorted(recenti, key=lambda file: file.stat().st_mtime, reverse=True)


def archivia_certificato(sorgente: Path, cartella: Path, protocollo: str) -> Path:
    sorgente, cartella, protocollo = Path(sorgente), Path(cartella), protocollo.strip()
    if not protocollo:
        raise ErroreInps("Serve il protocollo per dare il nome al certificato.")
    if sorgente.suffix.lower() != ".pdf":
        raise ErroreInps(f"Il file {sorgente.name} non è un PDF.")
    cartella.mkdir(parents=True, exist_ok=True)
    destinazione = cartella / f"{protocollo}.pdf"
    if destinazione.exists():
        if destinazione.read_bytes() == sorgente.read_bytes():
            sorgente.unlink()  # stesso certificato già archiviato
            return destinazione
        destinazione = nome_libero(destinazione)
    shutil.move(sorgente, destinazione)
    return destinazione
