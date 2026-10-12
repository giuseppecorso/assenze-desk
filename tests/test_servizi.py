"""Servizi dell'app: il collegamento tra schermate, archivio, anagrafica e posta (issue #5).

Si usa l'ambiente demo (dati finti) e, dove serve, l'Outlook finto dei test.
"""

import os
from dataclasses import replace
from datetime import date, datetime

import pytest
from outlook_finto import Allegato, Mail, OutlookFinto

from assenze_desk.adapters.outlook import Outlook
from assenze_desk.config import MailUfficio, PortaleAziendale
from assenze_desk.core.episodio import Certificato
from assenze_desk.core.giustificativi import TIPI_PREDEFINITI, righe_giustificativo
from assenze_desk.demo.ambiente import PostaDemo
from assenze_desk.demo.certificati import CertificatoFinto, scrivi_certificato_finto
from assenze_desk.servizi import ErroreServizi, apri_contesto
from assenze_desk.storage.archivio import Pratica

OGGI = date(2026, 10, 7)
CF = "FNTPRV80A01Z999Y"


class Orologio:
    def __init__(self):
        self.ora = datetime(2026, 10, 7, 9, 0)

    def __call__(self):
        return self.ora


@pytest.fixture
def aperti():
    return []


@pytest.fixture
def contesto(tmp_path, aperti):
    contesto, avvisi = apri_contesto(
        tmp_path / "dati", demo=True, oggi=OGGI, adesso=Orologio(), apri_url=aperti.append
    )
    assert avvisi == []
    yield contesto
    contesto.chiudi()


def certificato_pdf(cartella, protocollo="412345678", nome="certificato.pdf"):
    finto = CertificatoFinto(
        protocollo, CF, "Fittizio", "Luca", date(2026, 10, 5), date(2026, 10, 9)
    )
    return scrivi_certificato_finto(finto, cartella / nome)


# --- Apertura ---


def test_apre_la_demo(contesto):
    assert isinstance(contesto.posta, PostaDemo)
    assert contesto.demo
    assert len(contesto.anagrafica.dipendenti) == 24
    assert contesto.archivio.pratiche()
    assert (contesto.impostazioni.percorsi.log / "assenze-desk.log").is_file()


def test_primo_avvio_crea_le_impostazioni(tmp_path):
    contesto, avvisi = apri_contesto(tmp_path / "dati")
    try:
        assert (tmp_path / "dati" / "impostazioni.json").is_file()
        assert any("impostazioni" in avviso for avviso in avvisi)
        assert any("Anagrafica non trovata" in avviso for avviso in avvisi)
        assert isinstance(contesto.posta, Outlook)
        assert not contesto.demo
        assert contesto.anagrafica.dipendenti == ()
    finally:
        contesto.chiudi()


def test_anagrafica_rovinata_diventa_un_avviso(tmp_path):
    cartella = tmp_path / "dati"
    cartella.mkdir()
    (cartella / "anagrafica.xlsx").write_text("non sono un Excel", encoding="utf-8")
    contesto, avvisi = apri_contesto(cartella)
    try:
        assert any("Anagrafica non leggibile" in avviso for avviso in avvisi)
        assert contesto.anagrafica.dipendenti == ()
    finally:
        contesto.chiudi()


# --- Mail e certificati ---


def test_importa_una_mail_della_demo_con_il_certificato(contesto):
    mail = contesto.importa_mail("malattia")
    pdf = contesto.allegati_pdf(mail)
    assert len(pdf) == 1
    assert pdf[0].parent == contesto.cartella_in_arrivo
    assert contesto.leggi_certificato(pdf[0]).protocollo


def test_allegati_non_pdf_ignorati(tmp_path):
    mail_vera = Mail(
        "ID-1", "Certificato", allegati=[Allegato("cert.pdf"), Allegato("firma.png", b"png")]
    )
    contesto, _ = apri_contesto(tmp_path / "dati")
    try:
        contesto.posta = Outlook(OutlookFinto(mail_vera))
        mail = contesto.importa_mail("malattia")
        assert [p.name for p in contesto.allegati_pdf(mail)] == ["cert.pdf"]
    finally:
        contesto.chiudi()


