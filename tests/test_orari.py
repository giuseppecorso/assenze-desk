"""Fasce orarie e orari spostati (issue #15, passo 1).

Un orario spostato ("esco alle 16 anziché alle 18") vale come la fascia tra i due
orari: l'assenza va dalle 16 alle 18.
"""

from datetime import time

import pytest

from assenze_desk.core.orari import Intervallo, trova_intervalli
from assenze_desk.core.vocabolario import VOCABOLARIO


def intervalli(testo, vocabolario=VOCABOLARIO):
    return [(i.inizio, i.fine, i.minuti) for i in trova_intervalli(testo, vocabolario)]


# --- Fasce orarie ---


@pytest.mark.parametrize(
    ("testo", "inizio", "fine"),
    [
        ("chiedo un permesso dalle 9 alle 11", time(9), time(11)),
        ("dalle 9:00 alle 11:30", time(9), time(11, 30)),
        ("dalle 9.30 alle 11", time(9, 30), time(11)),
        ("dalle 9,30 alle 11", time(9, 30), time(11)),
        ("Dalle 08:30 Alle 10", time(8, 30), time(10)),
        ("dalle ore 14 alle ore 18", time(14), time(18)),
        ("dalle h 9 alle h 11", time(9), time(11)),
        ("dalle h9 alle h11", time(9), time(11)),
        ("dalle 9h alle 11h", time(9), time(11)),
        ("dalle 9h30 alle 11", time(9, 30), time(11)),
        ("tra le 9 e le 10:30", time(9), time(10, 30)),
        ("fra le 15 e le 17", time(15), time(17)),
        ("dalle 9 fino alle 12", time(9), time(12)),
        ("dalle 9 a 11", time(9), time(11)),
        ("dalle 9 alle 11 del 05/01/2026", time(9), time(11)),
    ],
)
def test_fascia(testo, inizio, fine):
    assert intervalli(testo) == [
        (inizio, fine, (fine.hour - inizio.hour) * 60 + fine.minute - inizio.minute)
    ]


# --- Orari spostati ---


@pytest.mark.parametrize(
    ("testo", "inizio", "fine"),
    [
        ("esco alle 16 anziché alle 18", time(16), time(18)),
        ("esco alle 16 anziche alle 18", time(16), time(18)),
        ("uscirò alle 16 invece che alle 18", time(16), time(18)),
        ("entro alle 10:30 invece che alle 9", time(9), time(10, 30)),
        ("entrerò alle 10 invece delle 9", time(9), time(10)),
        ("esco alle 17 al posto delle 18", time(17), time(18)),
        ("esco alle 16 e non alle 18", time(16), time(18)),
        ("entro alle ore 10, invece delle 9", time(9), time(10)),
    ],
)
def test_orario_spostato(testo, inizio, fine):
    [(trovato_inizio, trovato_fine, _minuti)] = intervalli(testo)
    assert (trovato_inizio, trovato_fine) == (inizio, fine)


def test_minuti_dell_intervallo():
    assert Intervallo(time(9), time(10, 30)).minuti == 90
    assert intervalli("esco alle 16 anziché alle 18")[0][2] == 120


# --- Casi da non leggere ---


@pytest.mark.parametrize(
    "testo",
    [
        "dalle 11 alle 9",  # la fine viene prima dell'inizio
        "dalle 25 alle 26",  # ore inesistenti
        "dalle 9:75 alle 11",  # minuti inesistenti
        "esco alle 16 anziché alle 16",  # nessuna differenza
        "ho 2 figli invece di 3",  # senza "alle" non è un orario
        "dalle 9 in poi",
        "alle 9",
        "",
    ],
)
def test_nessun_intervallo(testo):
    assert intervalli(testo) == []


def test_piu_intervalli_in_ordine():
    testo = "lunedì dalle 9 alle 11 e martedì esco alle 17 anziché alle 18"
    assert [(i, f) for i, f, _m in intervalli(testo)] == [(time(9), time(11)), (time(17), time(18))]


# --- Parole aggiunte dalle impostazioni ---


def test_parole_aggiunte():
    testo = "esco alle 16 piuttosto che alle 18"
    assert intervalli(testo) == []
    esteso = VOCABOLARIO.estendi(invece=["piuttosto che"])
    assert intervalli(testo, esteso) == [(time(16), time(18), 120)]


def test_unita_aggiunta():
    esteso = VOCABOLARIO.estendi(unita_ore=["hr"])
    assert intervalli("dalle hr 9 alle hr 11") == []
    assert intervalli("dalle hr 9 alle hr 11", esteso) == [(time(9), time(11), 120)]
