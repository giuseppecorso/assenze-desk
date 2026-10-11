"""Mini calendario e avvisi sulle date (richieste dopo la prova in demo).

Le date si scelgono dal calendario, che parte dalla data già scritta o da oggi.
Una data valida ma poco plausibile (fine prima dell'inizio, anno sbagliato)
mostra un avviso nel campo; un elenco di giorni con una parte sbagliata non
perde quella parte in silenzio.
"""

from datetime import date, datetime

import pytest
from PySide6.QtCore import QDate, Qt

from assenze_desk.core.date_utente import (
    AVVISO_FINE_PRIMA,
    AVVISO_GIORNI_LONTANI,
    AVVISO_LONTANA,
)
from assenze_desk.gui import icone, tema
from assenze_desk.gui.calendario import Calendario
from assenze_desk.gui.componenti import CampoDato
from assenze_desk.gui.finestra import FinestraPrincipale
from assenze_desk.servizi import apri_contesto

OGGI = date(2026, 10, 7)


@pytest.fixture
def app(qapp):
    tema.applica_tema(qapp, "chiaro")
    return qapp


@pytest.fixture
def finestra(app, tmp_path, distruggi):
    contesto, avvisi = apri_contesto(
        tmp_path / "dati",
        demo=True,
        oggi=OGGI,
        adesso=lambda: datetime(2026, 10, 7, 9, 0),
        apri_url=lambda _url: None,
    )
    finestra = FinestraPrincipale(contesto, avvisi)
    distruggi(finestra)
    finestra.show()
    yield finestra
    contesto.chiudi()


def apri_calendario(casella) -> Calendario:
    azione = next(a for a in casella.actions() if a.property("icona") == "calendario")
    azione.trigger()
    calendario = casella.findChild(Calendario)
    assert calendario is not None and calendario.isVisible()
    return calendario


def scrivi_data(qtbot, campo: CampoDato, testo: str) -> None:
    campo.editor.clear()
    qtbot.keyClicks(campo.editor, testo)
    qtbot.keyClick(campo.editor, Qt.Key.Key_Return)


# --- Il calendario nel campo ---


def test_il_calendario_parte_da_oggi_e_un_clic_sceglie(app, qtbot):
    campo = CampoDato("fine", "Al", "data", oggi=lambda: OGGI)
    qtbot.addWidget(campo)
    calendario = apri_calendario(campo.editor)
    assert calendario.mese.selectedDate().toPython() == OGGI
    assert calendario.mese.firstDayOfWeek() == Qt.DayOfWeek.Monday
    calendario.grab()  # si disegna, con oggi cerchiato
    with qtbot.waitSignal(campo.modificato) as segnale:
        calendario.mese.clicked.emit(QDate(2026, 10, 12))
    assert segnale.args == ["fine", date(2026, 10, 12)]
    assert campo.editor.text() == "12/10/2026"
    assert not calendario.isVisible()


def test_il_calendario_parte_dalla_data_scritta_ed_esc_chiude(app, qtbot):
    campo = CampoDato("fine", "Al", "data", oggi=lambda: OGGI)
    qtbot.addWidget(campo)
    campo.editor.setText("05/01/2026")
    calendario = apri_calendario(campo.editor)
    assert calendario.mese.selectedDate().toPython() == date(2026, 1, 5)
    with qtbot.assertNotEmitted(campo.modificato):
        qtbot.keyClick(calendario, Qt.Key.Key_Escape)
    assert not calendario.isVisible()


def test_piu_giorni_dal_calendario(app, qtbot):
    campo = CampoDato("giorni", "Giorni", "giorni", riferimento=lambda: OGGI, oggi=lambda: OGGI)
    qtbot.addWidget(campo)
    calendario = apri_calendario(campo.editor)
    calendario.mese.clicked.emit(QDate(2026, 10, 9))
    calendario.scegli(date(2026, 10, 14), intervallo=True)  # i feriali fino a mercoledì
    with qtbot.waitSignal(campo.modificato) as segnale:
        calendario.scegli(date(2026, 10, 13))  # secondo clic: tolto
    assert segnale.args == ["giorni", (date(2026, 10, 9), date(2026, 10, 12), date(2026, 10, 14))]
    assert campo.editor.text() == "09/10/2026, 12/10/2026, 14/10/2026"
    assert calendario.isVisible()  # resta aperto per scegliere altri giorni
    calendario.grab()  # i giorni scelti si disegnano pieni
    calendario.fatto.click()
    assert not calendario.isVisible()


