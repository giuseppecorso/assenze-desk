"""Scelta di una zona dello schermo per l'OCR.

Si apre solo quando l'utente preme "OCR zona": mostra la schermata catturata,
si trascina un rettangolo, Esc annulla. La zona scelta diventa un'immagine
Pillow per l'adapter dell'OCR.
"""

from io import BytesIO

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from assenze_desk.gui import tema

LATO_MINIMO = 12
SUGGERIMENTO = "Trascina per scegliere la zona da leggere · Esc per annullare"


class SelezioneZona(QWidget):
    scelta = Signal(QPixmap)
    annullata = Signal()

    def __init__(self, schermata: QPixmap, geometria: QRect) -> None:
        super().__init__(
            None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(geometria)
        self._schermata = schermata
        self._inizio: QPoint | None = None
        self._fine: QPoint | None = None

    def zona(self) -> QRect:
        if self._inizio is None or self._fine is None:
            return QRect()
        return QRect(self._inizio, self._fine).normalized()

    def ritaglio(self, zona: QRect) -> QPixmap:
        """La zona nella schermata vera (che sugli schermi ad alta densità è più grande)."""
        scala = self._schermata.devicePixelRatio()
        return self._schermata.copy(
            QRect(
                round(zona.x() * scala),
                round(zona.y() * scala),
                round(zona.width() * scala),
                round(zona.height() * scala),
            )
        )

    def paintEvent(self, _evento) -> None:
        pittore = QPainter(self)
        pittore.drawPixmap(self.rect(), self._schermata)
        pittore.fillRect(self.rect(), QColor(0, 0, 0, 110))
        zona = self.zona()
        if not zona.isEmpty():
            pittore.drawPixmap(zona, self.ritaglio(zona))
            pittore.setPen(QPen(QColor(tema.colore("accento")), 2))
            pittore.drawRect(zona)
        pittore.setPen(QColor("#ffffff"))
        pittore.drawText(
            self.rect().adjusted(0, 24, 0, 0), Qt.AlignmentFlag.AlignHCenter, SUGGERIMENTO
        )
        pittore.end()

    def mousePressEvent(self, evento: QMouseEvent) -> None:
        self._inizio = self._fine = evento.position().toPoint()
        self.update()

    def mouseMoveEvent(self, evento: QMouseEvent) -> None:
        if self._inizio is not None:
            self._fine = evento.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, evento: QMouseEvent) -> None:
        self._fine = evento.position().toPoint()
        zona = self.zona()
        if zona.width() < LATO_MINIMO or zona.height() < LATO_MINIMO:
            self._inizio = self._fine = None  # clic senza trascinare: si riprova
            self.update()
            return
        self.scelta.emit(self.ritaglio(zona))
        self.close()

    def keyPressEvent(self, evento: QKeyEvent) -> None:
        if evento.key() == Qt.Key.Key_Escape:
            self.annullata.emit()
            self.close()


def in_pillow(immagine: QPixmap) -> Image.Image:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    immagine.save(buffer, "PNG")
    risultato = Image.open(BytesIO(bytes(buffer.data())))
    risultato.load()
    return risultato.convert("RGB")
