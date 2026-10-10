"""Finestra principale: navigazione laterale con 4 sezioni, messaggi, log richiudibile.

Le sezioni sono Nuova pratica, Archivio, Statistiche e Impostazioni (al posto
delle 9 schede della v6.20). Si cambia sezione solo con un clic dell'utente.
Gli errori imprevisti finiscono nel log e nella barra dei messaggi.
"""

import logging
from collections.abc import Sequence
from dataclasses import replace
from types import TracebackType

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from assenze_desk.gui import icone, tema
from assenze_desk.gui.componenti import BarraMessaggi, Segmenti, etichetta
from assenze_desk.gui.errori import esegui
from assenze_desk.gui.nuova_pratica import NuovaPratica
from assenze_desk.gui.pannello_log import PannelloLog
from assenze_desk.servizi import Contesto

log = logging.getLogger(__name__)

SEZIONI = (
    ("Nuova pratica", "nuova"),
    ("Archivio", "archivio"),
    ("Statistiche", "statistiche"),
    ("Impostazioni", "impostazioni"),
)
TEMI = ("sistema", "chiaro", "scuro")


class FinestraPrincipale(QMainWindow):
    def __init__(self, contesto: Contesto, avvisi: Sequence[str] = ()) -> None:
        super().__init__()
        self.contesto = contesto
        self.setWindowTitle("Assenze Desk" + (" · demo" if contesto.demo else ""))
        self.resize(1360, 880)
        self.setMinimumSize(1100, 700)

        centrale = QWidget()
        centrale.setObjectName("principale")
        layout = QHBoxLayout(centrale)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._laterale())

        area = QVBoxLayout()
        area.setContentsMargins(0, 0, 0, 0)
        area.setSpacing(0)
        self.messaggi = BarraMessaggi()
        contenitore_messaggi = QVBoxLayout()
        contenitore_messaggi.setContentsMargins(24, 12, 24, 0)
        contenitore_messaggi.addWidget(self.messaggi)
        area.addLayout(contenitore_messaggi)

        self.sezioni = QStackedWidget()
        self.nuova_pratica = NuovaPratica(contesto, self.messaggi)
        self.sezioni.addWidget(self.nuova_pratica)
        for titolo, _icona in SEZIONI[1:]:
            self.sezioni.addWidget(_in_arrivo(titolo))
        area.addWidget(self.sezioni, 1)

        self.log = PannelloLog()
        self.log.collega()
        area.addWidget(self.log)
        layout.addLayout(area, 1)
        self.setCentralWidget(centrale)

        self.applica_tema(contesto.impostazioni.tema)
        if avvisi:
            self.messaggi.mostra(" ".join(avvisi), "attenzione")

    # --- Barra laterale ---

    def _laterale(self) -> QFrame:
        laterale = QFrame()
        laterale.setObjectName("laterale")
        laterale.setFixedWidth(208)
        layout = QVBoxLayout(laterale)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(2)

        logo = QLabel("AD")
        logo.setObjectName("logo")
        logo.setFixedSize(26, 26)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        marchio = QLabel("Assenze Desk")
        marchio.setObjectName("marchio")
        testata = QHBoxLayout()
        testata.setContentsMargins(8, 0, 0, 16)
        testata.setSpacing(8)
        testata.addWidget(logo)
        testata.addWidget(marchio)
        testata.addStretch(1)
        layout.addLayout(testata)

        self.navigazione = QButtonGroup(self)
        self.voci: list[QPushButton] = []
        for numero, (titolo, icona) in enumerate(SEZIONI):
            voce = QPushButton(titolo)
            voce.setProperty("ruolo", "voce")
            voce.setCheckable(True)
            voce.setCursor(Qt.CursorShape.PointingHandCursor)
            icone.metti(voce, icona, "testo_2", "accento")
            self.navigazione.addButton(voce, numero)
            self.voci.append(voce)
            layout.addWidget(voce)
        self.voci[0].setChecked(True)
        self.navigazione.idClicked.connect(self.mostra_sezione)
        layout.addStretch(1)

        if self.contesto.demo:
            demo = etichetta("Modalità demo: dati finti, Outlook non usato")
            demo.setObjectName("demo")
            demo.setWordWrap(True)
            layout.addWidget(demo)
            layout.addSpacing(8)
        layout.addWidget(etichetta("Tema", "secondario"))
        self.tema = Segmenti(["Sistema", "Chiaro", "Scuro"])
        self.tema.setProperty("compatto", True)
        self.tema.cambiato.connect(self._tema_scelto)
        layout.addWidget(self.tema)
        return laterale

    def mostra_sezione(self, indice: int) -> None:
        self.voci[indice].setChecked(True)
        self.sezioni.setCurrentIndex(indice)

    # --- Tema ---

    def applica_tema(self, scelta: str) -> None:
        tema.applica_tema(QApplication.instance(), scelta)
        self.tema.seleziona(TEMI.index(scelta) if scelta in TEMI else 0)
        icone.ricolora(self)

    def _tema_scelto(self, indice: int) -> None:
        scelta = TEMI[indice]
        self.applica_tema(scelta)
        nuove = replace(self.contesto.impostazioni, tema=scelta)
        esegui(self.messaggi, lambda: self.contesto.salva_impostazioni(nuove))

    # --- Errori e chiusura ---

    def errore_imprevisto(
        self, tipo: type[BaseException], errore: BaseException, traccia: TracebackType | None
    ) -> None:
        log.error("Errore imprevisto", exc_info=(tipo, errore, traccia))
        self.messaggi.mostra(f"Errore imprevisto: {errore}. I dettagli sono nel log.", "errore")

    def closeEvent(self, evento: QCloseEvent) -> None:
        self.log.scollega()
        super().closeEvent(evento)


def _in_arrivo(titolo: str) -> QWidget:
    pagina = QWidget()
    layout = QVBoxLayout(pagina)
    layout.setContentsMargins(24, 16, 24, 16)
    layout.addWidget(etichetta(titolo, "titolo"))
    layout.addWidget(etichetta("Sezione in costruzione.", "secondario"))
    layout.addStretch(1)
    return pagina