def test_giorni_con_una_parte_sbagliata(app, qtbot):
    campo = CampoDato("giorni", "Giorni", "giorni", riferimento=lambda: OGGI)
    qtbot.addWidget(campo)
    with qtbot.waitSignal(campo.modificato) as segnale:
        scrivi_data(qtbot, campo, "12/10/2026, 40/10/2026")
    assert segnale.args == ["giorni", None]


def test_data_senza_anno_vicina_a_oggi(app, qtbot):
    campo = CampoDato("fine", "Al", "data", riferimento=lambda: OGGI)
    qtbot.addWidget(campo)
    assert campo.valore_da_testo("12/10") == date(2026, 10, 12)


def test_le_icone_nelle_caselle_cambiano_con_il_tema(app, qtbot):
    campo = CampoDato("fine", "Al", "data")
    qtbot.addWidget(campo)
    azione = next(a for a in campo.editor.actions() if a.property("icona"))
    prima = azione.icon().pixmap(16, 16).toImage()
    tema.applica_tema(app, "scuro")
    icone.ricolora(campo)
    assert azione.icon().pixmap(16, 16).toImage() != prima
    tema.applica_tema(app, "chiaro")


# --- Avvisi nelle schermate ---


def test_una_data_impossibile_si_segnala_e_sparisce_con_la_pratica_vuota(finestra, qtbot):
    pagina = finestra.nuova_pratica
    fine = pagina.malattia.campi["fine"]
    scrivi_data(qtbot, fine, "110/10/2026")
    assert "Data non valida" in fine.avviso.text()
    assert fine.editor.property("incerto")
    pagina.nuova_vuota()
    assert fine.editor.text() == ""
    assert not fine.avviso.isVisibleTo(fine)


def test_malattia_avvisa_della_fine_prima_dell_inizio_e_dell_anno(finestra, qtbot):
    malattia = finestra.nuova_pratica.malattia
    inizio, fine = malattia.campi["inizio"], malattia.campi["fine"]
    scrivi_data(qtbot, inizio, "09/10/2026")
    scrivi_data(qtbot, fine, "05/10/2026")
    assert fine.avviso.text() == AVVISO_FINE_PRIMA
    assert fine.editor.property("incerto")
    assert "correggi le date" in malattia.episodio.text()

    scrivi_data(qtbot, fine, "12/10/2062")
    assert fine.avviso.text() == AVVISO_LONTANA
    scrivi_data(qtbot, fine, "12/10")  # senza anno: il più vicino a oggi
    assert malattia.modulo["fine"].valore == date(2026, 10, 12)
    assert not fine.avviso.isVisibleTo(fine)


def test_giustificativo_avvisa_dei_giorni_lontani(finestra, qtbot):
    pagina = finestra.nuova_pratica
    pagina.mostra_flusso("giustificativo")
    giorni = pagina.giustificativo.campi["giorni"]
    scrivi_data(qtbot, giorni, "12/10/2026, 13/10/2062")
    assert giorni.avviso.text() == AVVISO_GIORNI_LONTANI
    calendario = apri_calendario(giorni.editor)
    assert calendario.mese.selectedDate().toPython() == date(2026, 10, 12)
    calendario.close()


def test_filtri_dell_archivio_con_il_calendario(finestra):
    finestra.voci[1].click()
    archivio = finestra.archivio
    archivio.dal.setText("45/13/2026")
    assert archivio.dal.property("incerto")
    assert "non valida" in archivio.dal.toolTip()
    archivio.dal.clear()
    assert not archivio.dal.property("incerto")

    calendario = apri_calendario(archivio.al)
    assert calendario.mese.selectedDate().toPython() == OGGI
    calendario.scegli(date(2026, 1, 1))
    assert archivio.al.text() == "01/01/2026"
    pratiche = finestra.contesto.archivio.pratiche()
    attese = [p for p in pratiche if p.inizio and p.inizio <= date(2026, 1, 1)]
    assert archivio.pratiche.rowCount() == len(attese)
