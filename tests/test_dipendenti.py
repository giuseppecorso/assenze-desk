"""Match del dipendente con l'anagrafica (issue #2). Anagrafica tutta inventata.

Ordine: JobOrder, mittente (escluse le mail interne), CF, nomi nel testo. Con più
candidati: JobOrder attivo nel periodo, poi cliente citato, poi scelta manuale.
"""

from datetime import date

import pytest

from assenze_desk.core.dipendenti import (
    Dipendente,
    attivo_nel_periodo,
    cerca_dipendenti,
    email_da_ricordare,
    trova_dipendente,
)

CF_LUCA = "FNTPRV80A01Z999Y"
CF_ANNA = "TSTCSO92M45Z888V"
CF_MARCO = "FNTPRVULALMZ999J"

LUCA_ALFA = Dipendente(
    cf=CF_LUCA,
    cognome="Fittizio",
    nome="Luca",
    email="luca.fittizio@example.com",
    joborder="201111111",
    cliente="Alfa Srl",
    inizio_joborder=date(2026, 1, 1),
    fine_joborder=date(2026, 6, 30),
)
LUCA_BETA = Dipendente(
    cf=CF_LUCA,
    cognome="Fittizio",
    nome="Luca",
    email="luca.fittizio@example.com",
    joborder="202222222",
    cliente="Beta Spa",
    inizio_joborder=date(2026, 7, 1),
    fine_joborder=date(2026, 12, 31),
)
ANNA = Dipendente(
    cf=CF_ANNA,
    cognome="Esempio",
    nome="Anna",
    email="anna.esempio@example.com",
    joborder="203333333",
    cliente="Alfa Srl",
)
MARCO = Dipendente(
    cf=CF_MARCO, cognome="Esempio", nome="Marco", joborder="204444444", cliente="Gamma Srl"
)

ANAGRAFICA = (LUCA_ALFA, LUCA_BETA, ANNA, MARCO)
OTTOBRE = (date(2026, 10, 5), date(2026, 10, 6))
MARZO = (date(2026, 3, 2), date(2026, 3, 3))


def trova(**argomenti):
    return trova_dipendente(ANAGRAFICA, **argomenti)


# --- Fonti, in ordine ---


def test_joborder():
    esito = trova(joborder="203333333")
    assert esito.dipendente == ANNA
    assert "JobOrder" in esito.motivo


def test_joborder_sconosciuto_passa_alla_fonte_successiva():
    assert trova(joborder="209999999", mittente="anna.esempio@example.com").dipendente == ANNA


def test_il_joborder_vince_sul_cf_di_un_altro():
    assert trova(joborder="203333333", cf=CF_MARCO).dipendente == ANNA


def test_mittente():
    esito = trova(mittente="Anna.Esempio@Example.com")
    assert esito.dipendente == ANNA
    assert "mittente" in esito.motivo


def test_mittente_interno_ignorato_si_cerca_l_indirizzo_nel_testo():
    testo = "Inoltro la richiesta di anna.esempio@example.com"
    esito = trova(
        mittente="collega@azienda.example", testo=testo, domini_interni=("azienda.example",)
    )
    assert esito.dipendente == ANNA


def test_mittente_interno_senza_altri_indirizzi():
    esito = trova(mittente="collega@azienda.example", domini_interni=("azienda.example",))
    assert esito.dipendente is None
    assert esito.candidati == ()


def test_mittente_ricordato():
    """Chi scrive da un indirizzo non in anagrafica viene riconosciuto se l'indirizzo
    è stato ricordato (email → CF), anche con maiuscole diverse."""
    note = {"marco.casa@example.org": CF_MARCO}
    esito = trova(mittente="Marco.Casa@example.org", email_note=note)
    assert esito.dipendente == MARCO
    assert "mittente" in esito.motivo
    assert trova(mittente="marco.casa@example.org").dipendente is None


def test_mittente_ricordato_con_piu_joborder_sceglie_il_periodo():
    note = {"luca.casa@example.org": CF_LUCA}
    esito = trova(mittente="luca.casa@example.org", email_note=note, periodo=OTTOBRE)
    assert esito.dipendente == LUCA_BETA


@pytest.mark.parametrize(
    ("mittente", "note", "atteso"),
    [
        ("Marco <marco.casa@example.org>", {}, "marco.casa@example.org"),  # nuovo indirizzo
        ("MARCO.CASA@example.org", {}, "marco.casa@example.org"),
        ("anna.esempio@example.com", {}, ""),  # è già l'indirizzo in anagrafica
        ("collega@azienda.example", {}, ""),  # mail interna: un collega, non il dipendente
        ("", {}, ""),
        ("senza indirizzo", {}, ""),
        ("marco.casa@example.org", {"marco.casa@example.org": CF_MARCO}, ""),  # già ricordato
        ("marco.casa@example.org", {"marco.casa@example.org": CF_ANNA}, "marco.casa@example.org"),
    ],
)
def test_email_da_ricordare(mittente, note, atteso):
    dipendente = ANNA if mittente.startswith("anna") else MARCO
    assert email_da_ricordare(mittente, dipendente, ("azienda.example",), note) == atteso


