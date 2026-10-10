"""Stato della pratica di malattia (issue #2).

Incompleta (manca protocollo, CF o date) → Da inviare (risposta al lavoratore non
fatta) → Parziale (episodio oltre 3 giorni senza mail all'ufficio) → Chiusa.
Uno stato impostato a mano non viene ricalcolato.
"""

from datetime import date

import pytest

from assenze_desk.core.stato import Stato, calcola_stato, serve_mail_ufficio

COMPLETA = {
    "protocollo": "412345678",
    "cf": "FNTPRV80A01Z999Y",
    "inizio": date(2026, 10, 5),
    "fine": date(2026, 10, 6),
}


def stato(**modifiche):
    return calcola_stato(
        **{**COMPLETA, "mail_lavoratore": True, "mail_ufficio": False, **modifiche}
    )


def test_nomi_degli_stati():
    assert [s.value for s in Stato] == ["Incompleta", "Da inviare", "Parziale", "Chiusa"]


@pytest.mark.parametrize(
    "mancante",
    [
        {"protocollo": ""},
        {"protocollo": "   "},
        {"cf": None},
        {"inizio": None},
        {"fine": None},
    ],
)
def test_incompleta_se_manca_un_dato(mancante):
    assert stato(**mancante) is Stato.INCOMPLETA


def test_incompleta_se_la_fine_viene_prima_dell_inizio():
    assert stato(inizio=date(2026, 10, 6), fine=date(2026, 10, 5)) is Stato.INCOMPLETA


def test_da_inviare_se_manca_la_risposta_al_lavoratore():
    assert stato(mail_lavoratore=False) is Stato.DA_INVIARE


def test_chiusa_fino_a_3_giorni_di_episodio():
    assert stato(giorni_episodio=3) is Stato.CHIUSA


def test_parziale_oltre_3_giorni_senza_mail_all_ufficio():
    assert stato(giorni_episodio=4) is Stato.PARZIALE
    assert stato(giorni_episodio=4, mail_ufficio=True) is Stato.CHIUSA


def test_senza_giorni_dell_episodio_valgono_quelli_del_certificato():
    assert stato(fine=date(2026, 10, 8)) is Stato.PARZIALE  # dal 5 all'8: 4 giorni
    assert stato() is Stato.CHIUSA  # dal 5 al 6: 2 giorni


def test_soglia_configurabile():
    assert stato(giorni_episodio=5, soglia_ufficio=5) is Stato.CHIUSA
    assert stato(giorni_episodio=6, soglia_ufficio=5) is Stato.PARZIALE


def test_stato_manuale_non_ricalcolato():
    assert stato(protocollo="", stato_manuale=Stato.CHIUSA) is Stato.CHIUSA
    assert stato(stato_manuale=Stato.DA_INVIARE) is Stato.DA_INVIARE


def test_serve_mail_ufficio():
    assert serve_mail_ufficio(4)
    assert not serve_mail_ufficio(3)
    assert serve_mail_ufficio(3, soglia=2)
