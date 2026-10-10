"""Date scritte esplicitamente (issue #9): meglio vuoto che sbagliato.

La data di riferimento (di solito la data della mail) entra sempre come argomento:
il core non legge mai l'orologio di sistema (vedi tests/test_architettura.py).
"""

from datetime import date

import pytest

from assenze_desk.core.date import leggi_data, trova_date

MAIL = date(2026, 10, 10)


# --- Una data sola (per esempio il valore di un campo) ---


@pytest.mark.parametrize(
    "scritta",
    [
        "05/01/2026",
        "5/1/2026",
        "05-01-2026",  # nella v6.20 diventava la data di oggi
        "05.01.2026",
        "05/01/26",  # anno a due cifre: 2000 + anno
        "2026-01-05",  # formato ISO
        "5 gennaio 2026",
        "5 Gen 2026",
        "5 gen. 2026",
        "  05/01/2026  ",
    ],
)
def test_data_completa(scritta):
    assert leggi_data(scritta) == date(2026, 1, 5)


def test_primo_del_mese_con_il_simbolo_di_grado():
    assert leggi_data("1° marzo 2026") == date(2026, 3, 1)
    assert leggi_data("1º marzo 2026") == date(2026, 3, 1)


@pytest.mark.parametrize(
    "scritta",
    [
        "abc",  # nella v6.20 diventava la data di oggi
        "",
        "31/02/2026",  # giorno inesistente
        "05/13/2026",  # mese inesistente
        "00/01/2026",
        "05/01/2026 abc",  # un campo deve contenere solo la data
        "05/01-2026",  # separatori diversi
        "5 gennaio 26",  # con il mese in lettere l'anno va scritto per intero
    ],
)
def test_data_non_leggibile(scritta):
    assert leggi_data(scritta, riferimento=MAIL) is None


# --- Anno mancante: l'anno che porta la data più vicina alla data della mail ---


def test_senza_anno_vicino_alla_data_della_mail():
    assert leggi_data("12/10", riferimento=MAIL) == date(2026, 10, 12)
    assert leggi_data("5 ottobre", riferimento=MAIL) == date(2026, 10, 5)


def test_senza_anno_a_cavallo_di_capodanno():
    assert leggi_data("02/01", riferimento=date(2026, 12, 28)) == date(2027, 1, 2)
    assert leggi_data("30/12", riferimento=date(2026, 1, 3)) == date(2025, 12, 30)


def test_senza_anno_con_riferimento_spostato_in_avanti():
    # Ferie chieste a gennaio per agosto: la data più vicina sarebbe l'agosto passato
    gennaio = date(2026, 1, 15)
    assert leggi_data("10/08", riferimento=gennaio) == date(2025, 8, 10)
    assert leggi_data("10/08", riferimento=gennaio, giorni_avanti=120) == date(2026, 8, 10)


def test_29_febbraio_senza_anno():
    assert leggi_data("29/02", riferimento=date(2028, 1, 10)) == date(2028, 2, 29)
    assert leggi_data("29/02", riferimento=MAIL) is None  # nessun anno bisestile vicino


def test_senza_anno_e_senza_riferimento_nessuna_data():
    assert leggi_data("05/01") is None  # mai la data di sistema come ripiego


@pytest.mark.parametrize("scritta", ["05-01", "05.01", "9.30"])
def test_senza_anno_solo_con_la_barra(scritta):
    assert leggi_data(scritta, riferimento=MAIL) is None


# --- Tutte le date di un testo ---


def test_trova_le_date_nel_testo_in_ordine():
    testo = "Malattia dal 05/01/2026 al 9.1.2026, controllo lunedì 12 gennaio 2026."
    assert trova_date(testo) == [date(2026, 1, 5), date(2026, 1, 9), date(2026, 1, 12)]


def test_nel_testo_senza_doppioni():
    assert trova_date("05/01/2026 e ancora 5 gennaio 2026") == [date(2026, 1, 5)]


def test_nel_testo_con_anno_mancante():
    assert trova_date("permesso il 12/10 e il 13/10", riferimento=MAIL) == [
        date(2026, 10, 12),
        date(2026, 10, 13),
    ]


@pytest.mark.parametrize(
    "testo",
    [
        "esco dalle 9.30 alle 11.30",  # orari
        "1.5 ore di permesso",
        "versione 6.20",
        "protocollo 412345678",
        "05/01/202",  # anno incompleto
        "105/01/2026",  # attaccata ad altre cifre
        "il 5 martedì",  # "mar" dentro un'altra parola
        "il 31/02/2026",
        "",
    ],
)
def test_nessuna_data_nel_testo(testo):
    assert trova_date(testo, riferimento=MAIL) == []