def test_cf():
    esito = trova(cf=CF_MARCO.lower())
    assert esito.dipendente == MARCO
    assert "codice fiscale" in esito.motivo
    assert CF_MARCO not in esito.motivo  # il CF non finisce nei messaggi


# --- Più candidati: periodo, cliente, scelta manuale ---


def test_stesso_cf_con_due_joborder_sceglie_quello_attivo_nel_periodo():
    assert trova(cf=CF_LUCA, periodo=OTTOBRE).dipendente == LUCA_BETA
    assert trova(cf=CF_LUCA, periodo=MARZO).dipendente == LUCA_ALFA


def test_senza_periodo_sceglie_l_utente():
    esito = trova(cf=CF_LUCA)
    assert esito.dipendente is None
    assert esito.candidati == (LUCA_ALFA, LUCA_BETA)


def test_cliente_citato_nel_testo():
    esito = trova(cf=CF_LUCA, testo="certificato per il cliente Beta Spa")
    assert esito.dipendente == LUCA_BETA
    assert "cliente" in esito.motivo


def test_periodo_a_cavallo_dei_due_joborder_poi_cliente():
    a_cavallo = (date(2026, 6, 30), date(2026, 7, 1))
    assert trova(cf=CF_LUCA, periodo=a_cavallo).dipendente is None
    assert trova(cf=CF_LUCA, periodo=a_cavallo, testo="Alfa Srl").dipendente == LUCA_ALFA


# --- Nomi nel testo ---


def test_nome_e_cognome_nell_oggetto():
    esito = trova(testo="Oggetto: malattia Fittizio Luca\ncertificato in allegato", periodo=OTTOBRE)
    assert esito.dipendente == LUCA_BETA
    assert "nome" in esito.motivo


def test_nome_e_cognome_nel_corpo_in_qualsiasi_ordine():
    assert trova(testo="Sono Anna Esempio, invio il certificato").dipendente == ANNA


def test_nome_del_mittente():
    testo = "Da: Anna Esempio <posta.personale@example.org>\n\ninvio il certificato"
    assert trova(testo=testo).dipendente == ANNA


def test_solo_il_cognome_da_solo_suggerimenti():
    esito = trova(testo="certificato di Esempio")
    assert esito.dipendente is None
    assert esito.candidati == (ANNA, MARCO)
    solo_anna = trova_dipendente((ANNA,), testo="certificato di Esempio")
    assert solo_anna.dipendente is None
    assert solo_anna.candidati == (ANNA,)


def test_le_righe_di_saluto_nominano_chi_riceve():
    esito = trova(testo="Buongiorno Anna Esempio,\nvi invio il certificato.")
    assert esito.dipendente is None
    assert esito.candidati == ()


def test_nessun_indizio():
    esito = trova(testo="buongiorno, allego il certificato")
    assert (esito.dipendente, esito.candidati, esito.motivo) == (None, (), "")


def test_righe_senza_cognome_non_si_cercano_per_nome():
    senza_cognome = Dipendente(cf=CF_ANNA, cognome="", nome="Anna")
    assert trova_dipendente((senza_cognome,), testo="Sono Anna").candidati == ()


def test_anagrafica_vuota():
    assert trova_dipendente((), cf=CF_ANNA).dipendente is None


# --- Periodo del JobOrder ---


def test_attivo_nel_periodo():
    assert attivo_nel_periodo(LUCA_ALFA, MARZO)
    assert not attivo_nel_periodo(LUCA_ALFA, OTTOBRE)
    assert attivo_nel_periodo(ANNA, OTTOBRE)  # senza date del JobOrder: sempre attivo
    assert attivo_nel_periodo(LUCA_ALFA, None)


# --- Ricerca manuale ---


@pytest.mark.parametrize(
    ("ricerca", "attesi"),
    [
        ("esempio", [ANNA, MARCO]),
        ("Esempio anna", [ANNA]),
        ("alfa", [LUCA_ALFA, ANNA]),
        ("tstcso", [ANNA]),
        ("2033", [ANNA]),
        ("beta fittizio", [LUCA_BETA]),
        ("", []),
        ("nessuno", []),
    ],
)
def test_cerca_dipendenti(ricerca, attesi):
    assert cerca_dipendenti(ANAGRAFICA, ricerca) == attesi


def test_dipendente_senza_cf_non_valido():
    with pytest.raises(ValueError):
        Dipendente(cf=" ", cognome="Esempio", nome="Anna")
