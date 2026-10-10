"""Vocabolario dei permessi: le parole con cui le mail esprimono ore e orari.

Ci sono parole predefinite, scelte tra le più comuni; dalle impostazioni se ne
possono aggiungere altre con `estendi`, senza toccare il codice. Maiuscole e
accenti non contano ("anziché" vale anche per "anziche").
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, fields, replace
from functools import cache

from assenze_desk.core.testo import senza_accenti


@dataclass(frozen=True)
class Vocabolario:
    unita_ore: tuple[str, ...] = ("ore", "ora", "h")
    unita_minuti: tuple[str, ...] = ("minuti", "minuto", "min")
    # "dalle 9 alle 11", "tra le 9 e le 11"
    inizio_fascia: tuple[str, ...] = ("dalle", "tra le", "fra le")
    fine_fascia: tuple[str, ...] = ("alle", "fino alle", "e le", "a")
    # "esco alle 16 anziché alle 18"
    invece: tuple[str, ...] = (
        "anziché",
        "invece che",
        "invece di",
        "invece",
        "al posto di",
        "al posto",
        "e non",
    )
    # Giorni relativi alla data della mail
    oggi: tuple[str, ...] = ("oggi", "stamattina", "stamani", "stamane", "stasera")
    domani: tuple[str, ...] = ("domani", "domattina")
    dopodomani: tuple[str, ...] = ("dopodomani",)
    ieri: tuple[str, ...] = ("ieri",)

    def __post_init__(self) -> None:
        for campo in fields(self):
            parole = getattr(self, campo.name)
            if not parole or any(not senza_accenti(parola).strip() for parola in parole):
                raise ValueError(f"parole non valide in {campo.name}: servono parole non vuote")

    def estendi(self, **aggiunte: Iterable[str]) -> Vocabolario:
        """Nuovo vocabolario con le parole aggiunte in coda, senza doppioni."""
        sconosciuti = set(aggiunte) - {campo.name for campo in fields(self)}
        if sconosciuti:
            raise TypeError(f"voci del vocabolario sconosciute: {sorted(sconosciuti)}")
        return replace(
            self,
            **{
                campo: tuple(dict.fromkeys((*getattr(self, campo), *parole)))
                for campo, parole in aggiunte.items()
            },
        )


VOCABOLARIO = Vocabolario()


@cache
def alternative(parole: tuple[str, ...]) -> str:
    """Regex che trova una delle parole (le più lunghe prima), spazi flessibili."""
    pulite = sorted({senza_accenti(parola).strip() for parola in parole}, key=len, reverse=True)
    return "|".join(re.escape(parola).replace(r"\ ", r"\s+") for parola in pulite)
