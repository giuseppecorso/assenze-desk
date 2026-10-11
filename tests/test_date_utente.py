"""Date inserite dall'utente: avvisi sulle date poco plausibili e mini calendario.

Una data scritta male (31/02, 45/13) non si legge e il campo lo dice subito.
Qui si controllano quelle che si leggono ma sembrano un errore di battitura:
la fine prima dell'inizio, l'anno sbagliato. Sono avvisi, non blocchi.
"""

from dataclasses import replace
from datetime import date

import pytest

from assenze_desk.core.campi import Campo, Origine
from assenze_desk.core.date_utente import (
    AVVISO_FINE_PRIMA,
    AVVISO_GIORNI_LONTANI,
    AVVISO_LONTANA,
    aggiungi_feriali,
    alterna_giorno,
    controlla_giorni,
    controlla_periodo,
    lontana,
)

OGGI = date(2026, 10, 11)


def manuale(valore) -> Campo:
    return Campo(valore, Origine.MANUALE)


# --- Date lontane da oggi ---


@pytest.mark.parametrize(
    ("giorno", "attesa"),
    [
        (date(2026, 10, 11), False),
        (date(2026, 4, 11), False),  # 183 giorni prima: ancora plausibile
        (date(2026, 4, 10), True),
        (date(2027, 4, 12), False),  # 183 giorni dopo
        (date(2027, 4, 13), True),
        (date(2062, 10, 11), True),  # anno scritto al contrario
        (date(2025, 10, 11), True),  # anno precedente per sbaglio
    ],
)
def test_data_lontana_da_oggi(giorno, attesa):
    assert lontana(giorno, OGGI) is attesa


# --- Periodo della malattia ---


def test_periodo_normale_senza_avvisi():
    inizio, fine = controlla_periodo(manuale(date(2026, 10, 5)), manuale(date(2026, 10, 9)), OGGI)
    assert inizio.avviso == fine.avviso == ""


def test_fine_prima_dell_inizio():
    inizio, fine = controlla_periodo(manuale(date(2026, 10, 9)), manuale(date(2026, 10, 5)), OGGI)
    assert inizio.avviso == ""
    assert fine.avviso == AVVISO_FINE_PRIMA
    assert fine.incerto


def test_anno_sbagliato():
    inizio, fine = controlla_periodo(manuale(date(2026, 10, 5)), manuale(date(2062, 10, 9)), OGGI)
    assert inizio.avviso == ""
    assert fine.avviso == AVVISO_LONTANA


def test_l_avviso_si_aggiunge_a_quello_dell_analisi():
    dal_testo = Campo(date(2025, 10, 5), Origine.TESTO, avviso="Più periodi nel testo.")
    inizio, _ = controlla_periodo(dal_testo, Campo(), OGGI)
    assert inizio.avviso == f"Più periodi nel testo. {AVVISO_LONTANA}"


def test_i_dati_riaperti_dall_archivio_non_si_ricontrollano_per_la_distanza():
    # Una pratica vecchia riaperta ha date lontane da oggi, ma già confermate
    vecchia = Campo(date(2025, 1, 5), Origine.ARCHIVIO)
    inizio, fine = controlla_periodo(vecchia, replace(vecchia, valore=date(2025, 1, 9)), OGGI)
    assert inizio.avviso == fine.avviso == ""


def test_campi_vuoti_senza_avvisi():
    inizio, fine = controlla_periodo(Campo(), Campo(), OGGI)
    assert inizio == Campo()
    assert fine == Campo()


# --- Giorni del giustificativo ---


def test_giorni_vicini_senza_avvisi():
    campo = manuale((date(2026, 10, 12), date(2026, 10, 13)))
    assert controlla_giorni(campo, OGGI) == campo


def test_giorni_lontani():
    campo = manuale((date(2026, 10, 12), date(2062, 10, 13)))
    assert controlla_giorni(campo, OGGI).avviso == AVVISO_GIORNI_LONTANI


def test_giorni_vuoti():
    assert controlla_giorni(Campo(), OGGI) == Campo()


# --- Scelta dei giorni dal mini calendario ---


def test_un_clic_aggiunge_o_toglie_il_giorno():
    giorni = alterna_giorno((), date(2026, 10, 13))
    giorni = alterna_giorno(giorni, date(2026, 10, 12))
    assert giorni == (date(2026, 10, 12), date(2026, 10, 13))
    assert alterna_giorno(giorni, date(2026, 10, 13)) == (date(2026, 10, 12),)


def test_intervallo_solo_con_i_giorni_feriali():
    # Da venerdì 9 a mercoledì 14: sabato e domenica restano fuori (D48)
    giorni = aggiungi_feriali((date(2026, 10, 9),), date(2026, 10, 9), date(2026, 10, 14))
    assert giorni == (
        date(2026, 10, 9),
        date(2026, 10, 12),
        date(2026, 10, 13),
        date(2026, 10, 14),
    )


def test_intervallo_all_indietro_e_senza_doppioni():
    giorni = aggiungi_feriali(
        (date(2026, 10, 1), date(2026, 10, 14)), date(2026, 10, 14), date(2026, 10, 12)
    )
    assert giorni == (date(2026, 10, 1), date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14))
