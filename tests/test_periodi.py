"""Periodi: "dal 12/10 al 16/10", "da lunedì a venerdì", "dal 5 al 9 ottobre" (#15, passo 3b).

Un periodo diventa l'elenco dei suoi giorni (una riga per giorno). I giorni di
weekend sono restituiti a parte: se includerli lo decide l'utente (D30).
"""

from datetime import date

import pytest

from assenze_desk.core.periodi import Periodo, trova_periodi
from assenze_desk.core.vocabolario import VOCABOLARIO

MERCOLEDI = date(2026, 10, 7)  # data della mail usata nei test


def estremi(testo, riferimento=MERCOLEDI, vocabolario=VOCABOLARIO):
    return [(p.inizio, p.fine) for p in trova_periodi(testo, riferimento, vocabolario)]


@pytest.mark.parametrize(
    ("testo", "inizio", "fine"),
    [
        ("ferie dal 12/10 al 16/10", date(2026, 10, 12), date(2026, 10, 16)),
        ("dal 12/10/2026 al 18/10/2026", date(2026, 10, 12), date(2026, 10, 18)),
        ("dal 5 al 9 ottobre", date(2026, 10, 5), date(2026, 10, 9)),
        ("dal 12 fino al 14 ottobre", date(2026, 10, 12), date(2026, 10, 14)),
        ("dal 30 al 2 novembre", date(2026, 10, 30), date(2026, 11, 2)),
        ("dal 31 al 30 novembre", date(2026, 10, 31), date(2026, 11, 30)),
        ("dal 30 al 2 gennaio", date(2026, 12, 30), date(2027, 1, 2)),
        ("dal 28 dicembre al 3 gennaio", date(2026, 12, 28), date(2027, 1, 3)),
        ("dal 28/12 al 03/01", date(2026, 12, 28), date(2027, 1, 3)),
        ("da lunedì a venerdì", date(2026, 10, 12), date(2026, 10, 16)),
        ("da lunedì 12 a venerdì 16", date(2026, 10, 12), date(2026, 10, 16)),
        ("da lunedì 12 ottobre a venerdì 16 ottobre", date(2026, 10, 12), date(2026, 10, 16)),
        ("da oggi a venerdì", date(2026, 10, 7), date(2026, 10, 9)),
        ("da domani a lunedì", date(2026, 10, 8), date(2026, 10, 12)),
        ("dall'8 al 12", date(2026, 10, 8), date(2026, 10, 12)),
        ("dal 12/10 all'11/11", date(2026, 10, 12), date(2026, 11, 11)),
    ],
)
def test_periodo(testo, inizio, fine):
    assert estremi(testo) == [(inizio, fine)]


def test_giorni_lavorativi_e_weekend_separati():
    periodo = Periodo(date(2026, 10, 8), date(2026, 10, 12))  # da giovedì a lunedì
    assert periodo.giorni == [date(2026, 10, d) for d in (8, 9, 10, 11, 12)]
    assert periodo.lavorativi == [date(2026, 10, 8), date(2026, 10, 9), date(2026, 10, 12)]
    assert periodo.weekend == [date(2026, 10, 10), date(2026, 10, 11)]


def test_periodo_di_un_giorno():
    assert Periodo(date(2026, 10, 12), date(2026, 10, 12)).giorni == [date(2026, 10, 12)]


def test_piu_periodi_in_ordine():
    testo = "ferie dal 12/10 al 16/10 e dal 2/11 al 6/11"
    assert estremi(testo) == [
        (date(2026, 10, 12), date(2026, 10, 16)),
        (date(2026, 11, 2), date(2026, 11, 6)),
    ]


@pytest.mark.parametrize(
    "testo",
    [
        "dal 16/10 al 12/10",  # la fine viene prima dell'inizio
        "dal 31/02 al 05/03",  # giorno inesistente
        "dal 31 al 2 dicembre",  # il 31 novembre non esiste: non si torna indietro di due mesi
        "dal 1/1/2026 al 1/1/2028",  # più lungo di un anno
        "dalle 9 alle 11",  # fascia oraria, non periodo
        "da casa al lavoro",
        "dal 12/10",  # manca la fine
        "",
    ],
)
def test_nessun_periodo(testo):
    assert estremi(testo) == []


def test_parole_aggiunte_dalle_impostazioni():
    testo = "ferie tra il 12/10 e il 16/10"
    assert estremi(testo) == []
    esteso = VOCABOLARIO.estendi(inizio_periodo=["tra il"], fine_periodo=["e il"])
    assert estremi(testo, vocabolario=esteso) == [(date(2026, 10, 12), date(2026, 10, 16))]


def test_periodo_non_valido():
    with pytest.raises(ValueError):
        Periodo(date(2026, 10, 16), date(2026, 10, 12))
