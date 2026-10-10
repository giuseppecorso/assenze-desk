"""Fasce orarie e orari spostati nei permessi.

- Fascia: "dalle 9 alle 11", "tra le 9 e le 10:30", "dalle ore 14 alle ore 18".
- Orario spostato: "esco alle 16 anziché alle 18", "entro alle 10:30 invece che
  alle 9". Vale come la fascia tra i due orari: l'assenza va dalle 16 alle 18.

Le parole (dalle, alle, anziché, ...) vengono dal vocabolario, estendibile dalle
impostazioni. Meglio vuoto che sbagliato: una fascia che finisce prima di
iniziare o un orario inesistente non si leggono; senza "alle" davanti, due
numeri con "invece" in mezzo non sono orari ("2 figli invece di 3").
"""

import re
from dataclasses import dataclass
from datetime import time
from functools import cache

from assenze_desk.core.testo import senza_accenti
from assenze_desk.core.vocabolario import VOCABOLARIO, Vocabolario, alternative

_ARTICOLI = r"alle|alla|delle|della|dalle|le"


@dataclass(frozen=True)
class Intervallo:
    inizio: time
    fine: time

    @property
    def minuti(self) -> int:
        return (self.fine.hour - self.inizio.hour) * 60 + self.fine.minute - self.inizio.minute


def trova_intervalli(testo: str, vocabolario: Vocabolario = VOCABOLARIO) -> list[Intervallo]:
    """Fasce e orari spostati del testo, in ordine di comparsa."""
    trovati = []
    for corrispondenza in _regex(vocabolario).finditer(senza_accenti(testo)):
        if corrispondenza["f1_ora"] is not None:
            inizio, fine = _orario(corrispondenza, "f1"), _orario(corrispondenza, "f2")
        else:
            inizio, fine = sorted((_orario(corrispondenza, "s1"), _orario(corrispondenza, "s2")))
        if inizio < fine:
            trovati.append(Intervallo(inizio, fine))
    return trovati


def _orario(corrispondenza: re.Match[str], nome: str) -> time:
    return time(int(corrispondenza[f"{nome}_ora"]), int(corrispondenza[f"{nome}_min"] or 0))


@cache
def _regex(vocabolario: Vocabolario) -> re.Pattern[str]:
    unita = alternative(vocabolario.unita_ore)

    def orario(nome: str) -> str:
        # "9", "09:30", "9.30", "9,30", "9h30", "ore 9", "h9", "9h"
        return (
            rf"(?:(?:{unita})\s*)?"
            rf"(?P<{nome}_ora>2[0-3]|[01]?[0-9])"
            rf"(?:(?:[:.,]|h)\s?(?P<{nome}_min>[0-5][0-9]))?"
            rf"(?:\s*(?:{unita})\b)?"
            r"(?![0-9])"
        )

    fascia = (
        rf"(?:{alternative(vocabolario.inizio_fascia)})\s*{orario('f1')}"
        rf"\s*(?:{alternative(vocabolario.fine_fascia)})\s*{orario('f2')}"
    )
    spostato = (
        rf"(?:{_ARTICOLI})\s+{orario('s1')}\s*,?\s*(?:{alternative(vocabolario.invece)})"
        rf"\s*(?:(?:{_ARTICOLI})\s+)?{orario('s2')}"
    )
    return re.compile(rf"(?<![0-9a-z])(?:{fascia}|{spostato})")
