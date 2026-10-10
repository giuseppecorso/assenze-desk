"""Lettura dei dati dal testo di un certificato di malattia INPS (issue #4).

Testi inventati, con le stesse etichette del certificato. Le spunte ("X") vengono
attribuite solo quando la loro posizione è chiara (D45).
"""

from datetime import date

import pytest

from assenze_desk.core.certificato import leggi_certificato

TESTO = """CERTIFICATO DI MALATTIA - FAC-SIMILE CON DATI INVENTATI
Protocollo univoco del certificato (PUC): 412 345 678
DATI DEL LAVORATORE
Cognome FITTIZIO Nome LUCA C.F. FNTPRV80A01Z999Y
Trattasi di: X Inizio Continuazione Ricaduta Ricovero
Visita: X Ambulatoriale Domiciliare Pronto Soccorso
Data visita 01/10/2026
Il medico dichiara che il lavoratore è ammalato dal 01/10/2026 a tutto il 03/10/2026
"""


def test_certificato_completo():
    dati = leggi_certificato(TESTO)
    assert dati.protocollo == "412345678"
    assert dati.cf == "FNTPRV80A01Z999Y"
    assert (dati.cognome, dati.nome) == ("Fittizio", "Luca")
    assert (dati.inizio, dati.fine) == (date(2026, 10, 1), date(2026, 10, 3))
    assert dati.data_visita == date(2026, 10, 1)
    assert (dati.tipo, dati.visita) == ("Inizio", "Ambulatoriale")
    assert not dati.continuazione
    assert dati.segnalazioni == ()


def con_spunte(trattasi, visita="X Ambulatoriale Domiciliare Pronto Soccorso"):
    return TESTO.replace("X Inizio Continuazione Ricaduta Ricovero", trattasi).replace(
        "X Ambulatoriale Domiciliare Pronto Soccorso", visita
    )


def test_spunte_dopo_le_voci_riconosciute_in_automatico():
    testo = con_spunte(
        "Inizio Continuazione Ricaduta Ricovero X", "Ambulatoriale Pronto Soccorso X"
    )
    dati = leggi_certificato(testo)
    assert (dati.tipo, dati.visita) == ("Ricovero", "Pronto Soccorso")


def test_spunta_in_mezzo_ambigua_in_automatico():
    dati = leggi_certificato(con_spunte("Inizio X Continuazione Ricaduta Ricovero"))
    assert dati.tipo is None
    assert any("spunte" in s for s in dati.segnalazioni)


def test_posizione_della_spunta_impostata():
    testo = con_spunte("Inizio X Continuazione Ricaduta Ricovero")
    prima = leggi_certificato(testo, x_prima_della_voce=True)
    assert (prima.tipo, prima.continuazione) == ("Continuazione", True)
    assert leggi_certificato(testo, x_prima_della_voce=False).tipo == "Inizio"


def test_sezione_senza_spunte():
    dati = leggi_certificato(con_spunte("Inizio Continuazione Ricaduta Ricovero"))
    assert dati.tipo is None
    assert dati.visita == "Ambulatoriale"


def test_spunta_senza_voce_accanto():
    dati = leggi_certificato(con_spunte("Inizio Continuazione X"), x_prima_della_voce=True)
    assert dati.tipo is None
    assert any("spunte" in s for s in dati.segnalazioni)


def test_protocollo_senza_etichetta():
    testo = TESTO.replace(
        "Protocollo univoco del certificato (PUC): 412 345 678", "Numero 412345678"
    )
    assert leggi_certificato(testo).protocollo == "412345678"


@pytest.mark.parametrize(
    ("da_togliere", "campo"),
    [
        ("Protocollo univoco del certificato (PUC): 412 345 678", "protocollo"),
        ("C.F. FNTPRV80A01Z999Y", "codice fiscale"),
        ("ammalato dal 01/10/2026", "inizio"),
        ("a tutto il 03/10/2026", "fine"),
    ],
)
def test_dati_mancanti_segnalati(da_togliere, campo):
    dati = leggi_certificato(TESTO.replace(da_togliere, ""))
    assert any(campo in s for s in dati.segnalazioni), dati.segnalazioni


def test_cf_con_carattere_di_controllo_sbagliato_scartato():
    dati = leggi_certificato(TESTO.replace("FNTPRV80A01Z999Y", "FNTPRV80A01Z999A"))
    assert dati.cf is None
    assert any("codice fiscale" in s for s in dati.segnalazioni)
    assert all("FNTPRV80A01Z999A" not in s for s in dati.segnalazioni)  # niente CF in chiaro


def test_testo_vuoto():
    dati = leggi_certificato("")
    assert dati.protocollo is None
    assert len(dati.segnalazioni) >= 4
