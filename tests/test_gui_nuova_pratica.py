"""Smoke test dell'interfaccia: l'app parte in demo e i flussi principali funzionano.

Issue #5, #13 (analisi solo quando lo decide l'utente), #14 (dipendente a mano
anche nei giustificativi). Le finestre non compaiono sullo schermo (offscreen).
"""

from dataclasses import replace
from datetime import date, datetime

import pytest
from PySide6.QtCore import QMimeData, Qt
from PySide6.QtWidgets import QApplication

from assenze_desk import app as modulo_app
from assenze_desk.core.campi import Origine
from assenze_desk.core.dipendenti import Dipendente
from assenze_desk.gui.finestra import FinestraPrincipale
from assenze_desk.servizi import apri_contesto

OGGI = date(2026, 10, 7)
MALATTIA = (
    "OGG: Certificato di malattia\n"
    "Da: Mario Rossi <mario.rossi@example.com>\n"
    "Data: 07/10/2026 09:12\n\n"
    "Buongiorno,\ninvio il certificato protocollo 412345678 dal 5 al 9 ottobre.\n"
)
FERIE_CON_WEEKEND = (
    "OGG: Richiesta ferie\nData: 02/10/2026 16:40\n\nchiedo le ferie dal 9 al 13 ottobre"
)


class Orologio:
    def __init__(self):
        self.ora = datetime(2026, 10, 7, 9, 0)

    def __call__(self):
        return self.ora


@pytest.fixture
def finestra(qtbot, tmp_path, distruggi):
    contesto, avvisi = apri_contesto(
        tmp_path / "dati", demo=True, oggi=OGGI, adesso=Orologio(), apri_url=lambda _url: None
    )
    finestra = FinestraPrincipale(contesto, avvisi)
    distruggi(finestra)
    finestra.show()
    yield finestra
    contesto.chiudi()


def scrivi(qtbot, finestra, testo):
    editor = finestra.nuova_pratica.mail.editor
    editor.setFocus()
    qtbot.keyClicks(editor, testo)


# --- Avvio ---


def test_l_app_parte_in_demo_con_quattro_sezioni(finestra):
    assert "demo" in finestra.windowTitle()
    assert [v.text() for v in finestra.voci] == [
        "Nuova pratica",
        "Archivio",
        "Statistiche",
        "Impostazioni",
    ]
    assert finestra.sezioni.currentIndex() == 0
    for indice in range(4):
        finestra.voci[indice].click()
        assert finestra.sezioni.currentIndex() == indice


def test_avvio_da_riga_di_comando_in_demo(monkeypatch, qapp, distruggi):
    monkeypatch.setattr(QApplication, "exec", lambda _self: 0)
    aperte = []
    monkeypatch.setattr(FinestraPrincipale, "show", lambda self: aperte.append(self))
    assert modulo_app.main(["--demo"]) == 0
    assert aperte and aperte[0].contesto.demo
    distruggi(aperte[0])


# --- Analisi solo quando lo decide l'utente (problema noto 6) ---


def test_scrivere_non_avvia_l_analisi(finestra, qtbot):
    pagina = finestra.nuova_pratica
    scrivi(qtbot, finestra, "protocollo 412345678")
    assert pagina.analisi_eseguite == 0
    assert pagina.malattia.modulo["protocollo"].valore is None


