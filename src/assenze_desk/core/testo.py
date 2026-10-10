"""Strumenti comuni per il testo delle mail."""

import re
import unicodedata


def normalizza(testo: str) -> str:
    """Minuscolo, senza accenti, con un solo spazio al posto di punteggiatura e a capo.

    Serve a cercare parole chiave senza badare a come sono scritte:
    "Entrerò PIÙ tardi" e "entrero piu tardi" diventano uguali.
    """
    scomposto = unicodedata.normalize("NFD", testo.lower())
    senza_accenti = "".join(c for c in scomposto if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", senza_accenti).split())
