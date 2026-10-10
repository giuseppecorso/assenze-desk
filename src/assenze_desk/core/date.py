"""Date scritte esplicitamente: "05/01/2026", "5-1-26", "2026-01-05", "5 gennaio 2026".

Meglio vuoto che sbagliato: una data che non si riesce a leggere dà None, mai la
data di oggi. Il core non legge l'orologio: la data di riferimento (di solito
quella della mail) arriva come argomento e serve solo quando manca l'anno.

Anno mancante: si sceglie l'anno che porta la data più vicina al riferimento.
`giorni_avanti` sposta in avanti il riferimento, per i testi che parlano di date
future (per esempio ferie chieste mesi prima). Senza anno vale solo la barra
("05/01"): con punto o trattino "9.30" sarebbe un orario, non il 9 marzo.

Le espressioni relative (oggi, domani, lunedì prossimo) sono fuori da questo modulo.
"""

import re
from datetime import date, timedelta

_MESI = {
    "gen": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "mag": 5,
    "giu": 6,
    "lug": 7,
    "ago": 8,
    "set": 9,
    "ott": 10,
    "nov": 11,
    "dic": 12,
}
_NOME_MESE = (
    r"gen(?:naio)?|feb(?:braio)?|mar(?:zo)?|apr(?:ile)?|mag(?:gio)?|giu(?:gno)?"
    r"|lug(?:lio)?|ago(?:sto)?|set(?:t(?:embre)?)?|ott(?:obre)?|nov(?:embre)?|dic(?:embre)?"
)

_DATA = re.compile(
    rf"""
    (?<![0-9])
    (?:
        # ISO: 2026-01-05
        (?P<iso_anno>(?:19|20)[0-9]{{2}})-(?P<iso_mese>[01]?[0-9])-(?P<iso_giorno>[0-3]?[0-9])
      |
        # Numeri: 05/01/2026, 5.1.26, 05-01-2026, 05/01 (stesso separatore)
        (?P<giorno>[0-3]?[0-9])(?P<sep>[/.-])(?P<mese>[01]?[0-9])
        (?:(?P=sep)(?P<anno>(?:19|20)?[0-9]{{2}}))?
      |
        # Mese in lettere: 5 gennaio 2026, 1° marzo, 5 gen. 2026
        (?P<giorno_l>[0-3]?[0-9])[°º]?\s+(?P<mese_l>{_NOME_MESE})\b\.?
        (?:\s+(?P<anno_l>(?:19|20)[0-9]{{2}})\b)?
    )
    (?![0-9]|[/.-][0-9])
    """,
    re.IGNORECASE | re.VERBOSE,
)


def leggi_data(valore: str, riferimento: date | None = None, giorni_avanti: int = 0) -> date | None:
    """Il valore deve contenere solo la data, a parte gli spazi intorno."""
    trovata = _DATA.fullmatch(valore.strip())
    return _converti(trovata, riferimento, giorni_avanti) if trovata else None


def trova_date(testo: str, riferimento: date | None = None, giorni_avanti: int = 0) -> list[date]:
    """Tutte le date leggibili del testo, in ordine e senza doppioni."""
    trovate: list[date] = []
    for corrispondenza in _DATA.finditer(testo):
        data = _converti(corrispondenza, riferimento, giorni_avanti)
        if data and data not in trovate:
            trovate.append(data)
    return trovate


def _converti(trovata: re.Match[str], riferimento: date | None, giorni_avanti: int) -> date | None:
    parti = trovata.groupdict()
    if parti["iso_anno"]:
        return _data_sicura(
            int(parti["iso_anno"]), int(parti["iso_mese"]), int(parti["iso_giorno"])
        )

    if parti["mese_l"]:
        giorno, mese = int(parti["giorno_l"]), _MESI[parti["mese_l"][:3].lower()]
        anno = parti["anno_l"]
    else:
        giorno, mese, anno = int(parti["giorno"]), int(parti["mese"]), parti["anno"]
        if anno is None and parti["sep"] != "/":
            return None  # "9.30" e "1-2" non sono date

    if anno is None:
        return _anno_piu_vicino(giorno, mese, riferimento, giorni_avanti)
    anno_intero = int(anno) + 2000 if len(anno) == 2 else int(anno)
    return _data_sicura(anno_intero, mese, giorno)


def _anno_piu_vicino(
    giorno: int, mese: int, riferimento: date | None, giorni_avanti: int
) -> date | None:
    if riferimento is None:
        return None  # mai la data di sistema come ripiego
    centro = riferimento + timedelta(days=giorni_avanti)
    candidati = [
        data
        for anno in (centro.year - 1, centro.year, centro.year + 1)
        if (data := _data_sicura(anno, mese, giorno))
    ]
    return min(candidati, key=lambda data: (abs((data - centro).days), data), default=None)


def _data_sicura(anno: int, mese: int, giorno: int) -> date | None:
    """La data, oppure None se non esiste (31 febbraio, mese 13, giorno 0)."""
    try:
        return date(anno, mese, giorno)
    except ValueError:
        return None
