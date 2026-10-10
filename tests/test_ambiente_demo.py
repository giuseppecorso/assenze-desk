"""Modalità demo: l'app parte con dati finti, senza Outlook (issue #5)."""

from datetime import date, datetime

import pytest

from assenze_desk.adapters.outlook import ErroreOutlook, MailImportata
from assenze_desk.adapters.pdf import leggi_certificato_pdf
from assenze_desk.config import carica_impostazioni
from assenze_desk.core.stato import Stato
from assenze_desk.demo.ambiente import PostaDemo, crea_ambiente_demo
from assenze_desk.storage.anagrafica import importa_anagrafica
from assenze_desk.storage.archivio import Archivio

OGGI = date(2026, 10, 7)


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    cartella = tmp_path_factory.mktemp("demo")
    return cartella, crea_ambiente_demo(cartella, OGGI)


def test_impostazioni_e_anagrafica_finte(demo):
    cartella, _posta = demo
    imp, avvisi = carica_impostazioni(cartella / "impostazioni.json", cartella)
    assert avvisi == []
    assert imp.ufficio.destinatari == ("ufficio.personale@example.com",)
    assert imp.cartelle_outlook.malattie
    esito = importa_anagrafica(imp.percorsi.anagrafica)
    assert len(esito.dipendenti) == 24
    assert all(d.cf[11:15] == "Z999" for d in esito.dipendenti)  # luogo di nascita inesistente
    assert all(d.email.endswith("@example.com") for d in esito.dipendenti)
    assert esito.orari
    assert esito.capienze


def test_archivio_con_pratiche_in_stati_diversi_e_certificati(demo):
    cartella, _posta = demo
    imp, _ = carica_impostazioni(cartella / "impostazioni.json", cartella)
    with Archivio(imp.percorsi.archivio) as archivio:
        pratiche = archivio.pratiche()
        assert len(pratiche) == 24
        assert {p.stato for p in pratiche} == set(Stato)
        complete = [p for p in pratiche if p.inizio and p.fine]
        assert all((imp.percorsi.certificati / f"{p.protocollo}.pdf").is_file() for p in complete)
        assert any(p.tempo_gestione_sec for p in pratiche)
        righe = archivio.righe()
        assert righe
        assert any(r.esportata for r in righe)
        assert any(not r.esportata for r in righe)


def test_la_posta_demo_restituisce_mail_e_certificati(demo, tmp_path):
    _cartella, posta = demo
    mail = posta.prossima("malattia")
    assert mail.entry_id.startswith("demo-")
    assert "malattia" in mail.testo.lower()
    allegati = posta.salva_allegati(mail, tmp_path / "in_arrivo")
    assert len(allegati) == 1
    certificato = leggi_certificato_pdf(allegati[0])
    assert certificato.protocollo
    assert certificato.segnalazioni == ()

    permesso = posta.prossima("giustificativo")
    assert posta.salva_allegati(permesso, tmp_path / "in_arrivo") == []


def test_la_posta_demo_registra_bozze_e_spostamenti_senza_aprire_niente(demo):
    _cartella, posta = demo
    mail = posta.prossima("malattia")
    posta.bozza_risposta(mail, "<p>Ricevuto</p>")
    assert posta.bozze[-1].risposta_a == mail.entry_id
    posta.bozza_nuova(["ufficio@example.com"], "Oggetto", "<p>corpo</p>", allegati=())
    assert posta.bozze[-1].a == ("ufficio@example.com",)
    assert posta.sposta(mail, "Gestite/Malattie") == "Gestite/Malattie"


def test_le_mail_della_demo_non_finiscono(demo):
    _cartella, posta = demo
    importate = {posta.prossima("giustificativo").entry_id for _ in range(50)}
    assert len(importate) == 50


def test_stessi_metodi_dell_adapter_di_outlook(demo):
    _cartella, posta = demo
    assert "malattia" in posta.mail_selezionata().testo.lower()
    with pytest.raises(ErroreOutlook, match="demo"):
        PostaDemo([], [], []).prossima("malattia")


def test_mail_sconosciuta(demo):
    _cartella, posta = demo
    estranea = MailImportata("x", "y", "a@example.com", datetime(2026, 10, 7), "altro", "")
    with pytest.raises(ErroreOutlook):
        posta.bozza_risposta(estranea, "<p>x</p>")