def test_ctrl_invio_avvia_l_analisi(finestra, qtbot):
    pagina = finestra.nuova_pratica
    scrivi(qtbot, finestra, "protocollo 412345678")
    qtbot.keyClick(pagina.mail.editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert pagina.analisi_eseguite == 1
    assert pagina.malattia.modulo["protocollo"].valore == "412345678"
    assert pagina.malattia.campi["protocollo"].origine.text() == "Testo"


def test_incollare_in_una_casella_vuota_avvia_l_analisi(finestra):
    pagina = finestra.nuova_pratica
    dati = QMimeData()
    dati.setText(MALATTIA)
    pagina.mail.editor.insertFromMimeData(dati)
    assert pagina.analisi_eseguite == 1
    assert pagina.malattia.modulo["inizio"].valore == date(2026, 10, 5)
    # incollare un pezzo dentro un testo già scritto non la riavvia
    pagina.mail.editor.insertFromMimeData(dati)
    assert pagina.analisi_eseguite == 1


def test_nessuna_finestra_si_apre_da_sola(finestra):
    prima = {w for w in QApplication.topLevelWidgets() if w.isVisible()}
    finestra.nuova_pratica.mail.imposta_testo(MALATTIA)
    finestra.nuova_pratica.analizza()
    finestra.nuova_pratica.mostra_flusso("giustificativo")
    finestra.nuova_pratica.mail.imposta_testo(FERIE_CON_WEEKEND)
    finestra.nuova_pratica.analizza()
    assert {w for w in QApplication.topLevelWidgets() if w.isVisible()} == prima
    assert finestra.sezioni.currentIndex() == 0


# --- Campi manuali protetti ---


def test_un_campo_scritto_a_mano_resta_dopo_una_nuova_analisi(finestra, qtbot):
    pagina = finestra.nuova_pratica
    pagina.mail.imposta_testo(MALATTIA)
    pagina.analizza()
    campo = pagina.malattia.campi["fine"]
    campo.editor.clear()
    qtbot.keyClicks(campo.editor, "10/10/2026")
    pagina.analizza()
    assert pagina.malattia.modulo["fine"].valore == date(2026, 10, 10)
    assert campo.origine.text() == "Manuale"
    assert campo.automatico.text() == "Automatico: 09/10/2026"
    campo.bottone_ripristina.click()
    assert pagina.malattia.modulo["fine"].valore == date(2026, 10, 9)
    assert campo.editor.text() == "09/10/2026"


# --- Malattia in demo: import, PDF, bozze, salvataggio ---


def test_import_dalla_demo_con_certificato(finestra):
    pagina = finestra.nuova_pratica
    pagina.mail.importa.click()
    malattia = pagina.malattia
    assert malattia.modulo["protocollo"].origine is Origine.PDF
    assert malattia.modulo["tipo_certificato"].valore == "Inizio"
    assert malattia.scelta["dipendente"].origine is Origine.ANAGRAFICA
    assert pagina.mail.pdf.text().endswith(".pdf")
    assert pagina.stato.text() == "Da inviare"


def test_bozza_salvataggio_e_stato(finestra):
    pagina = finestra.nuova_pratica
    pagina.mail.importa.click()
    malattia = pagina.malattia
    malattia.bozza_lavoratore.click()
    posta = finestra.contesto.posta
    assert posta.bozze[-1].risposta_a == pagina.info.mail.entry_id  # risposta alla mail importata
    protocollo = malattia.modulo["protocollo"].valore
    salvata = finestra.contesto.archivio.pratica(protocollo)
    assert salvata is not None and salvata.mail_lavoratore
    pdf = finestra.contesto.impostazioni.percorsi.certificati / f"{protocollo}.pdf"
    assert pdf.is_file()
    assert pagina.stato.text() in ("Parziale", "Chiusa")
    assert "Bozza al lavoratore" in finestra.messaggi.testo.text()


def test_salvare_senza_protocollo_mostra_l_errore(finestra):
    finestra.nuova_pratica.malattia.salva.click()
    assert finestra.messaggi.isVisible()
    assert "protocollo" in finestra.messaggi.testo.text()
    assert finestra.messaggi.property("avviso") == "errore"


def test_pratica_vuota(finestra):
    pagina = finestra.nuova_pratica
    pagina.mail.importa.click()
    pagina.vuota.click()
    assert pagina.mail.testo() == ""
    assert pagina.malattia.modulo["protocollo"].valore is None


# --- Giustificativo: weekend e dipendente a mano (problema noto 7) ---


def test_weekend_con_interruttore(finestra):
    pagina = finestra.nuova_pratica
    pagina.mostra_flusso("giustificativo")
    pagina.mail.imposta_testo(FERIE_CON_WEEKEND)
    pagina.analizza()
    giustificativo = pagina.giustificativo
    assert giustificativo.modulo["tipo"].valore == "Ferie"
    assert [r.giorno.day for r in giustificativo.righe()] == [9, 12, 13]
    assert giustificativo.avviso_weekend.isVisible()
    giustificativo.conta_weekend.click()
    assert [r.giorno.day for r in giustificativo.righe()] == [9, 10, 11, 12, 13]


def test_giustificativo_con_dipendente_scelto_a_mano(finestra, qtbot):
    pagina = finestra.nuova_pratica
    pagina.mostra_flusso("giustificativo")
    pagina.mail.imposta_testo("chiedo 2 ore di ROL il 12/10/2026")
    pagina.analizza()
    giustificativo = pagina.giustificativo
    assert giustificativo._dipendente() is None
    persona = finestra.contesto.anagrafica.dipendenti[3]
    qtbot.keyClicks(giustificativo.dipendente.cerca, persona.cf)
    risultati = giustificativo.dipendente.risultati
    assert risultati.count() >= 1
    risultati.itemClicked.emit(risultati.item(0))
    assert giustificativo._dipendente() == persona
    assert giustificativo.scelta["dipendente"].origine is Origine.MANUALE
    giustificativo.salva.click()
    salvate = [r for r in finestra.contesto.archivio.righe() if r.cf == persona.cf]
    assert [(r.giorno, r.minuti) for r in salvate][-1] == (date(2026, 10, 12), 120)
    assert not giustificativo.salva.isEnabled()  # niente doppioni con un secondo clic


def test_dipendente_inserito_a_mano_senza_anagrafica(finestra, qtbot):
    pannello = finestra.nuova_pratica.giustificativo.dipendente
    pannello.a_mano.click()
    for nome, valore in (("cognome", "Fittizio"), ("nome", "Luca"), ("cf", "FNTPRV80A01Z999Y")):
        qtbot.keyClicks(pannello.manuali[nome], valore)
    with qtbot.waitSignal(pannello.scelto) as segnale:
        pannello.modulo.findChildren(type(pannello.a_mano))[-1].click()
    assert segnale.args[0] == Dipendente("FNTPRV80A01Z999Y", "Fittizio", "Luca")


def test_cf_sbagliato_nell_inserimento_a_mano(finestra, qtbot):
    pannello = finestra.nuova_pratica.malattia.dipendente
    pannello.a_mano.click()
    for nome, valore in (("cognome", "Fittizio"), ("nome", "Luca"), ("cf", "FNTPRV80A01Z999X")):
        qtbot.keyClicks(pannello.manuali[nome], valore)
    pannello.modulo.findChildren(type(pannello.a_mano))[-1].click()
    assert "non valido" in pannello.errore_manuale.text()


# --- Tema e log ---


def test_cambio_tema_salvato(finestra):
    finestra.tema.pulsante(2).click()
    assert finestra.contesto.impostazioni.tema == "scuro"
    assert '"tema": "scuro"' in finestra.contesto.file_impostazioni.read_text(encoding="utf-8")


def test_il_log_mostra_le_azioni_con_il_cf_mascherato(finestra):
    pagina = finestra.nuova_pratica
    pagina.mostra_flusso("giustificativo")
    pagina.mail.imposta_testo("chiedo ferie domani, il mio codice fiscale è FNTPRV80A01Z999Y")
    pagina.analizza()
    import logging

    logging.getLogger("assenze_desk.prova").info("CF FNTPRV80A01Z999Y")
    testo = finestra.log.testo.toPlainText()
    assert "Analisi della mail" in testo
    assert "FNTPRV80A01Z999Y" not in testo
    finestra.log.interruttore.click()
    assert not finestra.log.testo.isVisible()


def test_import_non_disponibile_con_mailto(tmp_path, distruggi):
    contesto, _ = apri_contesto(tmp_path / "dati")
    contesto.impostazioni = replace(contesto.impostazioni, posta="mailto")
    finestra = FinestraPrincipale(contesto)
    distruggi(finestra)
    assert not finestra.nuova_pratica.mail.importa.isEnabled()
    contesto.chiudi()
