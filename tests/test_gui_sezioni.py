"""Smoke test di Archivio, Statistiche e Impostazioni in demo (issue #5)."""

from dataclasses import replace
from datetime import date, datetime

import pytest
from openpyxl import Workbook
from PySide6.QtCore import QItemSelectionModel, Qt

from assenze_desk.core.stato import Stato
from assenze_desk.gui.archivio import Archivio
from assenze_desk.gui.componenti import BarraMessaggi
from assenze_desk.gui.finestra import FinestraPrincipale
from assenze_desk.gui.statistiche import filtra_periodo
from assenze_desk.servizi import apri_contesto

OGGI = date(2026, 10, 7)


class Orologio:
    def __call__(self):
        return datetime(2026, 10, 7, 9, 0)


@pytest.fixture
def finestra(qapp, tmp_path, distruggi):
    contesto, avvisi = apri_contesto(
        tmp_path / "dati", demo=True, oggi=OGGI, adesso=Orologio(), apri_url=lambda _url: None
    )
    finestra = FinestraPrincipale(contesto, avvisi)
    distruggi(finestra)
    finestra.show()
    yield finestra
    contesto.chiudi()


def seleziona(tabella, *righe):
    """Come un clic con Ctrl: le righe si aggiungono alla selezione."""
    tabella.clearSelection()
    modello = tabella.selectionModel()
    for riga in righe:
        modello.select(
            tabella.model().index(riga, 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )


# --- Archivio ---


def test_archivio_mostra_e_filtra_le_pratiche(finestra):
    finestra.voci[1].click()
    archivio = finestra.archivio
    tutte = archivio.pratiche.rowCount()
    assert tutte == len(finestra.contesto.archivio.pratiche())
    archivio.stato.setCurrentIndex(archivio.stato.findData(Stato.INCOMPLETA))
    assert 0 < archivio.pratiche.rowCount() < tutte
    archivio.stato.setCurrentIndex(0)
    protocollo = archivio.pratiche.item(0, 0).text()
    archivio.cerca.setText(protocollo)
    assert archivio.pratiche.rowCount() == 1
    archivio.cerca.setText("")
    archivio.dal.setText("01/01/2030")
    assert archivio.pratiche.rowCount() == 0


def test_riaprire_una_pratica_dall_archivio(finestra):
    finestra.voci[1].click()
    archivio = finestra.archivio
    seleziona(archivio.pratiche, 0)
    pratica = archivio.pratiche.item(0, 0).data(Qt.ItemDataRole.UserRole)
    archivio.apri.click()
    assert finestra.sezioni.currentIndex() == 0  # cambio di sezione chiesto dall'utente
    malattia = finestra.nuova_pratica.malattia
    assert malattia.modulo["protocollo"].valore == pratica.protocollo
    assert malattia.campi["protocollo"].origine.text() == "Archivio"


def test_apri_senza_selezione(finestra):
    finestra.voci[1].click()
    finestra.archivio.pratiche.clearSelection()
    finestra.archivio.apri.click()
    assert "Seleziona" in finestra.messaggi.testo.text()


def test_cambiare_lo_stato_a_mano_e_storico(finestra):
    finestra.voci[1].click()
    archivio = finestra.archivio
    seleziona(archivio.pratiche, 0)
    protocollo = archivio.pratiche.item(0, 0).text()
    archivio.cambia_stato.activated.emit(archivio.cambia_stato.findData(Stato.CHIUSA))
    assert finestra.contesto.archivio.pratica(protocollo).stato_manuale is Stato.CHIUSA
    archivio.cerca.setText(protocollo)
    assert archivio.pratiche.item(0, 6).text() == "Chiusa · a mano"
    archivio.mostra_storico.click()
    assert archivio.storico.isVisible()
    assert archivio.storico.item(0, 1).text() == "Stato cambiato a mano"
    seleziona(archivio.pratiche, 0)
    archivio.cambia_stato.activated.emit(archivio.cambia_stato.findText("Stato automatico"))
    assert finestra.contesto.archivio.pratica(protocollo).stato_manuale is None


def test_eliminare_pratiche_con_conferma(qapp, tmp_path, distruggi):
    contesto, _ = apri_contesto(
        tmp_path / "dati", demo=True, oggi=OGGI, adesso=Orologio(), apri_url=lambda _url: None
    )
    risposte = {"conferma": False}
    messaggi = BarraMessaggi()
    distruggi(messaggi)
    archivio = Archivio(contesto, messaggi, conferma=lambda _domanda: risposte["conferma"])
    distruggi(archivio)
    totale = archivio.pratiche.rowCount()

    archivio.elimina_pratiche.click()  # niente selezionato
    assert "Seleziona" in messaggi.testo.text()
    seleziona(archivio.pratiche, 0, 1)
    archivio.elimina_pratiche.click()  # l'utente risponde no
    assert archivio.pratiche.rowCount() == totale
    risposte["conferma"] = True
    seleziona(archivio.pratiche, 0, 1)
    archivio.elimina_pratiche.click()
    assert archivio.pratiche.rowCount() == totale - 2
    assert len(contesto.archivio.pratiche()) == totale - 2
    assert contesto.archivio.storico()[0].azione == "Pratica eliminata"
    contesto.chiudi()


def test_esporta_le_pratiche_filtrate(finestra):
    finestra.voci[1].click()
    finestra.archivio.esporta.click()
    file = list(finestra.contesto.impostazioni.percorsi.export.glob("pratiche_*.xlsx"))
    assert len(file) == 1
    assert "Esportate" in finestra.messaggi.testo.text()


def test_giustificativi_correggere_eliminare_esportare(qapp, tmp_path, distruggi):
    contesto, _ = apri_contesto(
        tmp_path / "dati", demo=True, oggi=OGGI, adesso=Orologio(), apri_url=lambda _url: None
    )
    risposte = {"conferma": False}
    messaggi = BarraMessaggi()
    distruggi(messaggi)
    archivio = Archivio(
        contesto,
        messaggi,
        conferma=lambda _domanda: risposte["conferma"],
        chiedi_ore=lambda _attuali: "3:30",
    )
    distruggi(archivio)
    archivio.tipo.pulsante(1).click()
    totale = archivio.righe.rowCount()
    assert totale == len(contesto.archivio.righe())
    archivio.da_esportare.setChecked(True)
    da_esportare = archivio.righe.rowCount()
    assert 0 < da_esportare < totale

    seleziona(archivio.righe, 0)
    archivio.modifica_ore.click()
    assert archivio.righe.item(0, 5).text() == "3:30"

    seleziona(archivio.righe, 0)
    archivio.elimina.click()  # l'utente risponde no
    assert archivio.righe.rowCount() == da_esportare
    risposte["conferma"] = True
    archivio.elimina.click()
    assert archivio.righe.rowCount() == da_esportare - 1

    archivio.esporta.click()
    assert archivio.righe.rowCount() == 0  # esportate: non sono più "da esportare"
    contesto.chiudi()


def test_importa_dalla_versione_precedente(qapp, tmp_path, distruggi):
    contesto, _ = apri_contesto(
        tmp_path / "dati", demo=True, oggi=OGGI, adesso=Orologio(), apri_url=lambda _url: None
    )
    libro = Workbook()
    libro.active.append(["Protocollo", "CF", "DataInizio", "DataFine", "MailLav"])
    libro.active.append(["499999991", "FNTPRV80A01Z999Y", "01/10/2026", "03/10/2026", "SI"])
    libro.active.append([None, "FNTPRV80A01Z999Y", "01/10/2026", None, None])
    tracking = tmp_path / "tracking.xlsx"
    libro.save(tracking)
    altro = tmp_path / "altro.xlsx"
    Workbook().save(altro)

    scelti: list = []
    messaggi = BarraMessaggi()
    distruggi(messaggi)
    archivio = Archivio(contesto, messaggi, scegli_file=lambda: scelti)
    distruggi(archivio)
    prima = archivio.pratiche.rowCount()

    archivio.importa.click()  # nessun file scelto: non succede niente
    assert archivio.pratiche.rowCount() == prima

    scelti[:] = [tracking]
    archivio.importa.click()
    assert archivio.pratiche.rowCount() == prima + 1
    assert "1 pratiche nuove" in messaggi.testo.text()
    assert "1 righe non importate" in messaggi.testo.text()

    scelti[:] = [altro]
    archivio.importa.click()
    assert "non sembra un file della versione precedente" in messaggi.testo.text()
    contesto.chiudi()


# --- Statistiche ---


def test_statistiche_mostrano_i_numeri_della_demo(finestra):
    finestra.voci[2].click()
    statistiche = finestra.statistiche
    statistiche.periodo.setCurrentText("Tutto")
    assert statistiche.numeri["pratiche"].text() == str(len(finestra.contesto.archivio.pratiche()))
    assert statistiche.numeri["tempo"].text().endswith("min")
    assert statistiche.mesi.valori
    assert [voce[0] for voce in statistiche.stati.voci] == [str(s) for s in Stato]
    assert statistiche.clienti.rowCount() > 0
    statistiche.grab()  # i grafici si disegnano senza errori


def test_periodi_delle_statistiche(finestra):
    pratiche = finestra.contesto.pratiche_statistiche()
    assert len(filtra_periodo(pratiche, "Tutto", OGGI)) == len(pratiche)
    recenti = filtra_periodo(pratiche, "Ultimi 3 mesi", OGGI)
    assert all(p.inizio and p.inizio >= date(2026, 7, 8) for p in recenti)
    assert filtra_periodo(pratiche, "Anno in corso", date(2030, 1, 1)) == []


# --- Impostazioni ---


def test_impostazioni_si_salvano_e_si_applicano(finestra):
    finestra.voci[3].click()
    sezione = finestra.impostazioni
    regole = sezione.pagine[3]
    regole.soglia.setValue(5)
    mail = sezione.pagine[2]
    mail.destinatari.setText("personale@example.com; copia@example.com")
    mail.dalla_lista_cliente.setChecked(True)
    mail.mittente_collega.setText(" io@example.com ")
    mail.corpo_collega.setPlainText("Ciao, grazie!")
    sezione.salva.click()
    imp = finestra.contesto.impostazioni
    assert imp.risposte.dalla_lista_cliente
    assert imp.risposte.mittente_collega == "io@example.com"
    assert imp.template.corpo_collega == "Ciao, grazie!"
    assert imp.soglia_ufficio == 5
    assert imp.ufficio.destinatari == ("personale@example.com", "copia@example.com")
    assert finestra.contesto.archivio.soglia_ufficio == 5
    assert "salvate" in finestra.messaggi.testo.text()


def test_portale_aziendale_dalle_impostazioni(finestra):
    malattia = finestra.nuova_pratica.malattia
    giustificativo = finestra.nuova_pratica.giustificativo
    assert malattia.portale_aziendale.isHidden()  # senza indirizzo nessun pulsante
    assert giustificativo.portale_aziendale.isHidden()

    sezione = finestra.impostazioni
    pagina = sezione.pagine[6]
    pagina.nome_portale.setText("Intranet")
    pagina.indirizzo_portale.setText("intranet.example")  # manca https://
    sezione.salva.click()
    assert finestra.messaggi.property("avviso") == "errore"
    assert "portale aziendale" in finestra.messaggi.testo.text()

    pagina.indirizzo_portale.setText(" https://intranet.example/app ")
    sezione.salva.click()
    portale = finestra.contesto.impostazioni.portale_aziendale
    assert (portale.nome, portale.indirizzo) == ("Intranet", "https://intranet.example/app")
    for schermata in (malattia, giustificativo):
        assert not schermata.portale_aziendale.isHidden()
        assert schermata.portale_aziendale.text() == "Intranet"

    aperti = []
    finestra.contesto.apri_url = aperti.append
    malattia.portale_aziendale.click()
    giustificativo.portale_aziendale.click()
    assert aperti == ["https://intranet.example/app"] * 2


def test_impostazioni_non_valide_mostrano_dove_correggere(finestra):
    sezione = finestra.impostazioni
    sezione.pagine[3].regole["protocollo"][1].setText("A1")  # prefisso non numerico
    sezione.salva.click()
    assert "protocollo" in finestra.messaggi.testo.text()
    assert finestra.messaggi.property("avviso") == "errore"
    sezione.annulla.click()
    assert sezione.pagine[3].regole["protocollo"][1].text() == "4"


def test_tipi_di_giustificativo_modificabili(finestra):
    sezione = finestra.impostazioni
    tipi = sezione.pagine[4]
    tipi.aggiungi.click()
    riga = tipi.tabella.rowCount() - 1
    tipi.tabella.item(riga, 0).setText("Lavoro agile")
    tipi.tabella.item(riga, 1).setText("SW")
    tipi.tabella.item(riga, 2).setText("smart working, lavoro agile")
    sezione.salva.click()
    nomi = [t.nome for t in finestra.contesto.impostazioni.tipi]
    assert nomi[-1] == "Lavoro agile"
    scelte = finestra.nuova_pratica.giustificativo.campi["tipo"].editor
    assert scelte.findData("Lavoro agile") > 0  # già disponibile in Nuova pratica

    tipi.tabella.selectRow(riga)
    tipi.rimuovi.click()
    tipi.tabella.item(0, 1).setText("")
    sezione.salva.click()
    assert "riga 1" in finestra.messaggi.testo.text()


def test_vocabolario_e_ocr(finestra):
    sezione = finestra.impostazioni
    sezione.pagine[5].aggiunte["unita_ore"].setText("hr")
    ocr = sezione.pagine[6]
    ocr.rumore.setText("Portale Interno Demo")
    ocr.spunte.setCurrentIndex(1)
    sezione.salva.click()
    imp = finestra.contesto.impostazioni
    assert imp.vocabolario.unita_ore[-1] == "hr"
    assert imp.ocr.parole_rumore == ("Portale Interno Demo",)
    assert imp.spunte_prima_della_voce is True
    ocr.tesseract.setText(str(finestra.contesto.file_impostazioni))  # un file che esiste
    ocr.verifica.click()
    assert ocr.esito.text().startswith("Trovato")


def test_portale_non_valido(finestra):
    sezione = finestra.impostazioni
    sezione.pagine[6].portale.setText("portale.example")
    sezione.salva.click()
    assert "https://" in finestra.messaggi.testo.text()


def test_anagrafica_ricaricata(finestra):
    pagina = finestra.impostazioni.anagrafica
    assert "24 dipendenti" in pagina.riepilogo.text()
    finestra.contesto.impostazioni.percorsi.anagrafica.unlink()
    pagina.ricarica.click()
    assert "0 dipendenti" in pagina.riepilogo.text()
    assert pagina.avvisi.text()


def test_percorso_vuoto(finestra):
    sezione = finestra.impostazioni
    sezione.generali.percorsi["export"].setText("  ")
    sezione.salva.click()
    assert "Export" in finestra.messaggi.testo.text()


def test_tema_dalla_barra_laterale_aggiorna_le_impostazioni(finestra):
    finestra.tema.pulsante(1).click()
    assert finestra.impostazioni.generali.tema.currentData() == "chiaro"


def test_mailto_dalle_impostazioni_disattiva_l_import(finestra):
    finestra.contesto.demo = False
    generali = finestra.impostazioni.generali
    generali.posta.setCurrentIndex(generali.posta.findData("mailto"))
    finestra.impostazioni.salva.click()
    assert not finestra.nuova_pratica.mail.importa.isEnabled()
    finestra.contesto.impostazioni = replace(finestra.contesto.impostazioni, posta="outlook")
