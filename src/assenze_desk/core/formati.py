"""Come si mostrano e si leggono date e ore nei campi dell'interfaccia e nelle mail."""

import re
from collections.abc import Sequence
from datetime import date, timedelta

from assenze_desk.core.date import leggi_elenco_date
from assenze_desk.core.ore import leggi_durata

GIORNI_BREVI = ("lun", "mar", "mer", "gio", "ven", "sab", "dom")
_ORE_E_MINUTI = re.compile(r"(\d{1,2})(?:[:.](\d{2}))?")
MINIMO_GIORNI_DI_FILA = 3  # da tre giorni consecutivi in su: "dal ... al ..."


def data(giorno: date | None) -> str:
    return f"{giorno:%d/%m/%Y}" if giorno else ""


def giorno_breve(giorno: date) -> str:
    return f"{GIORNI_BREVI[giorno.weekday()]} {giorno:%d/%m}"


def ore(minuti: int | None) -> str:
    """Minuti come ore e minuti: 90 → "1:30"."""
    if minuti is None:
        return ""
    return f"{minuti // 60}:{minuti % 60:02d}"


def leggi_ore(testo: str) -> int | None:
    """Ore scritte a mano in un campo: "8", "1:30", "1.30" oppure come nelle mail ("2 ore")."""
    pulito = testo.strip()
    if trovato := _ORE_E_MINUTI.fullmatch(pulito):
        ore_scritte, minuti = int(trovato[1]), int(trovato[2] or 0)
        totale = ore_scritte * 60 + minuti
        return totale if minuti < 60 and 0 < totale <= 24 * 60 else None
    return leggi_durata(pulito) if pulito else None


def leggi_giorni(testo: str, riferimento: date) -> tuple[date, ...] | None:
    """Date scritte a mano, separate da virgole o spazi; senza anno vale la più vicina.

    None se una parte non è una data: nel campo compare l'avviso.
    """
    lette = leggi_elenco_date(testo, riferimento)
    return None if lette is None else tuple(sorted(set(lette)))


def elenco_giorni(giorni: Sequence[date]) -> str:
    """ "09/10/2026 e dal 12/10/2026 al 16/10/2026": i giorni di fila si riassumono."""
    pezzi = []
    for gruppo in _di_fila(sorted(set(giorni))):
        if len(gruppo) >= MINIMO_GIORNI_DI_FILA:
            pezzi.append(f"dal {data(gruppo[0])} al {data(gruppo[-1])}")
        else:
            pezzi += [data(giorno) for giorno in gruppo]
    if len(pezzi) <= 1:
        return "".join(pezzi)
    return f"{', '.join(pezzi[:-1])} e {pezzi[-1]}"


def durata_in_parole(minuti: int | None) -> str:
    if minuti is None:
        return ""
    ore_intere, resto = divmod(minuti, 60)
    parti = []
    if ore_intere:
        parti.append("1 ora" if ore_intere == 1 else f"{ore_intere} ore")
    if resto:
        parti.append(f"{resto} minuti")
    return " e ".join(parti)


def _di_fila(giorni: list[date]) -> list[list[date]]:
    gruppi: list[list[date]] = []
    for giorno in giorni:
        if gruppi and giorno - gruppi[-1][-1] == timedelta(days=1):
            gruppi[-1].append(giorno)
        else:
            gruppi.append([giorno])
    return gruppi
