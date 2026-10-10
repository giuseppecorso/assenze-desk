"""Periodi: "dal 12/10 al 16/10", "da lunedì a venerdì", "dal 5 al 9 ottobre".

Ognuno dei due estremi può essere scritto in tutti i modi che il core conosce:
data completa (date.py), giorno relativo (giorni.py) o numero da solo. Un numero
da solo prende mese e anno dall'altro estremo ("dal 5 al 9 ottobre"); se è da
solo anche l'altro, vale la regola di "il 13". Un giorno della settimana come
fine si conta dall'inizio del periodo: "da domani a lunedì" arriva al lunedì dopo
domani.

Il periodo diventa l'elenco dei giorni; i giorni di weekend sono a parte, perché
se includerli lo decide l'utente (D30). Meglio vuoto che sbagliato: niente periodi
che finiscono prima di iniziare o più lunghi di un anno.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache

from assenze_desk.core.date import NOME_MESE, leggi_data
from assenze_desk.core.giorni import GIORNI_SETTIMANA, prossimo_giorno_del_mese, trova_giorni
from assenze_desk.core.testo import senza_accenti
from assenze_desk.core.vocabolario import VOCABOLARIO, Vocabolario, alternative

MASSIMO_GIORNI = 366

_SETTIMANA = "|".join(GIORNI_SETTIMANA)
_SOLO_SETTIMANA = re.compile(rf"(?:{_SETTIMANA})'?")
_PREFISSO_SETTIMANA = re.compile(rf"(?:{_SETTIMANA})'?\s+(?=[0-9])")
_NUMERO_DA_SOLO = re.compile(r"([0-3]?[0-9])[°º]?")


@dataclass(frozen=True)
class Periodo:
    inizio: date
    fine: date

    def __post_init__(self) -> None:
        if self.fine < self.inizio:
            raise ValueError("il periodo finisce prima di iniziare")

    @property
    def giorni(self) -> list[date]:
        return [self.inizio + timedelta(days=n) for n in range((self.fine - self.inizio).days + 1)]

    @property
    def lavorativi(self) -> list[date]:
        return [giorno for giorno in self.giorni if giorno.weekday() < 5]

    @property
    def weekend(self) -> list[date]:
        return [giorno for giorno in self.giorni if giorno.weekday() >= 5]


def trova_periodi(
    testo: str,
    riferimento: date,
    vocabolario: Vocabolario = VOCABOLARIO,
    giorni_avanti: int = 0,
) -> list[Periodo]:
    """Periodi del testo, in ordine di comparsa."""
    periodi = []
    for corrispondenza in _regex(vocabolario).finditer(senza_accenti(testo)):
        inizio = _estremo(corrispondenza["inizio"], riferimento, vocabolario, giorni_avanti)
        # Un giorno della settimana come fine si conta dall'inizio del periodo
        riferimento_fine = riferimento
        if isinstance(inizio, date) and _SOLO_SETTIMANA.fullmatch(corrispondenza["fine"]):
            riferimento_fine = inizio - timedelta(days=1)
        fine = _estremo(corrispondenza["fine"], riferimento_fine, vocabolario, giorni_avanti)

        if isinstance(inizio, int) and isinstance(fine, int):
            inizio = prossimo_giorno_del_mese(inizio, riferimento)
        if isinstance(fine, int):
            fine = prossimo_giorno_del_mese(fine, inizio) if isinstance(inizio, date) else None
        if isinstance(inizio, int):
            inizio = _stesso_numero_prima(inizio, fine) if fine else None

        if inizio and fine and inizio <= fine and (fine - inizio).days <= MASSIMO_GIORNI:
            periodi.append(Periodo(inizio, fine))
    return periodi


def togli_periodi(testo: str, vocabolario: Vocabolario = VOCABOLARIO) -> str:
    """Il testo (senza accenti) con i periodi coperti da spazi.

    Serve a non rileggere gli estremi come giorni singoli: in "da lunedì a venerdì"
    il venerdì non è quello di questa settimana.
    """
    return _regex(vocabolario).sub(lambda c: " " * len(c.group()), senza_accenti(testo))


def _estremo(
    scritto: str, riferimento: date, vocabolario: Vocabolario, giorni_avanti: int
) -> date | int | None:
    """Data dell'estremo, oppure il numero del giorno se è scritto da solo."""
    prefisso = _PREFISSO_SETTIMANA.match(scritto)
    senza_settimana = scritto[prefisso.end() :] if prefisso else scritto
    if data := leggi_data(senza_settimana, riferimento, giorni_avanti):
        return data
    if not prefisso and (numero := _NUMERO_DA_SOLO.fullmatch(scritto)):
        return int(numero[1])
    trovati = trova_giorni(scritto, riferimento, vocabolario)
    return trovati[0] if trovati else None


def _stesso_numero_prima(numero: int, fine: date) -> date | None:
    """Il giorno con quel numero nel mese della fine o, se non va, nel mese prima.

    "dal 30 al 2 novembre" = dal 30 ottobre; "dal 31 al 2 dicembre" non si legge
    (il 31 novembre non esiste): meglio vuoto che tornare indietro di due mesi.
    """
    mese_prima = (fine.year - 1, 12) if fine.month == 1 else (fine.year, fine.month - 1)
    for anno, mese in ((fine.year, fine.month), mese_prima):
        try:
            giorno = date(anno, mese, numero)
        except ValueError:
            continue
        if giorno <= fine:
            return giorno
    return None


@cache
def _regex(vocabolario: Vocabolario) -> re.Pattern[str]:
    relativi = alternative(
        vocabolario.oggi + vocabolario.domani + vocabolario.dopodomani + vocabolario.ieri
    )
    numerica = r"[0-3]?[0-9][/.-][01]?[0-9](?:[/.-](?:19|20)?[0-9]{2})?"
    con_mese = rf"[0-3]?[0-9][°º]?\s+(?:{NOME_MESE})\b\.?(?:\s+(?:19|20)[0-9]{{2}})?"
    estremo = (
        rf"(?:(?:{_SETTIMANA})'?\s+)?(?:{numerica}|{con_mese}|[0-3]?[0-9][°º]?)(?![0-9])"
        rf"|(?:{_SETTIMANA})'?|(?:{relativi})"
    )
    # Dopo "dall'" il giorno segue subito; dopo "dal" serve uno spazio ("dalle" non è "dal")
    separatore = r"(?:(?<=')|\s+)"
    return re.compile(
        rf"(?<![0-9a-z'])(?:{alternative(vocabolario.inizio_periodo)}){separatore}"
        rf"(?P<inizio>{estremo})"
        rf"\s+(?:{alternative(vocabolario.fine_periodo)}){separatore}"
        rf"(?P<fine>{estremo})(?![0-9a-z])"
    )
