"""Generatore di dati finti per la modalità demo e per i test (issue #2).

Ogni mail generata porta con sé i valori attesi: il core deve leggerli tutti.
"""

from datetime import date

import pytest
from check_privacy import REGOLE_FISSE, controlla_testo

from assenze_desk.core.codice_fiscale import cf_valido, estrai_cf
from assenze_desk.core.dipendenti import trova_dipendente
from assenze_desk.core.identificativi import estrai_joborder, estrai_protocollo
from assenze_desk.core.permessi import leggi_permesso
from assenze_desk.demo.generatore import genera_dati

OGGI = date(2026, 10, 7)


@pytest.fixture(scope="module")
def dati():
    return genera_dati(OGGI, seme=1, dipendenti=25, mail_malattia=20, mail_permesso=20)


def test_stesso_seme_stessi_dati():
    assert genera_dati(OGGI, seme=7) == genera_dati(OGGI, seme=7)
    assert genera_dati(OGGI, seme=7) != genera_dati(OGGI, seme=8)


def test_quantita(dati):
    assert len({d.cf for d in dati.anagrafica}) == 25
    assert len(dati.mail_malattia) == 20
    assert len(dati.mail_permesso) == 20


def test_cf_validi_ma_mai_reali(dati):
    for dipendente in dati.anagrafica:
        assert cf_valido(dipendente.cf)
        assert dipendente.cf[11:15] == "Z999"  # luogo di nascita inesistente


def test_solo_email_di_esempio(dati):
    assert all(d.email.endswith("@example.com") for d in dati.anagrafica)


def test_nessun_dato_che_il_controllo_privacy_bloccherebbe(dati):
    testi = [m.testo for m in dati.mail_malattia + dati.mail_permesso]
    testi += [f"{d.cognome} {d.nome} {d.email} {d.cliente}" for d in dati.anagrafica]
    for testo in testi:
        assert controlla_testo(testo, "demo", REGOLE_FISSE) == []


def test_ogni_cliente_ha_un_orario(dati):
    assert {d.cliente for d in dati.anagrafica} <= set(dati.orari)


def test_il_core_legge_le_mail_di_malattia(dati):
    for mail in dati.mail_malattia:
        assert estrai_protocollo(mail.testo) == mail.atteso["protocollo"], mail.testo
        assert estrai_cf(mail.testo) == mail.atteso["cf"], mail.testo
        assert estrai_joborder(mail.testo) == mail.atteso["joborder"], mail.testo


def test_il_core_riconosce_il_dipendente_dal_mittente(dati):
    for mail in dati.mail_malattia + dati.mail_permesso:
        esito = trova_dipendente(dati.anagrafica, mittente=mail.mittente, testo=mail.testo)
        assert {d.cf for d in esito.candidati} == {mail.atteso["cf"]}, mail.testo


def test_il_core_legge_le_mail_di_permesso(dati):
    for mail in dati.mail_permesso:
        permesso = leggi_permesso(mail.testo, mail.ricevuta.date())
        assert permesso.tipo is not None, mail.testo
        assert permesso.tipo.nome == mail.atteso["tipo"], mail.testo
        assert permesso.giorni == mail.atteso["giorni"], mail.testo
        assert permesso.minuti == mail.atteso["minuti"], mail.testo
