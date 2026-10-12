"""Design system e componenti dell'interfaccia (issue #5 e #19)."""

import re
from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from assenze_desk.core.campi import Modulo, Origine, Proposta
from assenze_desk.gui import icone, tema
from assenze_desk.gui.componenti import BarraMessaggi, CampoDato, Interruttore, Segmenti


@pytest.fixture
def app(qapp):
    tema.applica_tema(qapp, "chiaro")
    return qapp


# --- Tema ---


def test_i_due_temi_hanno_gli_stessi_colori():
    assert tema.CHIARO.keys() == tema.SCURO.keys()
    for colori in tema.TEMI.values():
        assert all(re.fullmatch(r"#[0-9a-f]{6}", valore) for valore in colori.values())


def test_il_foglio_di_stile_usa_tutti_i_colori_del_tema():
    # Problema 12: nessun tema o colore definito e mai usato
    for nome, colori in tema.TEMI.items():
        qss = tema.foglio_di_stile(colori)
        assert "$" not in qss, nome
        usati = {chiave for chiave, valore in colori.items() if valore in qss}
        assert usati == set(colori), f"{nome}: colori mai usati {set(colori) - usati}"


def test_tema_di_sistema():
    assert tema.tema_effettivo("sistema", sistema_scuro=True) == "scuro"
    assert tema.tema_effettivo("sistema", sistema_scuro=False) == "chiaro"
    assert tema.tema_effettivo("scuro", sistema_scuro=False) == "scuro"
    assert tema.tema_effettivo("inventato", sistema_scuro=True) == "chiaro"


def test_applica_il_tema(app):
    assert tema.applica_tema(app, "scuro") == "scuro"
    assert tema.colore("sfondo") == tema.SCURO["sfondo"]
    assert tema.SCURO["sfondo"] in app.styleSheet()
    tema.applica_tema(app, "chiaro")
    assert tema.colore("sfondo") == tema.CHIARO["sfondo"]


def test_icone(app):
    for nome in icone.TRATTI:
        assert not icone.icona(nome).isNull()
    assert not icone.pixmap("mail", "#000000").isNull()


def test_icona_dell_app_e_file_ico(app, tmp_path):
    assert not icone.icona_app().isNull()
    assert icone.pixmap_app(26).deviceIndependentSize().width() == 26
    file = icone.scrivi_ico(tmp_path / "app.ico")
    dati = file.read_bytes()
    assert dati[:4] == b"\x00\x00\x01\x00"  # intestazione ICO
    numero = int.from_bytes(dati[4:6], "little")
    assert numero == len(icone.LATI_ICO)
    for indice in range(numero):
        voce = dati[6 + 16 * indice : 6 + 16 * (indice + 1)]
        dimensione = int.from_bytes(voce[8:12], "little")
        inizio = int.from_bytes(voce[12:16], "little")
        assert dati[inizio : inizio + 8] == b"\x89PNG\r\n\x1a\n"
        assert inizio + dimensione <= len(dati)


# --- Componenti ---


def test_segmenti(app, qtbot):
    segmenti = Segmenti(["Malattia", "Giustificativo"])
    qtbot.addWidget(segmenti)
    with qtbot.waitSignal(segmenti.cambiato) as segnale:
        segmenti.pulsante(1).click()
    assert segnale.args == [1]
    assert segmenti.indice() == 1
    segmenti.seleziona(0)
    assert segmenti.indice() == 0


def test_interruttore(app, qtbot):
    interruttore = Interruttore("Conta anche sabato e domenica")
    qtbot.addWidget(interruttore)
    interruttore.show()
    assert not interruttore.isChecked()
    interruttore.click()
    assert interruttore.isChecked()
    assert interruttore.sizeHint().width() > interruttore.LARGHEZZA
    interruttore.grab()  # si disegna senza errori


def test_barra_dei_messaggi(app, qtbot):
    barra = BarraMessaggi()
    qtbot.addWidget(barra)
    eseguite = []
    barra.mostra("Pratica salvata", "ok", ("Apri", lambda: eseguite.append(1)))
    assert barra.isVisibleTo(barra.parentWidget() or barra)
    barra._azione.click()
    assert eseguite == [1]
    barra.mostra("Errore", "errore")
    assert not barra._timer.isActive()  # gli errori restano finché non si chiudono


