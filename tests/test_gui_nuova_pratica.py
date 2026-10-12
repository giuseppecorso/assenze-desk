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
    qtbot.keyClick(campo.editor, Qt.Key.Key_Return)
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


def test_risposta_con_il_cliente_in_copia_e_dalla_sua_casella(finestra):
    pagina = finestra.nuova_pratica
    pagina.mail.importa.click()
    malattia = pagina.malattia
    assert malattia.risposta_a.indice() == 0  # mail del lavoratore
    dipendente = malattia.scelta["dipendente"].valore
    malattia.bozza_lavoratore.click()
    bozza = finestra.contesto.posta.bozze[-1]
    assert bozza.cc == (dipendente.copia_cliente,)
    assert bozza.mittente == ""
    assert "In copia il cliente" in finestra.messaggi.testo.text()

    contesto = finestra.contesto
    contesto.impostazioni = replace(
        contesto.impostazioni,
        risposte=replace(contesto.impostazioni.risposte, dalla_lista_cliente=True),
    )
    malattia.bozza_lavoratore.click()
    assert contesto.posta.bozze[-1].mittente == dipendente.copia_cliente


def test_mail_girata_da_un_collega(finestra):
    pagina = finestra.nuova_pratica
    pagina.mail.imposta_testo(
        "Da: Collega <collega@azienda.example>\nData: 07/10/2026 09:12\n\n"
        "Ti giro il certificato protocollo 412345678 dal 5 al 9 ottobre."
    )
    pagina.analizza()
    malattia = pagina.malattia
    assert malattia.risposta_a.indice() == 1  # mittente interno: si propone il collega
    assert malattia.bozza_lavoratore.text() == "Bozza al collega"
    malattia.bozza_lavoratore.click()
    bozza = finestra.contesto.posta.bozze[-1]
    assert bozza.a == ("collega@azienda.example",)
    assert bozza.cc == ()
    assert "prendo in carico" in bozza.corpo_html
    malattia.risposta_a.pulsante(0).click()  # l'utente può sempre cambiare
    assert malattia.bozza_lavoratore.text() == "Bozza al lavoratore"


def test_nessuna_risposta(finestra):
    pagina = finestra.nuova_pratica
    pagina.mail.importa.click()
    assert pagina.stato.text() == "Da inviare"
    pagina.malattia.nessuna_risposta.click()
    assert pagina.stato.text() != "Da inviare"
    assert finestra.contesto.archivio.storico()[0].azione == "Risposta non necessaria"
    assert finestra.contesto.posta.bozze == []  # nessuna bozza aperta


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


def test_protocollo_scritto_a_mano(finestra, qtbot):
    malattia = finestra.nuova_pratica.malattia
    editor = malattia.campi["protocollo"].editor
    editor.setFocus()
    qtbot.keyClicks(editor, "452 616 891")
    assert editor.text() == "452 616 891"  # mentre scrivi non cambia niente
    editor.setCursorPosition(3)
    qtbot.keyClicks(editor, "-")  # si può correggere anche nel mezzo
    assert editor.text() == "452- 616 891"
    qtbot.keyClick(editor, Qt.Key.Key_Return)
    assert editor.text() == "452616891"
    assert malattia.modulo["protocollo"].valore == "452616891"
    assert QApplication.clipboard().text() == "452616891"
    assert "copiato" in finestra.messaggi.testo.text()

    cf = malattia.campi["cf"].editor
    cf.setFocus()
    qtbot.keyClicks(cf, "rssmra80a01 z999x")
    qtbot.keyClick(cf, Qt.Key.Key_Return)
    assert cf.text() == "RSSMRA80A01Z999X"


# --- Mail da un indirizzo diverso e modifica dei dati ---


def mail_da_casa(dipendente, con_cf):
    riga_cf = f"Codice fiscale {dipendente.cf}\n" if con_cf else ""
    return (
        "OGG: Certificato\nDa: Qualcuno <casa.privata@example.org>\nData: 07/10/2026 09:12\n\n"
        f"Buongiorno,\n{riga_cf}protocollo 412345678 dal 5 al 9 ottobre."
    )


def test_mail_da_un_indirizzo_nuovo_viene_ricordata(finestra):
    pagina = finestra.nuova_pratica
    dipendente = finestra.contesto.anagrafica.dipendenti[3]
    pagina.mail.imposta_testo(mail_da_casa(dipendente, con_cf=True))
    pagina.analizza()
    malattia = pagina.malattia
    assert malattia.scelta["dipendente"].valore.cf == dipendente.cf  # trovato dal CF
    malattia.salva.click()
    assert "anche da casa.privata@example.org" in finestra.messaggi.testo.text()

    pagina.nuova_vuota()
    pagina.mail.imposta_testo(mail_da_casa(dipendente, con_cf=False))
    pagina.analizza()
    assert malattia.scelta["dipendente"].valore.cf == dipendente.cf  # ora dal mittente
    assert "mittente" in malattia.dipendente.origine.text()


