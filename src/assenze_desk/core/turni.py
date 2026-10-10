"""Turno del cliente e parti della giornata ("mattina", "pomeriggio", "tutto il giorno").

Una parte della giornata nel testo propone le ore della parte di turno
corrispondente: è una proposta che l'utente conferma. Senza turno, o se il turno
non ha quella parte, non si propone niente.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from functools import cache
from typing import Literal, cast

from assenze_desk.core.orari import Intervallo
from assenze_desk.core.testo import senza_accenti
from assenze_desk.core.vocabolario import VOCABOLARIO, Vocabolario, alternative

Parte = Literal["mattina", "pomeriggio", "giornata"]


@dataclass(frozen=True)
class Turno:
    """Orari di lavoro del cliente; una delle due parti può mancare (part time)."""

    mattina: Intervallo | None = None
    pomeriggio: Intervallo | None = None

    def __post_init__(self) -> None:
        parti = [parte for parte in (self.mattina, self.pomeriggio) if parte]
        if not parti:
            raise ValueError("il turno deve avere almeno una parte")
        if any(parte.inizio >= parte.fine for parte in parti):
            raise ValueError("ogni parte del turno deve finire dopo l'inizio")
        if self.mattina and self.pomeriggio and self.mattina.fine > self.pomeriggio.inizio:
            raise ValueError("la mattina deve finire prima che inizi il pomeriggio")


@dataclass(frozen=True)
class OrarioSettimanale:
    """Minuti di lavoro del cliente per ogni giorno, da lunedì a domenica (0 = non lavora)."""

    minuti: tuple[int, ...]  # 7 valori, controllati qui sotto

    def __post_init__(self) -> None:
        if len(self.minuti) != 7 or any(not 0 <= m <= 24 * 60 for m in self.minuti):
            raise ValueError("servono 7 valori, da 0 a 1440 minuti")

    @classmethod
    def da_turno(
        cls, turno: Turno, giorni_lavorativi: Sequence[int] = range(5)
    ) -> OrarioSettimanale:
        """Lo stesso turno nei giorni lavorativi (di default da lunedì a venerdì)."""
        giornata = minuti_parte("giornata", turno) or 0
        return cls(tuple(giornata if g in giorni_lavorativi else 0 for g in range(7)))

    def minuti_del_giorno(self, giorno: date) -> int | None:
        return self.minuti[giorno.weekday()] or None


def trova_parti_giornata(testo: str, vocabolario: Vocabolario = VOCABOLARIO) -> list[Parte]:
    """Parti della giornata citate nel testo, in ordine e senza doppioni."""
    parti: list[Parte] = []
    for corrispondenza in _regex(vocabolario).finditer(senza_accenti(testo)):
        parte = cast(Parte, corrispondenza.lastgroup)  # il nome del gruppo è la parte
        if parte not in parti:
            parti.append(parte)
    return parti


def minuti_parte(parte: Parte, turno: Turno | None) -> int | None:
    """Minuti proposti per la parte di giornata, oppure None se il turno non li dà."""
    if turno is None:
        return None
    scelte = {
        "mattina": [turno.mattina],
        "pomeriggio": [turno.pomeriggio],
        "giornata": [turno.mattina, turno.pomeriggio],
    }[parte]
    presenti = [intervallo for intervallo in scelte if intervallo]
    return sum(intervallo.minuti for intervallo in presenti) if presenti else None


@cache
def _regex(vocabolario: Vocabolario) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![0-9a-z])(?:"
        rf"(?P<giornata>{alternative(vocabolario.giornata_intera)})"
        rf"|(?P<mattina>{alternative(vocabolario.mattina)})"
        rf"|(?P<pomeriggio>{alternative(vocabolario.pomeriggio)})"
        rf")(?![0-9a-z])"
    )