def test_campo_mostra_origine_avviso_e_ripristino(app, qtbot):
    modulo = Modulo(["fine"])
    campo = CampoDato("fine", "Al", "data")
    qtbot.addWidget(campo)
    modulo.proponi({"fine": Proposta(date(2026, 10, 9), Origine.PDF)})
    campo.mostra(modulo["fine"])
    assert campo.editor.text() == "09/10/2026"
    assert campo.origine.text() == "PDF"

    with qtbot.assertNotEmitted(campo.modificato):
        qtbot.keyClicks(campo.editor, "x")  # le date valgono con Invio o uscendo
    with qtbot.waitSignal(campo.modificato) as segnale:
        qtbot.keyClick(campo.editor, Qt.Key.Key_Return)  # testo non valido
    assert segnale.args == ["fine", None]
    modulo.scrivi("fine", None)
    campo.mostra(modulo["fine"])
    assert "Data non valida" in campo.avviso.text()
    assert campo.editor.property("incerto")

    campo.editor.clear()
    qtbot.keyClicks(campo.editor, "10/10/2026")
    qtbot.keyClick(campo.editor, Qt.Key.Key_Return)
    modulo.scrivi("fine", date(2026, 10, 10))
    campo.mostra(modulo["fine"])
    assert campo.origine.text() == "Manuale"
    assert campo.automatico.text() == "Automatico: 09/10/2026"
    assert not campo.avviso.isVisibleTo(campo)
    with qtbot.waitSignal(campo.ripristino):
        campo.bottone_ripristina.click()


def test_campo_scelta_con_scelte_rapide(app, qtbot):
    modulo = Modulo(["tipo"])
    campo = CampoDato("tipo", "Tipo", "scelta", scelte=["Ferie", "ROL"])
    qtbot.addWidget(campo)
    modulo.proponi({"tipo": Proposta(avviso="Più tipi: scegli.", scelte=("Ferie", "ROL"))})
    campo.mostra(modulo["tipo"])
    assert campo.editor.currentData() is None
    assert campo.avviso.text() == "Più tipi: scegli."
    rapide = [campo.rapide.itemAt(i).widget() for i in range(campo.rapide.count())]
    bottone_rol = next(w for w in rapide if w and w.text() == "ROL")
    with qtbot.waitSignal(campo.modificato) as segnale:
        bottone_rol.click()
    assert segnale.args == ["tipo", "ROL"]
    modulo.scrivi("tipo", "ROL")
    campo.mostra(modulo["tipo"])
    assert campo.editor.currentData() == "ROL"


@pytest.mark.parametrize(
    ("tipo", "testo", "valore"),
    [
        ("ore", "1:30", 90),
        ("giorni", "12/10, 13/10/2026", (date(2026, 10, 12), date(2026, 10, 13))),
        ("testo", "  412345678 ", "412345678"),
    ],
)
def test_conversioni_dei_campi(app, qtbot, tipo, testo, valore):
    campo = CampoDato("x", "X", tipo, riferimento=lambda: date(2026, 10, 7))
    qtbot.addWidget(campo)
    assert campo.valore_da_testo(testo) == valore
    assert campo.valore_da_testo(campo.testo_da_valore(valore)) == valore


def test_qapp_unica(app):
    assert QApplication.instance() is app


def test_campo_di_testo_pulito_alla_fine_della_scrittura(app, qtbot):
    campo = CampoDato("protocollo", "Protocollo", al_termine=lambda t: t.replace(" ", ""))
    qtbot.addWidget(campo)
    valori, finiti = [], []
    campo.modificato.connect(lambda _nome, valore: valori.append(valore))
    campo.scritto_a_mano.connect(lambda nome, valore: finiti.append((nome, valore)))
    editor = campo.editor
    editor.setFocus()
    qtbot.keyClicks(editor, "452 616")
    assert editor.text() == "452 616"  # mentre si scrive non cambia niente
    assert valori[-1] == "452 616"
    editor.editingFinished.emit()  # Invio o uscita dalla casella
    assert editor.text() == "452616"
    assert valori[-1] == "452616"
    assert finiti == [("protocollo", "452616")]
    editor.editingFinished.emit()  # uscire di nuovo senza scrivere: niente di nuovo
    assert finiti == [("protocollo", "452616")]
