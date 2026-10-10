"""Durate dei permessi in minuti interi (issue #12).

Fasce orarie e orari spostati ("dalle 9 alle 11", "esco alle 16 anziché alle 18")
sono della issue #15.
"""

import pytest

from assenze_desk.core.ore import leggi_durata, trova_durate
from assenze_desk.core.vocabolario import VOCABOLARIO


@pytest.mark.parametrize(
    ("testo", "minuti"),
    [
        ("chiedo 2 ore di permesso", 120),
        ("2 ore e 30 minuti", 150),  # nella v6.20: 2 ore
        ("2 ore e mezza", 150),  # nella v6.20: 2 ore
        ("2 ore 30 min", 150),
        ("1 ora e un quarto", 75),
        ("1 ora e tre quarti", 105),
        ("1h30", 90),
        ("1h 30", 90),
        ("90 minuti", 90),
        ("30 min", 30),
        ("2,5 ore", 150),
        ("2.5 ore", 150),
        ("1,25 ore", 75),
        ("2h", 120),
        ("1 h", 60),
        ("un'ora", 60),
        ("un’ora e mezza", 90),  # apostrofo tipografico
        ("un ora", 60),
        ("una ora e mezzo", 90),
        ("due ore e mezza", 150),
        ("Tre ORE", 180),
        ("dodici ore", 720),
        ("mezz'ora", 30),
        ("mezzora", 30),
        ("mezza ora", 30),
        ("un quarto d'ora", 15),
        ("tre quarti d'ora", 45),
    ],
)
def test_durata(testo, minuti):
    assert trova_durate(testo) == [minuti]
    assert leggi_durata(testo) == minuti


@pytest.mark.parametrize(
    "testo",
    [
        "alle ore 9 sono in ufficio",  # "ore" prima del numero: è un orario
        "dalle 9 alle 11",  # fascia oraria: issue #15
        "1.30 ore",  # 1 ora e 30 minuti o 1,3 ore? meglio vuoto
        "0 ore",
        "contratto di 40 ore",  # oltre le 24 ore: non è un permesso
        "2 ore e 75 minuti",  # minuti impossibili
        "2,33 ore",  # non è un numero intero di minuti
        "orario continuato",
        "prenotato in 2 hotel",
        "le nostre ore di lavoro",  # "tre" dentro un'altra parola
        "aspetta un minuto",  # minuti solo in cifre
        "",
    ],
)
def test_nessuna_durata(testo):
    assert trova_durate(testo) == []
    assert leggi_durata(testo) is None


def test_piu_durate_in_ordine():
    assert trova_durate("oggi 2 ore e domani 1 ora e mezza") == [120, 90]


def test_piu_durate_diverse_sceglie_l_utente():
    assert leggi_durata("oggi 2 ore e domani 1 ora e mezza") is None


def test_unita_aggiunte_dalle_impostazioni():
    esteso = VOCABOLARIO.estendi(unita_ore=["hr"], unita_minuti=["mn"])
    assert trova_durate("2 hr e 15 mn") == []
    assert trova_durate("2 hr e 15 mn", esteso) == [135]


def test_stessa_durata_ripetuta():
    assert leggi_durata("Oggetto: permesso 2 ore\nconfermo le 2 ore di stamattina") == 120
