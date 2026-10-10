"""Pannello della mail: da dove arriva il testo e quando parte l'analisi.

L'analisi parte solo con Analizza, Ctrl+Invio, oppure subito dopo un import o
un incolla (in una casella vuota o al posto di tutto il testo). Scrivere nel
testo non la avvia mai (problema noto 6).
"""

from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from assenze_desk.gui import icone
from assenze_desk.gui.componenti import Scheda, etichetta, pulsante, riga

SEGNAPOSTO = (
    "Incolla qui il testo della mail, oppure usa i pulsanti qui sopra.\n"
    "L'analisi parte con Analizza o Ctrl+Invio, mai mentre scrivi."
)


class EditorMail(QPlainTextEdit):
    incollato = Signal()  # incolla in una casella vuota o al posto di tutto il testo
    ctrl_invio = Signal()

    def insertFromMimeData(self, sorgente: QMimeData) -> None:
        tutto = not self.toPlainText().strip() or (
            self.textCursor().selectedText().replace("\N{PARAGRAPH SEPARATOR}", "\n")
            == self.toPlainText()
        )
        super().insertFromMimeData(sorgente)
        if tutto and self.toPlainText().strip():
            self.incollato.emit()

    def keyPressEvent(self, evento: QKeyEvent) -> None:
        invio = evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        if invio and evento.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.ctrl_invio.emit()
            return
        super().keyPressEvent(evento)


class PannelloMail(Scheda):
    testo_nuovo = Signal()  # incollato: non è più la mail importata (arriva prima dell'analisi)
    analisi_richiesta = Signal()
    importa_richiesto = Signal()
    selezione_richiesta = Signal()
    ocr_richiesto = Signal()
    pdf_richiesto = Signal()

    def __init__(self) -> None:
        super().__init__("Mail", "mail")
        self.importa = pulsante(
            "Importa da Outlook", "mail", suggerimento="La mail selezionata in Outlook"
        )
        self.incolla = pulsante("Incolla", "incolla", suggerimento="Il testo copiato negli appunti")
        self.selezione = pulsante(
            "Testo selezionato",
            "selezione",
            suggerimento="Il testo selezionato in un'altra finestra",
        )
        self.ocr = pulsante("OCR zona", "ocr", suggerimento="Leggi una zona dello schermo")
        self.corpo.addLayout(riga(self.importa, self.incolla, self.selezione, self.ocr))
        self.meta = etichetta("", "secondario", a_capo=True)
        self.meta.hide()
        self.corpo.addWidget(self.meta)

        self.editor = EditorMail()
        self.editor.setPlaceholderText(SEGNAPOSTO)
        self.editor.setMinimumHeight(300)
        self.corpo.addWidget(self.editor, 1)

        self.pdf = etichetta("", "secondario")
        self._icona_pdf = icone.etichetta("file")
        self.apri_pdf = pulsante(
            "Apri un PDF…", "file", "piatto", "Il certificato di malattia in PDF"
        )
        self.riga_pdf = QWidget()
        self.riga_pdf.setLayout(riga(self._icona_pdf, self.pdf, self.apri_pdf))
        self.analizza = pulsante("Analizza  (Ctrl+Invio)", "analizza", "primario")
        fondo = riga(self.riga_pdf, self.analizza, allunga=False)
        fondo.setStretch(0, 1)  # il nome del PDF usa tutto lo spazio libero
        self.corpo.addLayout(fondo)
        self.mostra_pdf(None)

        self.importa.clicked.connect(self.importa_richiesto)
        self.incolla.clicked.connect(self._incolla)
        self.selezione.clicked.connect(self.selezione_richiesta)
        self.ocr.clicked.connect(self.ocr_richiesto)
        self.apri_pdf.clicked.connect(self.pdf_richiesto)
        self.analizza.clicked.connect(self.analisi_richiesta)
        self.editor.incollato.connect(self._incollato)
        self.editor.ctrl_invio.connect(self.analisi_richiesta)
        for tasti in ("Ctrl+Return", "Ctrl+Enter"):
            scorciatoia = QShortcut(QKeySequence(tasti), self)
            scorciatoia.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            scorciatoia.activated.connect(self.analisi_richiesta)

    def testo(self) -> str:
        return self.editor.toPlainText()

    def imposta_testo(self, testo: str, provenienza: str = "") -> None:
        """Testo nuovo da import, incolla, selezione o OCR (l'analisi la chiede chi chiama)."""
        self.editor.setPlainText(testo)
        self.mostra_provenienza(provenienza)

    def mostra_provenienza(self, testo: str) -> None:
        self.meta.setText(testo)
        self.meta.setVisible(bool(testo))

    def mostra_pdf(self, percorso: Path | None) -> None:
        self.pdf.setText(Path(percorso).name if percorso else "Nessun certificato PDF")

    def _incolla(self) -> None:
        testo = QGuiApplication.clipboard().text()
        if not testo.strip():
            self.mostra_provenienza("Gli appunti sono vuoti: copia prima il testo della mail.")
            return
        self.imposta_testo(testo, "Incollata dagli appunti")
        self._incollato()

    def _incollato(self) -> None:
        self.testo_nuovo.emit()
        self.analisi_richiesta.emit()
