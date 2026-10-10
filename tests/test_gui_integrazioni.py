"""Interfaccia con le integrazioni: INPS, PDF, bozze, spostamento, OCR, testo selezionato.

Tutto in demo e senza programmi esterni: il browser non si apre, l'OCR e la
tastiera sono sostituiti nei test (issue #4 e #5).
"""

import os
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QPixmap

from assenze_desk.demo.certificati import CertificatoFinto, scrivi_certificato_finto
from assenze_desk.gui import nuova_pratica as modulo_nuova_pratica
from assenze_desk.gui.cattura import SelezioneZona, in_pillow
from assenze_desk.gui.finestra import FinestraPrincipale
from assenze_desk.servizi import apri_contesto

OGGI = date(2026, 10, 7)
CF = "FNTPRV80A01Z999Y"


class Orologio:
    def __call__(self):
        return datetime(2026, 10, 7, 9, 0)


@pytest.fixture
def aperti():
    return []


@pytest.fixture
def finestra(qapp, tmp_path, distruggi, aperti):
    contesto, avvisi = apri_contesto(
        tmp_path / "dati", demo=True, oggi=OGGI, adesso=Orologio(), apri_url=aperti.append
    )
    download = tmp_path / "Download"
    download.mkdir()
    percorsi = replace(contesto.impostazioni.percorsi, download=download)
    contesto.impostazioni = replace(contesto.impostazioni, percorsi=percorsi)
    finestra = FinestraPrincipale(contesto, avvisi)
    distruggi(finestra)
    finestra.show()
    yield finestra
    contesto.chiudi()


def certificato(cartella: Path, nome: str, protocollo="412345678", giorni=5) -> Path:
    finto = CertificatoFinto(
        protocollo, CF, "Fittizio", "Luca", date(2026, 10, 5), date(2026, 10, 4 + giorni)
    )
    return scrivi_certificato_finto(finto, cartella / nome)


# --- Certificati e bozze della malattia ---


def test_pdf_scelto_a_mano_senza_testo_della_mail(finestra, tmp_path):
    pagina = finestra.nuova_pratica
    pagina.carica_pdf_scelto(certificato(tmp_path, "scelto.pdf"))
    malattia = pagina.malattia
    assert malattia.modulo["protocollo"].valore == "412345678"
    assert malattia.modulo["fine"].valore == date(2026, 10, 9)
    assert (tmp_path / "scelto.pdf").is_file()  # l'originale resta dov'è


def test_bozza_all_ufficio_con_i_pdf_dell_episodio(finestra, tmp_path):
    pagina = finestra.nuova_pratica
    pagina.mail.imposta_testo("Buongiorno, certificato in allegato.\nMario")
    pagina.carica_pdf_scelto(certificato(tmp_path, "scelto.pdf"))
    malattia = pagina.malattia
    assert malattia.bozza_ufficio.isEnabled()  # 5 giorni: oltre la soglia di 3
    malattia.bozza_ufficio.click()
    bozza = finestra.contesto.posta.bozze[-1]
    assert bozza.a == finestra.contesto.impostazioni.ufficio.destinatari
    assert [p.name for p in bozza.allegati] == ["412345678.pdf"]
    salvata = finestra.contesto.archivio.pratica("412345678")
    assert salvata.mail_ufficio
    assert "Bozza all'ufficio" in finestra.messaggi.testo.text()


def test_con_mailto_i_pdf_si_allegano_a_mano(finestra, tmp_path, aperti):
    contesto = finestra.contesto
    contesto.impostazioni = replace(contesto.impostazioni, posta="mailto")
    pagina = finestra.nuova_pratica
    pagina.mail.imposta_testo("certificato in allegato")
    pagina.carica_pdf_scelto(certificato(tmp_path, "scelto.pdf"))
    pagina.malattia.bozza_ufficio.click()
    assert aperti[-1].startswith("mailto:")
    assert "a mano" in finestra.messaggi.testo.text()
    assert finestra.messaggi._azione.isVisibleTo(finestra.messaggi)


