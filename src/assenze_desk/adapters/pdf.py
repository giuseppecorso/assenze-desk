"""Lettura del certificato di malattia da PDF: estrae il testo con pypdf e lo passa al core."""

import logging
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from assenze_desk.core.certificato import DatiCertificato, leggi_certificato

log = logging.getLogger(__name__)


class ErrorePdf(Exception):
    """Il PDF non si può leggere: il messaggio è pronto da mostrare all'utente."""


def testo_pdf(percorso: Path) -> str:
    percorso = Path(percorso)
    try:
        lettore = PdfReader(str(percorso))
        return "\n".join(pagina.extract_text() or "" for pagina in lettore.pages).strip()
    except FileNotFoundError:
        raise ErrorePdf(f"Il file {percorso.name} non esiste.") from None
    except (PdfReadError, OSError, ValueError) as errore:
        log.warning("PDF non leggibile %s: %s", percorso.name, errore)
        raise ErrorePdf(f"Il file {percorso.name} non è un PDF leggibile.") from errore


def leggi_certificato_pdf(
    percorso: Path, x_prima_della_voce: bool | None = None
) -> DatiCertificato:
    testo = testo_pdf(percorso)
    if not testo:
        raise ErrorePdf(
            f"Il file {Path(percorso).name} non contiene testo: forse è una scansione. "
            "Inserisci i dati a mano."
        )
    return leggi_certificato(testo, x_prima_della_voce)
