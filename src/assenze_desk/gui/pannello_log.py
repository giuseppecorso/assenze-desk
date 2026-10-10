"""Pannello del log, richiudibile, in fondo alla finestra.

Mostra le righe del logger dell'app con lo stesso mascheramento del file:
il codice fiscale non compare mai in chiaro.
"""

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFrame, QPlainTextEdit, QVBoxLayout

from assenze_desk.gui import tema
from assenze_desk.gui.componenti import etichetta, pulsante, riga
from assenze_desk.registro import FormatterRiservato

RIGHE_MASSIME = 500
ALTEZZA_APERTO = 130


class _Segnali(QObject):
    riga = Signal(str)


class GestoreLogQt(logging.Handler):
    """Gira le righe del log al pannello (anche da altri thread, con un segnale)."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.segnali = _Segnali()
        self.setFormatter(FormatterRiservato("%(asctime)s  %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.segnali.riga.emit(self.format(record))
        except RuntimeError:  # pannello già chiuso
            self.handleError(record)


class PannelloLog(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("log")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(tema.SPAZIO[4], tema.SPAZIO[0], tema.SPAZIO[4], tema.SPAZIO[1])
        layout.setSpacing(tema.SPAZIO[0])
        self.interruttore = pulsante("Log", "log", "piatto", "Mostra o nasconde il log")
        self.interruttore.setCheckable(True)
        self.interruttore.setChecked(True)
        self.interruttore.toggled.connect(self._mostra)
        layout.addLayout(
            riga(self.interruttore, etichetta("codice fiscale sempre mascherato", "secondario"))
        )
        self.testo = QPlainTextEdit()
        self.testo.setObjectName("testo-log")
        self.testo.setReadOnly(True)
        self.testo.setMaximumBlockCount(RIGHE_MASSIME)
        self.testo.setFixedHeight(ALTEZZA_APERTO)
        layout.addWidget(self.testo)
        self.gestore = GestoreLogQt()
        self.gestore.segnali.riga.connect(self.testo.appendPlainText)

    def collega(self) -> None:
        logging.getLogger("assenze_desk").addHandler(self.gestore)

    def scollega(self) -> None:
        logging.getLogger("assenze_desk").removeHandler(self.gestore)

    def _mostra(self, aperto: bool) -> None:
        self.testo.setVisible(aperto)