def test_un_pdf_scelto_dall_utente_si_copia_non_si_sposta(contesto, tmp_path):
    originale = certificato_pdf(tmp_path / "scrivania")
    copia = contesto.prepara_pdf(originale)
    assert originale.is_file()
    assert copia.parent == contesto.cartella_in_arrivo


def test_salvare_la_pratica_archivia_il_certificato(contesto, tmp_path):
    copia = contesto.prepara_pdf(certificato_pdf(tmp_path))
    pratica = Pratica("412345678", cf=CF, inizio=date(2026, 10, 5), fine=date(2026, 10, 9))
    archiviato = contesto.salva_pratica(pratica, copia)
    assert archiviato == contesto.impostazioni.percorsi.certificati / "412345678.pdf"
    assert archiviato.is_file()
    assert not copia.exists()
    assert contesto.archivio.pratica("412345678").cf == CF
    assert contesto.archivio.storico()[0].protocollo == "412345678"
    # un PDF già archiviato con quel nome non si sposta di nuovo
    assert contesto.salva_pratica(pratica, archiviato) == archiviato


def test_salvare_senza_protocollo(contesto):
    with pytest.raises(ErroreServizi, match="protocollo"):
        contesto.salva_pratica(Pratica(" "), None)


def test_salvare_senza_certificato(contesto):
    assert contesto.salva_pratica(Pratica("412345678", cf=CF), None) is None
    assert contesto.archivio.pratica("412345678") is not None


def test_un_file_non_pdf_non_si_archivia(contesto, tmp_path):
    nota = tmp_path / "nota.txt"
    nota.write_text("x", encoding="utf-8")
    with pytest.raises(ErroreServizi, match="non archiviato"):
        contesto.archivia_scaricato(nota, "412345678")


def test_episodio_e_certificati_da_allegare(contesto):
    pratica = next(p for p in contesto.archivio.pratiche() if p.fine)
    certificato = Certificato(pratica.protocollo, pratica.cf, pratica.inizio, pratica.fine)
    episodio = contesto.episodio(certificato)
    assert pratica.protocollo in episodio.protocolli
    trovati, mancanti = contesto.pdf_episodio(episodio)
    assert [p.stem for p in trovati] == list(episodio.protocolli)
    assert mancanti == ()
    nuovo = Certificato("499999999", "ZZZZZZ00A00Z999Z", date(2026, 1, 1), date(2026, 1, 2))
    assert contesto.pdf_episodio(contesto.episodio(nuovo)) == ((), ("499999999",))


# --- Bozze e spostamento: mai invii ---


def test_bozza_di_risposta_alla_mail_importata(contesto):
    mail = contesto.importa_mail("malattia")
    mancanti = contesto.crea_bozza(
        a=["lavoratore@example.com"],
        oggetto="Ricevuto {PROTOCOLLO}",
        corpo="Gentile {NOME},\nricevuto.",
        valori={"PROTOCOLLO": "412345678", "NOME": None},
        rispondi_a=mail,
    )
    assert mancanti == ("NOME",)
    bozza = contesto.posta.bozze[-1]
    assert bozza.risposta_a == mail.entry_id
    assert "<br>" in bozza.corpo_html


def test_bozza_nuova_con_allegati(contesto, tmp_path):
    allegato = certificato_pdf(tmp_path)
    contesto.crea_bozza(
        a=["ufficio@example.com"],
        oggetto="Malattia",
        corpo="In allegato.",
        valori={},
        cc=["copia@example.com"],
        allegati=[allegato],
    )
    bozza = contesto.posta.bozze[-1]
    assert (bozza.a, bozza.cc, bozza.allegati) == (
        ("ufficio@example.com",),
        ("copia@example.com",),
        (allegato,),
    )


def test_bozza_senza_destinatari(contesto):
    with pytest.raises(ErroreServizi, match="destinatar"):
        contesto.crea_bozza(a=[], oggetto="x", corpo="y", valori={})