def test_assistente_inps(finestra, tmp_path, aperti):
    pagina = finestra.nuova_pratica
    malattia = pagina.malattia
    malattia.scaricato.click()
    assert "portale" in finestra.messaggi.testo.text()  # prima si apre il portale
    malattia.apri_portale.click()
    assert aperti == [finestra.contesto.impostazioni.portale_inps]

    malattia.scaricato.click()
    assert "Nessun PDF" in finestra.messaggi.testo.text()

    download = finestra.contesto.impostazioni.percorsi.download
    scaricato = certificato(download, "AttestatoMalattia.pdf")
    os.utime(scaricato, (datetime(2026, 10, 7, 9, 5).timestamp(),) * 2)
    malattia.scaricato.click()
    assert "protocollo" in finestra.messaggi.testo.text()  # serve il protocollo per il nome

    pagina.mail.imposta_testo("certificato protocollo 412345678")
    pagina.analizza()
    malattia.copia_protocollo.click()
    assert QGuiApplication.clipboard().text() == "412345678"
    malattia.scaricato.click()
    archiviato = finestra.contesto.impostazioni.percorsi.certificati / "412345678.pdf"
    assert archiviato.is_file()
    assert malattia.modulo["cf"].valore == CF  # letto dal PDF
    assert pagina.mail.pdf.text() == "412345678.pdf"


def test_piu_pdf_scaricati_sceglie_l_utente(finestra):
    pagina = finestra.nuova_pratica
    malattia = pagina.malattia
    pagina.mail.imposta_testo("protocollo 412345678")
    pagina.analizza()
    malattia.apri_portale.click()
    download = finestra.contesto.impostazioni.percorsi.download
    for numero, nome in enumerate(("primo.pdf", "secondo.pdf")):
        file = certificato(download, nome)
        os.utime(file, (datetime(2026, 10, 7, 9, 5 + numero).timestamp(),) * 2)
    malattia.scaricato.click()
    assert malattia.scaricati.count() == 2
    malattia.scaricati.itemClicked.emit(malattia.scaricati.item(0))
    assert not malattia.scaricati.isVisibleTo(malattia)
    assert malattia.modulo["cf"].valore == CF


def test_copiare_un_campo_vuoto(finestra):
    finestra.nuova_pratica.malattia.copia_cf.click()
    assert "vuoto" in finestra.messaggi.testo.text()


def test_spostare_la_mail_importata(finestra):
    pagina = finestra.nuova_pratica
    pagina.malattia.sposta.click()  # senza mail importata il pulsante è spento
    assert not pagina.malattia.sposta.isEnabled()
    pagina.mail.importa.click()
    pagina.malattia.sposta.click()
    assert finestra.contesto.posta.spostate[-1][1] == "Gestite/Malattie"
    assert not pagina.malattia.sposta.isEnabled()


# --- Giustificativo: bozza, spostamento, capienza ---


def test_giustificativo_bozza_spostamento_e_capienza(finestra):
    pagina = finestra.nuova_pratica
    pagina.mostra_flusso("giustificativo")
    pagina.mail.importa.click()
    giustificativo = pagina.giustificativo
    giustificativo.bozza_lavoratore.click()
    bozza = finestra.contesto.posta.bozze[-1]
    assert bozza.risposta_a == pagina.info.mail.entry_id
    giustificativo.sposta.click()
    assert finestra.contesto.posta.spostate[-1][1] == "Gestite/Giustificativi"
    if giustificativo._tipo() and giustificativo._tipo().nome in ("Ferie", "ROL"):
        assert giustificativo.avviso_capienza.testo.text()


def test_capienza_superata(finestra, qtbot):
    pagina = finestra.nuova_pratica
    pagina.mostra_flusso("giustificativo")
    pagina.mail.imposta_testo("chiedo un permesso ROL il 12/10/2026")
    pagina.analizza()
    giustificativo = pagina.giustificativo
    persona = finestra.contesto.anagrafica.dipendenti[0]
    giustificativo._dipendente_scelto(persona)
    capienza = finestra.contesto.capienza(persona, finestra.contesto.impostazioni.tipi[1])
    ore = giustificativo.campi["minuti"].editor
    qtbot.keyClicks(ore, "24")
    if capienza is not None and capienza < 24 * 60:
        assert "supera" in giustificativo.avviso_capienza.testo.text()
        assert giustificativo.avviso_capienza.property("avviso") == "attenzione"


def test_salvare_righe_senza_dipendente(finestra):
    pagina = finestra.nuova_pratica
    pagina.mostra_flusso("giustificativo")
    pagina.mail.imposta_testo("chiedo 2 ore di ROL il 12/10/2026")
    pagina.analizza()
    pagina.giustificativo.salva.click()
    assert "dipendente" in finestra.messaggi.testo.text()


