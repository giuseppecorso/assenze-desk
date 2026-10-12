"""Correzioni dell'anagrafica fatte nell'app: valgono sopra i dati dell'Excel."""

from datetime import date

import pytest

from assenze_desk.core.correzioni import CAMPI_MODIFICABILI, applica_correzioni, differenze
from assenze_desk.core.dipendenti import Dipendente

ROSSI = Dipendente(
    "RSSMRA80A01Z999X",
    "Rossi",
    "Mario",
    email="mario.rossi@example.com",
    joborder="JO1",
    cliente="Alfa Srl",
    inizio_joborder=date(2026, 1, 1),
)
ROSSI_JO2 = Dipendente("RSSMRA80A01Z999X", "Rossi", "Mario", joborder="JO2", cliente="Beta Spa")
BIANCHI = Dipendente("BNCLRA85B41Z999Y", "Bianchi", "Laura", joborder="JO3")


def test_differenze_solo_i_campi_cambiati():
    corretto = Dipendente(
        ROSSI.cf,
        "Rossi",
        "Mario Luigi",
        email="m.rossi@example.org",
        joborder="JO1",
        cliente="Alfa Srl",
        inizio_joborder=date(2026, 2, 1),
    )
    assert differenze(ROSSI, corretto) == {
        "nome": "Mario Luigi",
        "email": "m.rossi@example.org",
        "inizio_joborder": date(2026, 2, 1),
    }
    assert differenze(ROSSI, ROSSI) == {}


def test_cf_e_joborder_non_si_correggono():
    assert "cf" not in CAMPI_MODIFICABILI and "joborder" not in CAMPI_MODIFICABILI
    with pytest.raises(ValueError, match="stesso dipendente"):
        differenze(ROSSI, ROSSI_JO2)


def test_applica_solo_alla_riga_giusta():
    correzioni = {(ROSSI.cf, "JO1"): {"email": "m.rossi@example.org", "fine_joborder": None}}
    risultato = applica_correzioni((ROSSI, ROSSI_JO2, BIANCHI), correzioni)
    assert risultato[0].email == "m.rossi@example.org"
    assert risultato[0].nome == "Mario"  # gli altri campi restano quelli dell'Excel
    assert risultato[1] == ROSSI_JO2  # altro JobOrder della stessa persona: non cambia
    assert risultato[2] == BIANCHI


def test_correzioni_di_righe_sparite_o_campi_sconosciuti_si_ignorano():
    correzioni = {
        ("CFINESISTENTE", "JO9"): {"nome": "X"},
        (ROSSI.cf.lower(), "JO1"): {"cf": "ALTRO", "inventato": 1, "cliente": "Gamma Srl"},
    }
    (risultato,) = applica_correzioni((ROSSI,), correzioni)
    assert risultato.cf == ROSSI.cf
    assert risultato.cliente == "Gamma Srl"  # il CF si confronta senza maiuscole
