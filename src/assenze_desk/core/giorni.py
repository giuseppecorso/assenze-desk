"""Giorni relativi alla data della mail: oggi, domani, lunedì, "martedì 13", "il 13".

Regole:
- oggi, domani, dopodomani, ieri (parole estendibili dal vocabolario);
- giorno della settimana da solo o con "prossimo": il primo dopo la data della
  mail (per il giorno stesso si scrive "oggi"); con "scorso": l'ultimo prima;
- "martedì 13": il primo 13 che cade di martedì, dalla data della mail compresa,
  entro circa sei mesi; "il 13", "giorno 13", "l'8": il primo giorno con quel
  numero, dalla data della mail compresa.
Le date con il mese ("lunedì 12 ottobre", "il 13/10") sono di date.py e qui si saltano.
"""

import re
from datetime import date, timedelta
from functools import cache

from assenze_desk.core.date import NOME_MESE
from assenze_desk.core.testo import senza_accenti
from assenze_desk.core.vocabolario import VOCABOLARIO, Vocabolario, alternative

GIORNI_SETTIMANA = ("lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica")
GIORNI_DI_RICERCA = 183  # per "martedì 13": circa sei mesi

# Dopo il numero del giorno viene il mese: è una data completa, non un giorno relativo
_SEGUE_UN_MESE = re.compile(rf"\s*(?:[/.-]\s*[0-9]|(?:{NOME_MESE})\b)")


def trova_giorni(
    testo: str, riferimento: date, vocabolario: Vocabolario = VOCABOLARIO
) -> list[date]:
    """Giorni relativi del testo, in ordine di comparsa e senza doppioni."""
    pulito = senza_accenti(testo)
    trovati: list[date] = []
    for corrispondenza in _regex(vocabolario).finditer(pulito):
        giorno = _giorno(corrispondenza, pulito, riferimento)
        if giorno and giorno not in trovati:
            trovati.append(giorno)
    return trovati


def _giorno(corrispondenza: re.Match[str], testo: str, riferimento: date) -> date | None:
    spostamenti = {"oggi": 0, "domani": 1, "dopodomani": 2, "ieri": -1}
    for parola, giorni in spostamenti.items():
        if corrispondenza[parola]:
            return riferimento + timedelta(days=giorni)

    numero = corrispondenza["numero"] or corrispondenza["solo_numero"]
    if numero and _SEGUE_UN_MESE.match(testo, corrispondenza.end()):
        return None
    if corrispondenza["solo_numero"]:
        return prossimo_giorno_del_mese(int(numero), riferimento)

    settimana = GIORNI_SETTIMANA.index(corrispondenza["settimana"])
    if numero:
        return _prossimo_con_numero(settimana, int(numero), riferimento)
    if corrispondenza["scorso_prima"] or corrispondenza["scorso_dopo"]:
        return riferimento - timedelta(days=(riferimento.weekday() - settimana) % 7 or 7)
    return riferimento + timedelta(days=(settimana - riferimento.weekday()) % 7 or 7)


def _prossimo_con_numero(settimana: int, numero: int, riferimento: date) -> date | None:
    for avanti in range(GIORNI_DI_RICERCA):
        giorno = riferimento + timedelta(days=avanti)
        if giorno.day == numero and giorno.weekday() == settimana:
            return giorno
    return None


def prossimo_giorno_del_mese(numero: int, riferimento: date) -> date | None:
    """Il primo giorno con quel numero, dal riferimento compreso ("il 13", "il 31")."""
    anno, mese = riferimento.year, riferimento.month
    for _ in range(13):
        try:
            giorno = date(anno, mese, numero)
        except ValueError:
            giorno = None  # il 31 in un mese di 30 giorni, il 40...
        if giorno and giorno >= riferimento:
            return giorno
        anno, mese = (anno + 1, 1) if mese == 12 else (anno, mese + 1)
    return None


@cache
def _regex(vocabolario: Vocabolario) -> re.Pattern[str]:
    settimana = "|".join(GIORNI_SETTIMANA)
    return re.compile(
        rf"""
        (?<![0-9a-z'])
        (?:
            (?P<dopodomani>{alternative(vocabolario.dopodomani)})
          | (?P<domani>{alternative(vocabolario.domani)})
          | (?P<oggi>{alternative(vocabolario.oggi)})
          | (?P<ieri>{alternative(vocabolario.ieri)})
          | # lunedì, lunedì 13, lunedì prossimo, lo scorso lunedì, lunedì scorso
            (?:(?P<scorso_prima>scors[oa])\s+)?
            (?P<settimana>{settimana})'?
            (?:\s+(?P<numero>[0-9]{{1,2}})(?![0-9])|\s+(?P<scorso_dopo>scors[oa]))?
          | # il 13, giorno 13, l'8
            (?:(?:il|giorno)\s+|l')(?P<solo_numero>[0-9]{{1,2}})(?![0-9])
        )
        (?![0-9a-z])
        """,
        re.VERBOSE,
    )
