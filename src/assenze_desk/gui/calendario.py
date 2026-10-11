"""Mini calendario a comparsa per le caselle con le date.

Si apre dall'icona a destra nella casella. Parte dalla data già scritta o, se
la casella è vuota, da oggi (cerchiata). Per una data sola un clic sceglie e
chiude. Per un elenco di giorni ogni clic aggiunge o toglie un giorno e
Maiusc+clic aggiunge i giorni feriali fino a quello (core/date_utente.py).
Esc o un clic fuori chiudono.
"""

from collections.abc import Callable, Sequence
from datetime import date

from PySide6.QtCore import QDate, QLocale, QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QKeyEvent, QPainter, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from assenze_desk.core.date_utente import aggiungi_feriali, alterna_giorno
from assenze_desk.gui import icone, tema

S1, S2, S3, S4, S5 = tema.SPAZIO


def in_qdate(giorno: date) -> QDate:
    return QDate(giorno.year, giorno.month, giorno.day)


class Mese(QCalendarWidget):
    """Il calendario di un mese, in italiano e da lunedì, con oggi cerchiato.

    Con più giorni da scegliere quelli scelti si disegnano pieni e la selezione
    di Qt (un giorno solo) non si vede.
    """

    def __init__(self, oggi: date, multipli: bool) -> None:
        super().__init__()
        self.oggi = in_qdate(oggi)
        self.multipli = multipli
        self.scelti: set[QDate] = set()
        self.setLocale(QLocale(QLocale.Language.Italian, QLocale.Country.Italy))
        self.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setGridVisible(False)
        tenue = QTextCharFormat()
        tenue.setForeground(QColor(tema.colore("testo_2")))
        self.setHeaderTextFormat(tenue)
        for giorno in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            self.setWeekdayTextFormat(giorno, tenue)
        frecce = (("qt_calendar_prevmonth", "indietro"), ("qt_calendar_nextmonth", "avanti"))
        for nome, icona in frecce:
            bottone = self.findChild(QToolButton, nome)
            if bottone is not None:
                icone.metti(bottone, icona)
        self.setProperty("multipli", multipli)  # il foglio di stile nasconde la selezione

    def paintCell(self, pittore: QPainter, rettangolo: QRect, giorno: QDate) -> None:
        if self.multipli and giorno in self.scelti:
            pittore.save()
            pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
            pittore.setPen(Qt.PenStyle.NoPen)
            pittore.setBrush(QColor(tema.colore("accento")))
            pittore.drawRoundedRect(QRectF(rettangolo).adjusted(2, 2, -2, -2), 4, 4)
            pittore.setPen(QColor(tema.colore("accento_testo")))
            pittore.drawText(rettangolo, Qt.AlignmentFlag.AlignCenter, str(giorno.day()))
            pittore.restore()
            return
        if (giorno.month(), giorno.year()) != (self.monthShown(), self.yearShown()):
            pittore.save()
            pittore.setOpacity(0.4)  # giorni del mese prima e dopo: più chiari
            super().paintCell(pittore, rettangolo, giorno)
            pittore.restore()
            return
        super().paintCell(pittore, rettangolo, giorno)
        if giorno == self.oggi:
            pittore.save()
            pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
            pittore.setPen(QColor(tema.colore("accento")))
            pittore.setBrush(Qt.BrushStyle.NoBrush)
            pittore.drawRoundedRect(QRectF(rettangolo).adjusted(2.5, 2.5, -2.5, -2.5), 4, 4)
            pittore.restore()


class Calendario(QFrame):
    """Il riquadro a comparsa; `scelti` porta i giorni scelti (uno solo per una data)."""

    scelti = Signal(tuple)

    def __init__(
        self, giorni: Sequence[date], oggi: date, multipli: bool, genitore: QLineEdit
    ) -> None:
        super().__init__(genitore, Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setProperty("ruolo", "calendario")
        self.multipli = multipli
        self.giorni = tuple(sorted(giorni))
        self._ultimo: date | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S2, S2, S2, S2)
        layout.setSpacing(S2)

        self.mese = Mese(oggi, multipli)
        partenza = self.giorni[0] if self.giorni else oggi
        self.mese.setSelectedDate(in_qdate(partenza))
        layout.addWidget(self.mese)
        if multipli:
            self.mese.clicked.connect(self._clic_multiplo)
            # Widget semplici: componenti.py usa questo modulo e non si importa da qui
            spiegazione = QLabel(
                "Clic: aggiungi o togli un giorno\nMaiusc+clic: i feriali fino a quel giorno"
            )
            spiegazione.setProperty("ruolo", "secondario")
            self.fatto = QPushButton("Fatto")
            self.fatto.setProperty("variante", "primario")
            self.fatto.clicked.connect(self.close)
            piede = QHBoxLayout()
            piede.addWidget(spiegazione, 1)
            piede.addWidget(self.fatto)
            layout.addLayout(piede)
            self._aggiorna_scelti()
        else:
            self.mese.clicked.connect(self._clic_singolo)
            self.mese.activated.connect(self._clic_singolo)

    # --- Scelta ---

    def scegli(self, giorno: date, intervallo: bool = False) -> None:
        if not self.multipli:
            self.scelti.emit((giorno,))
            self.close()
            return
        if intervallo and self._ultimo is not None:
            self.giorni = aggiungi_feriali(self.giorni, self._ultimo, giorno)
        else:
            self.giorni = alterna_giorno(self.giorni, giorno)
        self._ultimo = giorno
        self._aggiorna_scelti()
        self.scelti.emit(self.giorni)

    def _clic_singolo(self, giorno: QDate) -> None:
        self.scegli(giorno.toPython())

    def _clic_multiplo(self, giorno: QDate) -> None:
        maiuscolo = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
        self.scegli(giorno.toPython(), intervallo=bool(maiuscolo))

    def _aggiorna_scelti(self) -> None:
        self.mese.scelti = {in_qdate(giorno) for giorno in self.giorni}
        self.mese.updateCells()

    # --- Comparsa ---

    def apri_sotto(self, casella: QLineEdit) -> None:
        self.adjustSize()
        punto = casella.mapToGlobal(QPoint(0, casella.height() + S1))
        schermo = casella.screen().availableGeometry()
        if punto.y() + self.height() > schermo.bottom():  # non c'è posto sotto: sopra
            punto.setY(casella.mapToGlobal(QPoint(0, 0)).y() - self.height() - S1)
        punto.setX(max(schermo.left(), min(punto.x(), schermo.right() - self.width())))
        self.move(punto)
        self.show()
        self.mese.setFocus()

    def keyPressEvent(self, evento: QKeyEvent) -> None:
        if evento.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(evento)


def aggiungi_calendario(
    casella: QLineEdit,
    giorni_scritti: Callable[[], Sequence[date]],
    oggi: Callable[[], date],
    scegli: Callable[[tuple[date, ...]], None],
    multipli: bool = False,
) -> QAction:
    """L'icona del calendario a destra nella casella; il clic apre il mini calendario."""
    azione = icone.in_casella(casella, "calendario", QLineEdit.ActionPosition.TrailingPosition)
    azione.setToolTip("Scegli dal calendario")

    def apri() -> None:
        calendario = Calendario(giorni_scritti(), oggi(), multipli, casella)
        calendario.scelti.connect(scegli)
        calendario.apri_sotto(casella)

    azione.triggered.connect(apri)
    return azione