def test_modifica_dati_dal_riquadro_dipendente(finestra, monkeypatch):
    from assenze_desk.gui import modifica_dipendente

    def compila(dialogo):
        dialogo.caselle["email"].setText("nuova@example.org")
        dialogo.caselle["altre_email"].setText("casa@example.org")
        dialogo.caselle["cliente"].setText("Cliente Corretto")
        dialogo.salva.click()

    monkeypatch.setattr(modifica_dipendente, "mostra_finestra", compila)
    pagina = finestra.nuova_pratica
    malattia = pagina.malattia
    assert malattia.dipendente.modifica.isHidden()  # nessun dipendente: niente da modificare
    larghezza = malattia.minimumSizeHint().width()
    pagina.mail.importa.click()
    assert not malattia.dipendente.modifica.isHidden()
    assert malattia.minimumSizeHint().width() == larghezza  # la colonna non si allarga
    origine = malattia.scelta["dipendente"].origine

    malattia.dipendente.modifica.click()
    scelto = malattia.scelta["dipendente"]
    assert scelto.valore.cliente == "Cliente Corretto"
    assert scelto.origine == origine  # resta automatico
    assert "Cliente Corretto" in malattia.dipendente.dettagli.text()
    assert "l'Excel non cambia" in finestra.messaggi.testo.text()
    assert finestra.contesto.archivio.email_di(scelto.valore.cf) == ["casa@example.org"]

    def ripristina(dialogo):
        assert dialogo.ripristina.isVisible() or not dialogo.ripristina.isHidden()
        dialogo.ripristina.click()

    monkeypatch.setattr(modifica_dipendente, "mostra_finestra", ripristina)
    malattia.dipendente.modifica.click()
    assert malattia.scelta["dipendente"].valore.cliente != "Cliente Corretto"


def test_modifica_dati_con_errori_e_annulla(finestra, monkeypatch):
    from assenze_desk.gui import modifica_dipendente

    def sbaglia(dialogo):
        dialogo.caselle["inizio_joborder"].setText("31/02/2026")
        dialogo.salva.click()
        assert "Data non valida" in dialogo.errore.text()
        dialogo.caselle["inizio_joborder"].setText("")
        dialogo.caselle["email"].setText("senza-chiocciola")
        dialogo.salva.click()
        assert "@" in dialogo.errore.text()
        dialogo.caselle["cognome"].setText("")
        dialogo.salva.click()
        assert "cognome" in dialogo.errore.text()
        dialogo.annulla.click()

    monkeypatch.setattr(modifica_dipendente, "mostra_finestra", sbaglia)
    finestra.nuova_pratica.mail.importa.click()
    malattia = finestra.nuova_pratica.malattia
    prima = malattia.scelta["dipendente"].valore
    malattia.dipendente.modifica.click()
    assert malattia.scelta["dipendente"].valore == prima
    assert finestra.contesto.archivio.correzioni() == {}


def test_modifica_di_un_dipendente_inserito_a_mano(finestra, qtbot):
    from assenze_desk.core.dipendenti import Dipendente as D

    malattia = finestra.nuova_pratica.malattia
    malattia._dipendente_scelto(D("ZZZZZZ80A01Z999Z", "Nuovo", "Dipendente"))
    malattia.dipendente.modifica.click()
    assert "solo i dipendenti dell'anagrafica" in finestra.messaggi.testo.text()


def test_giustificativo_ricorda_il_mittente_e_si_modifica(finestra, qtbot, monkeypatch):
    from assenze_desk.gui import modifica_dipendente

    pagina = finestra.nuova_pratica
    pagina.segmenti.pulsante(1).click()
    giustificativo = pagina.giustificativo
    tutti = finestra.contesto.anagrafica.dipendenti
    nomi = [(d.nome, d.cognome) for d in tutti]
    dipendente = next(d for d in tutti if nomi.count((d.nome, d.cognome)) == 1)  # senza omonimi
    pagina.mail.imposta_testo(
        f"OGG: Ferie\nDa: <altro.indirizzo@example.org>\nData: 02/10/2026 16:40\n\n"
        f"Sono {dipendente.nome} {dipendente.cognome}, chiedo le ferie il 12 ottobre"
    )
    pagina.analizza()
    assert giustificativo.scelta["dipendente"].valore.cf == dipendente.cf
    giustificativo.salva.click()
    assert "anche da altro.indirizzo@example.org" in finestra.messaggi.testo.text()

    monkeypatch.setattr(
        modifica_dipendente,
        "mostra_finestra",
        lambda d: (d.caselle["nome"].setText("Nome Nuovo"), d.salva.click()),
    )
    giustificativo.dipendente.modifica.click()
    assert giustificativo.scelta["dipendente"].valore.nome == "Nome Nuovo"
