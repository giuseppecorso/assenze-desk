"""Sezione Impostazioni: pagine a sinistra, contenuto a destra, Salva in fondo.

Le impostazioni stanno in un solo file JSON nella cartella dell'utente.
Salvare le applica subito (tema, archivio, anagrafica); "Annulla modifiche"
torna all'ultimo salvataggio.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from assenze_desk.config import Impostazioni
from assenze_desk.gui.componenti import BarraMessaggi, etichetta, pulsante, riga
from assenze_desk.gui.errori import esegui
from assenze_desk.gui.pagine_impostazioni import (
    Pagina,
    PaginaAnagrafica,
    PaginaGenerali,
    PaginaMail,
    PaginaOcrInps,
    PaginaRegole,
    PaginaTipi,
    PaginaVocabolario,
)
from assenze_desk.servizi import Contesto


class SezioneImpostazioni(QWidget):
    salvate = Signal()

    def __init__(self, contesto: Contesto, messaggi: BarraMessaggi) -> None:
        super().__init__()
        self.contesto, self.messaggi = contesto, messaggi
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 12)
        layout.setSpacing(12)
        layout.addWidget(etichetta("Impostazioni", "titolo"))

        self.generali = PaginaGenerali()
        self.anagrafica = PaginaAnagrafica(contesto)
        self.pagine: list[Pagina] = [
            self.generali,
            self.anagrafica,
            PaginaMail(),
            PaginaRegole(),
            PaginaTipi(),
            PaginaVocabolario(),
            PaginaOcrInps(),
        ]
        self.menu = QListWidget()
        self.menu.setObjectName("sottomenu")
        self.menu.setFixedWidth(210)
        self.contenuto = QStackedWidget()
        for pagina in self.pagine:
            self.menu.addItem(pagina.titolo)
            contenitore = QWidget()
            interno = QVBoxLayout(contenitore)
            interno.setContentsMargins(0, 0, 8, 0)
            interno.addWidget(pagina)
            interno.addStretch(1)
            scorrimento = QScrollArea()
            scorrimento.setWidgetResizable(True)
            scorrimento.setFrameShape(QScrollArea.Shape.NoFrame)
            scorrimento.setWidget(contenitore)
            self.contenuto.addWidget(scorrimento)
        self.menu.currentRowChanged.connect(self.contenuto.setCurrentIndex)
        self.menu.setCurrentRow(0)
        corpo = QHBoxLayout()
        corpo.setSpacing(12)
        corpo.addWidget(self.menu)
        corpo.addWidget(self.contenuto, 1)
        layout.addLayout(corpo, 1)

        self.file = etichetta("", "secondario")
        self.annulla = pulsante("Annulla modifiche", "ripristina")
        self.salva = pulsante("Salva", "salva", "primario")
        layout.addLayout(riga(self.file, None, self.annulla, self.salva))
        self.annulla.clicked.connect(self.carica)
        self.salva.clicked.connect(lambda: esegui(self.messaggi, self._salva))
        self.carica()

    def carica(self) -> None:
        for pagina in self.pagine:
            pagina.carica(self.contesto.impostazioni)
        self.file.setText(f"Salvate in {self.contesto.file_impostazioni}")

    def mostra_tema(self, scelta: str) -> None:
        """Tema cambiato dalla barra laterale (già salvato)."""
        self.generali.tema.setCurrentIndex(max(self.generali.tema.findData(scelta), 0))

    def raccogli(self) -> Impostazioni:
        nuove = self.contesto.impostazioni
        for pagina in self.pagine:
            nuove = pagina.applica(nuove)
        return nuove

    def _salva(self) -> None:
        avvisi = self.contesto.salva_impostazioni(self.raccogli())
        self.carica()
        if avvisi:
            self.anagrafica.mostra(avvisi)
            self.messaggi.mostra("Impostazioni salvate. " + " ".join(avvisi), "attenzione")
        else:
            self.messaggi.mostra("Impostazioni salvate e applicate.", "ok")
        self.salvate.emit()
