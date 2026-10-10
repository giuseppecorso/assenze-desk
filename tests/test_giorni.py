"""Giorni relativi alla data della mail (issue #15, passo 2).

Regole (D28): un giorno della settimana da solo o con "prossimo" è il primo dopo la
data della mail; con "scorso" è l'ultimo prima; "martedì 13" e "il 13" sono il primo
giorno 13 a partire dalla data della mail (compresa). Le date con il mese ("lunedì
12 ottobre", "il 13/10") sono di date.py.
"""

from datetime import date

import pytest

from assenze_desk.core.giorni import trova_giorni
from assenze_desk.core.vocabolario import VOCABOLARIO

MERCOLEDI = date(2026, 10, 7)  # data della mail usata nei test


def giorni(testo, riferimento=MERCOLEDI, vocabolario=VOCABOLARIO):
    return trova_giorni(testo, riferimento, vocabolario)


@pytest.mark.parametrize(
    ("testo", "atteso"),
    [
        ("oggi", date(2026, 10, 7)),
        ("stamattina esco prima", date(2026, 10, 7)),
        ("stasera", date(2026, 10, 7)),
        ("domani", date(2026, 10, 8)),
        ("Domattina entro alle 10", date(2026, 10, 8)),
        ("dopodomani", date(2026, 10, 9)),
        ("ieri", date(2026, 10, 6)),
    ],
)
def test_parole_relative(testo, atteso):
    assert giorni(testo) == [atteso]


@pytest.mark.parametrize(
    ("testo", "atteso"),
    [
        ("lunedì", date(2026, 10, 12)),
        ("lunedi", date(2026, 10, 12)),
        ("LUNEDÌ", date(2026, 10, 12)),
        ("lunedi'", date(2026, 10, 12)),  # accento scritto come apostrofo
        ("giovedì", date(2026, 10, 8)),
        ("sabato", date(2026, 10, 10)),
        ("domenica", date(2026, 10, 11)),
        ("mercoledì", date(2026, 10, 14)),  # stesso giorno della mail: la settimana dopo
        ("lunedì prossimo", date(2026, 10, 12)),
        ("il prossimo lunedì", date(2026, 10, 12)),
    ],
)
def test_giorno_della_settimana(testo, atteso):
    assert giorni(testo) == [atteso]


@pytest.mark.parametrize(
    ("testo", "atteso"),
    [
        ("lunedì scorso", date(2026, 10, 5)),
        ("lo scorso venerdì", date(2026, 10, 2)),
        ("mercoledì scorso", date(2026, 9, 30)),
        ("la scorsa domenica", date(2026, 10, 4)),
    ],
)
def test_giorno_della_settimana_passato(testo, atteso):
    assert giorni(testo) == [atteso]


@pytest.mark.parametrize(
    ("testo", "atteso"),
    [
        ("martedì 13", date(2026, 10, 13)),
        ("venerdì 16 dalle 9 alle 11", date(2026, 10, 16)),
        ("mercoledì 7", date(2026, 10, 7)),  # il giorno stesso della mail è compreso
        ("il 13", date(2026, 10, 13)),
        ("giorno 7", date(2026, 10, 7)),
        ("il 5", date(2026, 11, 5)),  # il 5 ottobre è già passato
        ("l'8", date(2026, 10, 8)),
        ("l’11", date(2026, 10, 11)),
    ],
)
def test_giorno_del_mese(testo, atteso):
    assert giorni(testo) == [atteso]


def test_giorno_del_mese_che_non_esiste_in_tutti_i_mesi():
    assert giorni("il 31", riferimento=date(2026, 11, 10)) == [date(2026, 12, 31)]


@pytest.mark.parametrize(
    "testo",
    [
        "martedì 14",  # nei prossimi mesi nessun 14 cade di martedì
        "il 40",
        "lunedì 32",
        "lunedì 12 ottobre",  # data con il mese: è di date.py
        "il 13 gennaio 2026",
        "il 13/10",
        "il 13.10.2026",
        "soggiorno",  # "oggi" dentro un'altra parola
        "domaniale",
        "",
    ],
)
def test_nessun_giorno(testo):
    assert giorni(testo) == []


def test_piu_giorni_in_ordine_e_senza_doppioni():
    assert giorni("da lunedì a mercoledì") == [date(2026, 10, 12), date(2026, 10, 14)]
    assert giorni("domani e dopodomani") == [date(2026, 10, 8), date(2026, 10, 9)]
    assert giorni("domani, cioè giovedì") == [date(2026, 10, 8)]


def test_parole_aggiunte_dalle_impostazioni():
    esteso = VOCABOLARIO.estendi(oggi=["in giornata"])
    assert giorni("esco in giornata") == []
    assert giorni("esco in giornata", vocabolario=esteso) == [MERCOLEDI]