def test_bozza_con_il_programma_di_posta_predefinito(contesto, aperti, tmp_path):
    contesto.impostazioni = replace(contesto.impostazioni, posta="mailto")
    contesto.crea_bozza(
        a=["ufficio@example.com"],
        oggetto="Malattia {PROTOCOLLO}",
        corpo="Riga uno\nRiga due",
        valori={"PROTOCOLLO": "412345678"},
        allegati=[certificato_pdf(tmp_path)],
    )
    assert aperti[-1].startswith("mailto:ufficio@example.com?")
    assert "412345678" in aperti[-1]
    # la risposta va al mittente della mail importata
    mail = contesto.importa_mail("malattia")
    contesto.crea_bozza(a=[], oggetto="Ricevuto", corpo="Ok", valori={}, rispondi_a=mail)
    assert aperti[-1].startswith(f"mailto:{mail.mittente}?")


def test_sposta_la_mail_nella_cartella_del_flusso(contesto):
    mail = contesto.importa_mail("giustificativo")
    assert contesto.sposta_mail(mail, "giustificativo") == "Gestite/Giustificativi"
    contesto.impostazioni = replace(
        contesto.impostazioni,
        cartelle_outlook=replace(contesto.impostazioni.cartelle_outlook, malattie=""),
    )
    with pytest.raises(ErroreServizi, match="Impostazioni"):
        contesto.sposta_mail(mail, "malattia")


def test_con_mailto_niente_import_ne_spostamento(contesto):
    contesto.impostazioni = replace(contesto.impostazioni, posta="mailto", ufficio=MailUfficio())
    mail = contesto.importa_mail("malattia")  # in demo l'import resta disponibile
    contesto.demo = False
    with pytest.raises(ErroreServizi, match="Outlook"):
        contesto.importa_mail("malattia")
    with pytest.raises(ErroreServizi, match="Outlook"):
        contesto.sposta_mail(mail, "malattia")


# --- Assistente INPS ---


def test_assistente_inps(contesto, aperti, tmp_path):
    download = tmp_path / "Download"
    download.mkdir()
    contesto.impostazioni = replace(
        contesto.impostazioni, percorsi=replace(contesto.impostazioni.percorsi, download=download)
    )
    with pytest.raises(ErroreServizi, match="portale"):
        contesto.pdf_scaricati()
    contesto.apri_portale()
    assert aperti == [contesto.impostazioni.portale_inps]

    scaricato = certificato_pdf(download, nome="AttestatoMalattia.pdf")
    quando = datetime(2026, 10, 7, 9, 3).timestamp()
    os.utime(scaricato, (quando, quando))
    assert contesto.pdf_scaricati() == [scaricato]
    archiviato = contesto.archivia_scaricato(scaricato, "412345678")
    assert archiviato.name == "412345678.pdf"
    assert not scaricato.exists()


def test_portale_aziendale(contesto, aperti):
    with pytest.raises(ErroreServizi, match="Impostazioni"):
        contesto.apri_portale_aziendale()  # senza indirizzo non si apre niente
    assert aperti == []
    contesto.impostazioni = replace(
        contesto.impostazioni,
        portale_aziendale=PortaleAziendale("Intranet", "https://intranet.example/app"),
    )
    contesto.apri_portale_aziendale()
    assert aperti == ["https://intranet.example/app"]


# --- Giustificativi ---


def test_orario_capienza_e_righe(contesto):
    dipendente = contesto.anagrafica.dipendenti[0]
    ferie = TIPI_PREDEFINITI[0]
    orario = contesto.orario(dipendente)
    assert orario is not None
    assert contesto.capienza(dipendente, ferie) > 0
    assert contesto.capienza(dipendente, TIPI_PREDEFINITI[2]) is None  # nessuna capienza PVM

    righe = righe_giustificativo(ferie, [date(2026, 10, 12), date(2026, 10, 13)], None, orario)
    prima = len(contesto.archivio.righe())
    ids = contesto.salva_righe(dipendente, righe)
    assert len(ids) == 2
    salvate = contesto.archivio.righe()
    assert len(salvate) == prima + 2
    assert {r.dipendente for r in salvate if r.id in ids} == {
        f"{dipendente.cognome} {dipendente.nome}"
    }


def test_righe_senza_ore_non_si_salvano(contesto):
    dipendente = contesto.anagrafica.dipendenti[0]
    righe = righe_giustificativo(TIPI_PREDEFINITI[1], [date(2026, 10, 12)], None, None)
    with pytest.raises(ErroreServizi, match="ore"):
        contesto.salva_righe(dipendente, righe)
    with pytest.raises(ErroreServizi, match="giorni"):
        contesto.salva_righe(dipendente, [])


