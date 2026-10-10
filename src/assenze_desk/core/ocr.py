"""Pulizia del testo letto con l'OCR e stima della sua qualità.

Si tolgono le righe di disturbo (barre dei menu, simboli, lettere sparse) ma si
tengono sempre le righe con dati utili: numeri lunghi, date, CF, email, parole
dei certificati e dei permessi. Le parole di disturbo specifiche (nomi di
programmi o portali visibili sullo schermo) vengono dalle impostazioni.
Le righe non si uniscono: il core legge anche testi su più righe.
"""

import re
from collections.abc import Sequence

from assenze_desk.core.testo import normalizza

_UTILI = re.compile(
    r"(?:\d[\s-]?){8,}"  # protocollo, JobOrder
    r"|\b[0-3]?\d[/.-][01]?\d[/.-]\d{2,4}\b"  # data
    r"|\b[A-Za-z]{6}\d{2}[A-Za-z]\d{2}[A-Za-z]\d{3}[A-Za-z]\b"  # CF
    r"|[\w.+-]+@[\w-]+\.[\w.]+"  # email
)
_PAROLE_UTILI = {
    "malattia",
    "protocollo",
    "certificato",
    "inps",
    "ferie",
    "rol",
    "permesso",
    "visita",
    "entrata",
    "uscita",
    "ritardo",
}
_INVISIBILI = re.compile(
    "[\N{ZERO WIDTH SPACE}\N{ZERO WIDTH NON-JOINER}"
    "\N{ZERO WIDTH JOINER}\N{ZERO WIDTH NO-BREAK SPACE}]"
)
_BORDI = " \t|\N{SINGLE RIGHT-POINTING ANGLE QUOTATION MARK}\N{MIDDLE DOT}\N{BULLET}"
_LETTERA = re.compile(r"[A-Za-zÀ-ÿ]")
_STRANO = re.compile(r"[^A-Za-zÀ-ÿ0-9\s:;,.@/'\"()\-]")


def pulisci_testo_ocr(testo: str, parole_rumore: Sequence[str] = ()) -> str:
    rumore = [normalizza(p) for p in parole_rumore if normalizza(p)]
    testo = (
        _INVISIBILI.sub("", testo.replace("\r", ""))
        .replace("\N{RIGHT SINGLE QUOTATION MARK}", "'")
        .replace("`", "'")
    )
    righe: list[str] = []
    for grezza in testo.split("\n"):
        riga = re.sub(r"[ \t]+", " ", grezza).strip(_BORDI)
        if not riga:
            if righe and righe[-1]:
                righe.append("")  # al massimo una riga vuota tra due paragrafi
            continue
        if not _disturbo(riga, rumore):
            righe.append(riga)
    return "\n".join(righe).strip()


def qualita_testo(testo: str) -> int:
    """Più alta = più testo leggibile; serve a scegliere il ritaglio migliore."""
    if not testo.strip():
        return -999
    righe = [riga for riga in testo.splitlines() if riga.strip()]
    significative = sum(1 for riga in righe if len(_LETTERA.findall(riga)) >= 4)
    return significative * 12 + len(_LETTERA.findall(testo)) // 12 - len(_STRANO.findall(testo)) * 3


def _disturbo(riga: str, rumore: Sequence[str]) -> bool:
    if _UTILI.search(riga):
        return False
    normalizzata = normalizza(riga)
    if set(normalizzata.split()) & _PAROLE_UTILI:
        return False
    lettere = len(_LETTERA.findall(riga))
    cifre = sum(c.isdigit() for c in riga)
    strani = len(_STRANO.findall(riga))
    return (
        riga.count("|") >= 2
        or bool(re.search(r"(?:\b[A-Za-zÀ-ÿ]\b[\s|/\\-]*){5,}", riga))
        or bool(re.search(r"[<>_=~]{3,}", riga))
        or (lettere < 3 and cifre == 0)
        or (strani > max(4, int(len(riga) * 0.18)) and lettere < 6)
        or (any(parola in normalizzata for parola in rumore) and lettere < 25)
    )
