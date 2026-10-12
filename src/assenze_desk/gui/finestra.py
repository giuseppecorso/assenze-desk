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
from assenze_desk.gui.archivio import Archivio
from assenze_desk.gui.componenti import BarraMessaggi, Segmenti, etichetta
from assenze_desk.gui.errori import esegui
from assenze_desk.gui.impostazioni import SezioneImpostazioni
from assenze_desk.gui.nuova_pratica import NuovaPratica
from assenze_desk.gui.pannello_log import PannelloLog
from assenze_desk.gui.statistiche import Statistiche
from assenze_desk.servizi import Contesto
from assenze_desk.storage.archivio import Pratica

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
        self.archivio = Archivio(contesto, self.messaggi)
        self.statistiche = Statistiche(contesto)
        self.impostazioni = SezioneImpostazioni(contesto, self.messaggi)
        for sezione in (self.nuova_pratica, self.archivio, self.statistiche, self.impostazioni):
            self.sezioni.addWidget(sezione)
        area.addWidget(self.sezioni, 1)
        self.nuova_pratica.archivio_cambiato.connect(self.archivio.aggiorna)
        self.archivio.apri_pratica.connect(self._riapri_pratica)
        self.impostazioni.salvate.connect(self._impostazioni_salvate)

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

        logo = QLabel()
        logo.setPixmap(icone.pixmap_app(26))
        logo.setFixedSize(26, 26)
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
        """Cambio di sezione: solo da un clic dell'utente."""
        self.voci[indice].setChecked(True)
        if self.sezioni.widget(indice) is self.archivio:
            self.archivio.aggiorna()
        elif self.sezioni.widget(indice) is self.statistiche:
            self.statistiche.aggiorna()
        self.sezioni.setCurrentIndex(indice)

    def _riapri_pratica(self, pratica: Pratica) -> None:
        self.nuova_pratica.carica_pratica(pratica)
        self.mostra_sezione(0)

    def _impostazioni_salvate(self) -> None:
        self.applica_tema(self.contesto.impostazioni.tema)
        self.nuova_pratica.impostazioni_cambiate()

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
        self.impostazioni.mostra_tema(scelta)

    # --- Errori e chiusura ---

    def errore_imprevisto(
        self, tipo: type[BaseException], errore: BaseException, traccia: TracebackType | None
    ) -> None:
        log.error("Errore imprevisto", exc_info=(tipo, errore, traccia))
        self.messaggi.mostra(f"Errore imprevisto: {errore}. I dettagli sono nel log.", "errore")

    def closeEvent(self, evento: QCloseEvent) -> None:
        self.log.scollega()
        super().closeEvent(evento)
