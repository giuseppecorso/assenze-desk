"""Formati mostrati all'utente e valori dei segnaposti delle bozze (issue #5)."""

from datetime import date

import pytest

from assenze_desk.core import formati
from assenze_desk.core.bozze import valori_giustificativo, valori_malattia
from assenze_desk.core.dipendenti import Dipendente
from assenze_desk.core.episodio import Certificato, Episodio
from assenze_desk.core.template import compila

CF = "FNTPRV80A01Z999Y"
ANNA = Dipendente(CF, "Esempio", "Anna", joborder="201234567", cliente="Alfa Srl")


# --- Formati ---


def test_date_e_ore():
    assert formati.data(date(2026, 10, 9)) == "09/10/2026"
    assert formati.data(None) == ""
    assert formati.giorno_breve(date(2026, 10, 9)) == "ven 09/10"
    assert formati.ore(480) == "8:00"
    assert formati.ore(90) == "1:30"
    assert formati.ore(None) == ""


@pytest.mark.parametrize(
    ("scritto", "minuti"),
    [("8", 480), ("1:30", 90), ("1.30", 90), (" 2 ore ", 120), ("1h30", 90), ("45 minuti", 45)],
)
def test_ore_scritte_a_mano(scritto, minuti):
    assert formati.leggi_ore(scritto) == minuti


@pytest.mark.parametrize("scritto", ["", "tante", "1:75", "25", "2,5"])
def test_ore_non_valide(scritto):
    assert formati.leggi_ore(scritto) is None


def test_giorni_scritti_a_mano():
    assert formati.leggi_giorni("09/10/2026, 12/10, 13/10", date(2026, 10, 2)) == (
        date(2026, 10, 9),
        date(2026, 10, 12),
        date(2026, 10, 13),
    )
    assert formati.leggi_giorni("", date(2026, 10, 2)) == ()


def test_elenco_dei_giorni_per_la_mail():
    assert formati.elenco_giorni([date(2026, 10, 9)]) == "09/10/2026"
    assert formati.elenco_giorni([date(2026, 10, 9), date(2026, 10, 13)]) == (
        "09/10/2026 e 13/10/2026"
    )
    consecutivi = [date(2026, 10, d) for d in (12, 13, 14, 15, 16)]
    assert formati.elenco_giorni([date(2026, 10, 9), *consecutivi]) == (
        "09/10/2026 e dal 12/10/2026 al 16/10/2026"
    )
    assert formati.elenco_giorni([]) == ""


def test_durata_in_parole():
    assert formati.durata_in_parole(120) == "2 ore"
    assert formati.durata_in_parole(60) == "1 ora"
    assert formati.durata_in_parole(90) == "1 ora e 30 minuti"
    assert formati.durata_in_parole(30) == "30 minuti"
    assert formati.durata_in_parole(None) == ""


# --- Valori dei segnaposti ---


def test_valori_della_malattia():
    episodio = Episodio(
        (
            Certificato("411111111", CF, date(2026, 10, 1), date(2026, 10, 4)),
            Certificato("412345678", CF, date(2026, 10, 5), date(2026, 10, 9)),
        )
    )
    valori = valori_malattia(
        dipendente=ANNA,
        protocollo="412345678",
        cf=CF,
        joborder="201234567",
        inizio=date(2026, 10, 5),
        fine=date(2026, 10, 9),
        episodio=episodio,
    )
    assert valori["NOME"] == "Anna"
    assert valori["CANDIDATO"] == "Esempio Anna"
    assert valori["CLIENTE"] == "Alfa Srl"
    assert (valori["DAL"], valori["AL"]) == ("05/10/2026", "09/10/2026")
    assert (valori["INIZIO_EPISODIO"], valori["FINE_EPISODIO"]) == ("01/10/2026", "09/10/2026")
    assert valori["GIORNI_EPISODIO"] == "9"
    assert valori["PROTOCOLLI"] == "411111111, 412345678"
    assert (valori["CF"], valori["JOB"]) == (CF, "201234567")


def test_valori_mancanti_restano_visibili_nella_bozza():
    valori = valori_malattia(
        dipendente=None, protocollo="412345678", cf=None, joborder=None, inizio=None, fine=None
    )
    compilato = compila("Gentile {NOME}, certificato {PROTOCOLLO} dal {DAL}", valori)
    assert compilato.testo == "Gentile {NOME}, certificato 412345678 dal {DAL}"
    assert compilato.mancanti == ("NOME", "DAL")


def test_valori_del_giustificativo():
    valori = valori_giustificativo(
        dipendente=ANNA, tipo="Ferie", giorni=[date(2026, 10, 9), date(2026, 10, 12)], minuti=None
    )
    assert valori["TIPO"] == "Ferie"
    assert valori["GIORNI"] == "09/10/2026 e 12/10/2026"
    assert valori["ORE"] is None
    assert valori["NOME"] == "Anna"
    con_ore = valori_giustificativo(dipendente=None, tipo="ROL", giorni=[], minuti=120)
    assert con_ore["ORE"] == "2 ore"
    assert con_ore["GIORNI"] is None
    assert con_ore["NOME"] is None
