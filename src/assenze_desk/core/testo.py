"""Strumenti comuni per il testo delle mail."""

import re
import unicodedata

_APOSTROFI = str.maketrans(
    {"\N{RIGHT SINGLE QUOTATION MARK}": "'", "\N{LEFT SINGLE QUOTATION MARK}": "'"}
)


def senza_accenti(testo: str) -> str:
    """Minuscolo, senza accenti, apostrofi tipografici resi semplici; punteggiatura intatta."""
    scomposto = unicodedata.normalize("NFD", testo.lower().translate(_APOSTROFI))
    return "".join(c for c in scomposto if not unicodedata.combining(c))


def normalizza(testo: str) -> str:
    """Come `senza_accenti`, con un solo spazio al posto di punteggiatura e a capo.

    Serve a cercare parole chiave senza badare a come sono scritte:
    "Entrerò PIÙ tardi" e "entrero piu tardi" diventano uguali.
    """
    return " ".join(re.sub(r"[^0-9a-z]+", " ", senza_accenti(testo)).split())