# --- Export, statistiche, impostazioni ---


def test_export_in_excel(contesto):
    file = contesto.esporta_pratiche(contesto.archivio.pratiche())
    assert file.parent == contesto.impostazioni.percorsi.export
    assert file.suffix == ".xlsx"
    da_esportare = contesto.archivio.righe(solo_da_esportare=True)
    file = contesto.esporta_righe(da_esportare)
    assert file.is_file()
    assert contesto.archivio.righe(solo_da_esportare=True) == []


def test_pratiche_per_le_statistiche(contesto):
    pratiche = contesto.pratiche_statistiche()
    assert len(pratiche) == len(contesto.archivio.pratiche())
    assert pratiche[0].dipendente


def test_impostazioni_con_percorsi_nuovi(contesto, tmp_path):
    altrove = tmp_path / "altrove"
    percorsi = replace(
        contesto.impostazioni.percorsi,
        archivio=altrove / "archivio.db",
        log=altrove / "log",
        anagrafica=altrove / "manca.xlsx",
    )
    avvisi = contesto.salva_impostazioni(replace(contesto.impostazioni, percorsi=percorsi))
    assert any("Anagrafica non trovata" in avviso for avviso in avvisi)
    assert contesto.anagrafica.dipendenti == ()
    assert contesto.archivio.pratiche() == []  # archivio nuovo, vuoto
    assert (altrove / "log" / "assenze-desk.log").is_file()


def test_ricarica_l_anagrafica(contesto):
    contesto.impostazioni.percorsi.anagrafica.unlink()
    assert contesto.ricarica_anagrafica()
    assert contesto.anagrafica.dipendenti == ()


def test_salvare_le_impostazioni_le_applica(contesto):
    nuove = replace(contesto.impostazioni, soglia_ufficio=5)
    avvisi = contesto.salva_impostazioni(nuove)
    assert avvisi == []
    assert contesto.archivio.soglia_ufficio == 5
    assert '"soglia_ufficio": 5' in contesto.file_impostazioni.read_text(encoding="utf-8")


# --- Mail ricordate e correzioni dell'anagrafica ---


def test_ricorda_il_mittente_diverso_dall_anagrafica(contesto):
    dipendente = contesto.anagrafica.dipendenti[0]
    assert contesto.ricorda_mittente(dipendente, "Casa <Casa.Mia@example.org>") == (
        "casa.mia@example.org"
    )
    assert contesto.email_note == {"casa.mia@example.org": dipendente.cf}
    assert contesto.ricorda_mittente(dipendente, "casa.mia@example.org") == ""  # già noto
    assert contesto.ricorda_mittente(dipendente, dipendente.email) == ""
    assert contesto.archivio.storico()[0].azione == "Indirizzo del mittente ricordato"
    assert dipendente.cf not in contesto.archivio.storico()[0].dettaglio


def test_correzione_sopra_l_excel(contesto):
    originale = contesto.anagrafica.dipendenti[0]
    corretto = replace(originale, email="nuova@example.org", cliente="Cliente Nuovo")
    contesto.correggi_dipendente(corretto, ["altra@example.org", "nuova@example.org"])
    assert contesto.anagrafica.dipendenti[0] == corretto
    assert contesto.corretto(corretto)
    assert contesto.archivio.email_di(corretto.cf) == ["altra@example.org"]  # senza la principale
    assert contesto.anagrafica_excel.dipendenti[0] == originale  # l'Excel non cambia

    contesto.ricarica_anagrafica()  # anche ricaricando l'Excel la correzione resta
    assert contesto.anagrafica.dipendenti[0] == corretto

    contesto.togli_correzione(corretto)
    assert contesto.anagrafica.dipendenti[0] == originale
    assert not contesto.corretto(originale)


def test_correzione_di_un_dipendente_non_in_anagrafica(contesto):
    from assenze_desk.core.dipendenti import Dipendente

    estraneo = Dipendente("ZZZZZZ80A01Z999Z", "Nuovo", "Dipendente", joborder="X1")
    with pytest.raises(ErroreServizi, match="anagrafica"):
        contesto.correggi_dipendente(estraneo, [])
