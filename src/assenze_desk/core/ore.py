"""Durate dei permessi: "2 ore e 30 minuti", "1h30", "un'ora e mezza", "90 minuti".

Il risultato è in minuti interi, così le somme non hanno errori di arrotondamento;
in ore si mostra solo nell'interfaccia. Meglio vuoto che sbagliato:
- "1.30 ore" non si legge: può essere 1 ora e 30 o 1,3 ore ("2,5" e "2.5" sì);
- durate oltre le 24 ore ("contratto di 40 ore") non sono permessi;
- più durate diverse nello stesso testo: sceglie l'utente.
Fasce orarie e orari spostati non sono qui (issue #15).
"""

import re
from decimal import Decimal

from assenze_desk.core.testo import senza_accenti

_NUMERI_IN_LETTERE = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "due": 2,
    "tre": 3,
    "quattro": 4,
    "cinque": 5,
    "sei": 6,
    "sette": 7,
    "otto": 8,
    "nove": 9,
    "dieci": 10,
    "undici": 11,
    "dodici": 12,
}
_FRAZIONI = {"mezza": 30, "mezzo": 30, "un quarto": 15, "tre quarti": 45}
_SOLE_FRAZIONI = {"mezz": 30, "mezza": 30, "un quarto": 15, "tre quarti": 45}
MASSIMO_MINUTI = 24 * 60

_PAROLE = "|".join(sorted(_NUMERI_IN_LETTERE, key=len, reverse=True))
_NUMERO = rf"(?:[0-9]{{1,2}}(?:,[0-9]{{1,2}}|\.[0-9])?|(?:{_PAROLE})\b)"
_SEP = r"\s*'?\s*"  # "un'ora", "un ora", "2ore"
_ORE = r"(?:ore|ora|h)\b"
_MIN = r"(?:minuti|minuto|min)\b"

_DURATA = re.compile(
    rf"""
    (?<![0-9a-z.,'])
    (?:
        # 2 ore e 30 minuti, 2 ore 30 min
        (?P<ore_a>{_NUMERO}){_SEP}{_ORE}\s*(?:e\s+)?(?P<min_a>[0-9]{{1,2}})\s*{_MIN}
      | # 1h30, 1h 30
        (?P<ore_b>[0-9]{{1,2}})h\s?(?P<min_b>[0-9]{{2}})\b
      | # 2 ore e mezza, 1 ora e un quarto
        (?P<ore_c>{_NUMERO}){_SEP}{_ORE}\s+e\s+(?P<frazione>mezza|mezzo|un\s+quarto|tre\s+quarti)\b
      | # mezz'ora, un quarto d'ora, tre quarti d'ora
        (?P<sola_frazione>mezz|mezza|un\s+quarto|tre\s+quarti)\s*(?:d\s*)?'?\s*ora\b
      | # 2 ore, 2,5 ore, un'ora, 2h
        (?P<ore_d>{_NUMERO}){_SEP}{_ORE}
      | # 90 minuti (solo in cifre: "un minuto" è un modo di dire)
        (?P<min_e>[0-9]{{1,3}})\s*{_MIN}
    )
    """,
    re.VERBOSE,
)


def trova_durate(testo: str) -> list[int]:
    """Tutte le durate valide del testo, in minuti, in ordine di comparsa."""
    durate = []
    for corrispondenza in _DURATA.finditer(senza_accenti(testo)):
        minuti = _in_minuti(corrispondenza.groupdict())
        if minuti is not None and 0 < minuti <= MASSIMO_MINUTI:
            durate.append(minuti)
    return durate


def leggi_durata(testo: str) -> int | None:
    """La durata in minuti, se nel testo ce n'è una sola (anche ripetuta)."""
    diverse = set(trova_durate(testo))
    return diverse.pop() if len(diverse) == 1 else None


def _in_minuti(parti: dict[str, str | None]) -> int | None:
    if parti["sola_frazione"]:
        return _SOLE_FRAZIONI[" ".join(parti["sola_frazione"].split())]
    if parti["min_e"]:
        return int(parti["min_e"])
    if parti["ore_b"]:
        ore, minuti = Decimal(parti["ore_b"]), int(parti["min_b"] or 0)
    elif parti["ore_a"]:
        ore, minuti = _ore(parti["ore_a"]), int(parti["min_a"] or 0)
    elif parti["ore_c"]:
        ore, minuti = _ore(parti["ore_c"]), _FRAZIONI[" ".join((parti["frazione"] or "").split())]
    else:
        ore, minuti = _ore(parti["ore_d"] or ""), 0

    if minuti >= 60:
        return None
    totale = ore * 60 + minuti
    return int(totale) if totale == int(totale) else None  # "2,33 ore" non sono minuti interi


def _ore(numero: str) -> Decimal:
    if numero in _NUMERI_IN_LETTERE:
        return Decimal(_NUMERI_IN_LETTERE[numero])
    return Decimal(numero.replace(",", "."))
