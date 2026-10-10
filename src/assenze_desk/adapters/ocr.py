"""OCR di una zona dello schermo: prepara l'immagine e la legge con Tesseract.

La cattura dello schermo la fa l'interfaccia; qui arriva un'immagine (Pillow).
Tesseract è un programma da installare a parte: si cerca nell'impostazione, nella
variabile TESSERACT_CMD, nel PATH e nei percorsi di installazione standard.
Si leggono più ritagli dell'immagine e si tiene il testo di qualità migliore.
"""

import logging
import os
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from assenze_desk.core.ocr import pulisci_testo_ocr, qualita_testo

log = logging.getLogger(__name__)

PERCORSI_STANDARD = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)
QUALITA_SUFFICIENTE = 45
_CONFIGURAZIONE = "--oem 3 --psm 6 -c preserve_interword_spaces=1"


class ErroreOcr(Exception):
    """Problema con l'OCR: il messaggio è pronto da mostrare all'utente."""


def trova_tesseract(
    impostato: str = "", esiste: Callable[[Path], bool] = Path.is_file
) -> Path | None:
    candidati = [impostato, os.environ.get("TESSERACT_CMD", ""), shutil.which("tesseract") or ""]
    percorsi = [Path(c) for c in candidati if c.strip()] + list(PERCORSI_STANDARD)
    if programmi_utente := os.environ.get("LOCALAPPDATA"):
        percorsi.append(Path(programmi_utente) / "Programs" / "Tesseract-OCR" / "tesseract.exe")
    return next((percorso for percorso in percorsi if esiste(percorso)), None)


def prepara_immagine(immagine: Image.Image) -> Image.Image:
    """Bianco e nero, ingrandita e contrastata: Tesseract legge meglio."""
    grigio = ImageOps.grayscale(immagine)
    scala = 3 if max(grigio.size) < 1200 else 2
    grigio = grigio.resize((grigio.width * scala, grigio.height * scala))
    grigio = ImageEnhance.Contrast(grigio).enhance(2.2).filter(ImageFilter.SHARPEN)
    return grigio.point(lambda pixel: 255 if pixel > 178 else 0)


def leggi_testo_immagine(
    immagine: Image.Image,
    tesseract: Path | None,
    parole_rumore: Sequence[str] = (),
    ocr: Callable[..., str] | None = None,
) -> str:
    if tesseract is None:
        raise ErroreOcr(
            "Tesseract OCR non trovato: installalo oppure indica dove si trova nelle impostazioni."
        )
    leggi = ocr or _tesseract(tesseract)
    larghezza, altezza = immagine.size
    ritagli = [
        immagine,
        immagine.crop(
            (int(larghezza * 0.02), int(altezza * 0.02), int(larghezza * 0.98), int(altezza * 0.98))
        ),
        immagine.crop(
            (int(larghezza * 0.05), int(altezza * 0.04), int(larghezza * 0.97), int(altezza * 0.97))
        ),
    ]
    migliore, punteggio_migliore = "", -1000
    for ritaglio in ritagli:
        testo = pulisci_testo_ocr(
            leggi(prepara_immagine(ritaglio), config=_CONFIGURAZIONE), parole_rumore
        )
        punteggio = qualita_testo(testo)
        if punteggio > punteggio_migliore:
            migliore, punteggio_migliore = testo, punteggio
        if punteggio >= QUALITA_SUFFICIENTE:
            break
    if not migliore:
        raise ErroreOcr("Nessun testo utile trovato: prova con un ritaglio più stretto sulla mail.")
    return migliore


def _tesseract(comando: Path) -> Callable[..., str]:  # pragma: no cover - serve Tesseract
    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = str(comando)

    def leggi(immagine: Any, config: str) -> str:
        try:
            return pytesseract.image_to_string(immagine, lang="ita+eng", config=config)
        except pytesseract.TesseractError:
            log.info("Lingua italiana di Tesseract non disponibile: uso l'inglese")
            return pytesseract.image_to_string(immagine, lang="eng", config=config)

    return leggi