# --- OCR e testo selezionato ---


def test_ocr_senza_tesseract(finestra, monkeypatch):
    monkeypatch.setattr(modulo_nuova_pratica, "trova_tesseract", lambda _impostato: None)
    finestra.nuova_pratica.mail.ocr.click()
    assert "Tesseract" in finestra.messaggi.testo.text()
    assert finestra.isVisible()


def test_ocr_di_una_zona(finestra, monkeypatch, qtbot):
    pagina = finestra.nuova_pratica
    letto = "OGG: Certificato\n\nprotocollo 412345678 dal 5 al 9 ottobre"
    monkeypatch.setattr(modulo_nuova_pratica, "trova_tesseract", lambda _impostato: Path("t.exe"))
    monkeypatch.setattr(
        modulo_nuova_pratica, "leggi_testo_immagine", lambda immagine, *_a, **_k: letto
    )
    pagina._cattura(Path("t.exe"))
    zona = pagina._selezione_zona
    qtbot.mousePress(zona, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    qtbot.mouseMove(zona, QPoint(120, 80))
    qtbot.mouseRelease(zona, Qt.MouseButton.LeftButton, pos=QPoint(120, 80))
    assert pagina.mail.testo() == letto
    assert pagina.malattia.modulo["protocollo"].valore == "412345678"
    assert "OCR" in pagina.mail.meta.text()


def test_ocr_che_non_legge_niente(finestra, monkeypatch, qtbot):
    pagina = finestra.nuova_pratica

    def senza_testo(*_a, **_k):
        raise modulo_nuova_pratica.ErroreOcr("Nessun testo utile trovato.")

    monkeypatch.setattr(modulo_nuova_pratica, "leggi_testo_immagine", senza_testo)
    pagina._leggi_zona(QPixmap(40, 40), Path("t.exe"))
    assert "Nessun testo" in finestra.messaggi.testo.text()


def test_selezione_della_zona(qapp, qtbot, distruggi):
    schermata = QPixmap(200, 100)
    schermata.fill(Qt.GlobalColor.white)
    zona = SelezioneZona(schermata, schermata.rect())
    distruggi(zona)
    zona.show()
    qtbot.mouseClick(zona, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))  # un clic non basta
    assert zona.zona().isEmpty()
    with qtbot.waitSignal(zona.annullata):
        qtbot.keyClick(zona, Qt.Key.Key_Escape)
    immagine = in_pillow(schermata)
    assert immagine.size == (200, 100)
    assert immagine.mode == "RGB"


def test_testo_selezionato(finestra, monkeypatch):
    pagina = finestra.nuova_pratica
    monkeypatch.setattr(modulo_nuova_pratica.sys, "platform", "linux")
    pagina.mail.selezione.click()
    assert "solo su Windows" in finestra.messaggi.testo.text()

    QGuiApplication.clipboard().setText("vecchio")
    pagina._appunti_prima = "vecchio"
    pagina._leggi_selezione()
    assert "Nessun testo nuovo" in finestra.messaggi.testo.text()
    QGuiApplication.clipboard().setText("chiedo ferie domani")
    pagina._leggi_selezione()
    assert pagina.mail.testo() == "chiedo ferie domani"
    assert pagina.analisi_eseguite == 1


def test_analisi_senza_testo(finestra):
    finestra.nuova_pratica.mail.analizza.click()
    assert "testo della mail" in finestra.messaggi.testo.text()


def test_incolla_dagli_appunti(finestra):
    pagina = finestra.nuova_pratica
    QGuiApplication.clipboard().setText("")
    pagina.mail.incolla.click()
    assert "vuoti" in pagina.mail.meta.text()
    QGuiApplication.clipboard().setText("protocollo 412345678")
    pagina.mail.incolla.click()
    assert pagina.malattia.modulo["protocollo"].valore == "412345678"


def test_errore_imprevisto_nella_barra(finestra):
    try:
        raise RuntimeError("guasto di prova")
    except RuntimeError as errore:
        finestra.errore_imprevisto(type(errore), errore, errore.__traceback__)
    assert "guasto di prova" in finestra.messaggi.testo.text()
    assert "log" in finestra.messaggi.testo.text()
