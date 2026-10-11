"""Sezione Statistiche: numeri principali, giorni per mese, stati, classifiche.

I calcoli sono nel core (core/statistiche.py) con le soglie delle impostazioni;
qui si sceglie il periodo e si mostra. I grafici sono semplici e disegnati
dall'app con i colori del tema, senza librerie esterne.
"""

from collections.abc import Sequence
from datetime import date, timedelta

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from assenze_desk.core.statistiche import PraticaStatistica, Riepilogo, riepilogo
from assenze_desk.gui import tema
from assenze_desk.gui.componenti import Scheda, etichetta, riga
from assenze_desk.servizi import Contesto

MESI = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")
MESI_NEL_GRAFICO = 12
PERIODI = ("Ultimi 3 mesi", "Anno in corso", "Tutto")
COLORI_STATO = {
    "Chiusa": "ok",
    "Da inviare": "attenzione_bordo",
    "Parziale": "accento",
    "Incompleta": "errore",
}
CLASSIFICA = 5


class GraficoBarre(QWidget):
    """Barre verticali con l'etichetta sotto e il valore sopra."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(190)
        # Il grafico riempie la scheda: il titolo resta in alto
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.valori: list[tuple[str, int]] = []

    def imposta(self, valori: Sequence[tuple[str, int]]) -> None:
        self.valori = list(valori)
        self.update()

    def paintEvent(self, _evento) -> None:
        pittore = QPainter(self)
        pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
        pittore.setPen(QColor(tema.colore("testo_2")))
        if not self.valori:
            pittore.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Nessun dato nel periodo")
            pittore.end()
            return
        massimo = max(valore for _e, valore in self.valori) or 1
        larghezza = self.width() / len(self.valori)
        alto_testo = self.fontMetrics().height()
        area = self.height() - 2 * alto_testo - 8
        for numero, (testo, valore) in enumerate(self.valori):
            x = numero * larghezza
            altezza = area * valore / massimo
            barra = QRectF(
                x + larghezza * 0.18, alto_testo + 4 + area - altezza, larghezza * 0.64, altezza
            )
            pittore.setPen(Qt.PenStyle.NoPen)
            pittore.setBrush(QColor(tema.colore("accento")))
            pittore.drawRoundedRect(barra, 3, 3)
            pittore.setPen(QColor(tema.colore("testo_2")))
            sotto = QRectF(x, self.height() - alto_testo, larghezza, alto_testo)
            pittore.drawText(sotto, Qt.AlignmentFlag.AlignCenter, testo)
            sopra = QRectF(x, barra.top() - alto_testo - 2, larghezza, alto_testo)
            pittore.drawText(sopra, Qt.AlignmentFlag.AlignCenter, str(valore))
        pittore.end()


class BarreOrizzontali(QWidget):
    """Una barra per voce, lunga in proporzione al totale."""

    ALTEZZA_RIGA = 26

    def __init__(self) -> None:
        super().__init__()
        self.voci: list[tuple[str, int, str]] = []

    def imposta(self, voci: Sequence[tuple[str, int, str]]) -> None:
        self.voci = list(voci)
        self.setMinimumHeight(self.ALTEZZA_RIGA * max(len(self.voci), 1))
        self.update()

    def paintEvent(self, _evento) -> None:
        pittore = QPainter(self)
        pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
        totale = sum(valore for _e, valore, _c in self.voci) or 1
        etichette, numeri = 90, 34
        traccia = self.width() - etichette - numeri - 16
        for numero, (testo, valore, ruolo) in enumerate(self.voci):
            y = numero * self.ALTEZZA_RIGA
            pittore.setPen(QColor(tema.colore("testo")))
            pittore.drawText(
                QRectF(0, y, etichette, self.ALTEZZA_RIGA), Qt.AlignmentFlag.AlignVCenter, testo
            )
            fondo = QRectF(etichette + 8, y + self.ALTEZZA_RIGA / 2 - 4, traccia, 8)
            pittore.setPen(Qt.PenStyle.NoPen)
            pittore.setBrush(QColor(tema.colore("superficie_2")))
            pittore.drawRoundedRect(fondo, 4, 4)
            pittore.setBrush(QColor(tema.colore(ruolo)))
            pittore.drawRoundedRect(
                QRectF(fondo.left(), fondo.top(), traccia * valore / totale, 8), 4, 4
            )
            pittore.setPen(QColor(tema.colore("testo_2")))
            pittore.drawText(
                QRectF(self.width() - numeri, y, numeri, self.ALTEZZA_RIGA),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                str(valore),
            )
        pittore.end()


def _scheda_numero(etichetta_testo: str) -> tuple[Scheda, object]:
    scheda = Scheda()
    numero = etichetta("0", "numero")
    scheda.corpo.addWidget(numero)
    scheda.corpo.addWidget(etichetta(etichetta_testo, "secondario"))
    return scheda, numero


def _classifica(titolo: str) -> tuple[Scheda, QTableWidget]:
    scheda = Scheda(titolo)
    tabella = QTableWidget(0, 3)
    tabella.setHorizontalHeaderLabels(["", "Pratiche", "Giorni"])
    tabella.verticalHeader().hide()
    tabella.setShowGrid(False)
    tabella.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tabella.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    tabella.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    tabella.setMinimumHeight(190)
    scheda.corpo.addWidget(tabella)
    return scheda, tabella


def filtra_periodo(
    pratiche: Sequence[PraticaStatistica], periodo: str, oggi: date
) -> list[PraticaStatistica]:
    if periodo == "Tutto":
        return list(pratiche)
    inizio = oggi - timedelta(days=91) if periodo == "Ultimi 3 mesi" else date(oggi.year, 1, 1)
    return [p for p in pratiche if p.inizio is not None and p.inizio >= inizio]


class Statistiche(QWidget):
    def __init__(self, contesto: Contesto) -> None:
        super().__init__()
        self.contesto = contesto
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 12)
        layout.setSpacing(12)
        self.periodo = QComboBox()
        self.periodo.addItems(PERIODI)
        self.periodo.currentIndexChanged.connect(self.aggiorna)
        layout.addLayout(riga(etichetta("Statistiche", "titolo"), None, self.periodo))

        numeri = QGridLayout()
        numeri.setSpacing(12)
        self.numeri = {}
        for colonna, (chiave, testo) in enumerate(
            (
                ("pratiche", "Pratiche di malattia"),
                ("dipendenti", "Dipendenti coinvolti"),
                ("giorni", "Giorni di malattia"),
                ("tempo", "Tempo medio di gestione (senza valori anomali)"),
            )
        ):
            scheda, numero = _scheda_numero(testo)
            self.numeri[chiave] = numero
            numeri.addWidget(scheda, 0, colonna)
        layout.addLayout(numeri)

        grafici = QGridLayout()
        grafici.setSpacing(12)
        scheda_mesi = Scheda("Giorni di malattia per mese")
        self.mesi = GraficoBarre()
        scheda_mesi.corpo.addWidget(self.mesi)
        scheda_stati = Scheda("Stato delle pratiche")
        self.stati = BarreOrizzontali()
        scheda_stati.corpo.addWidget(self.stati)
        self.lunghi = etichetta("", "secondario")
        scheda_stati.corpo.addWidget(self.lunghi)
        scheda_stati.corpo.addStretch(1)
        grafici.addWidget(scheda_mesi, 0, 0)
        grafici.addWidget(scheda_stati, 0, 1)
        grafici.setColumnStretch(0, 3)
        grafici.setColumnStretch(1, 2)
        scheda_clienti, self.clienti = _classifica("Clienti con più giorni")
        scheda_dipendenti, self.dipendenti = _classifica("Dipendenti con più giorni")
        grafici.addWidget(scheda_clienti, 1, 0)
        grafici.addWidget(scheda_dipendenti, 1, 1)
        layout.addLayout(grafici, 1)
        self.aggiorna()

    def aggiorna(self) -> None:
        imp = self.contesto.impostazioni
        pratiche = filtra_periodo(
            self.contesto.pratiche_statistiche(),
            self.periodo.currentText(),
            self.contesto.adesso().date(),
        )
        self.mostra(riepilogo(pratiche, imp.soglia_ufficio, imp.minuti_oltre_la_media))

    def mostra(self, dati: Riepilogo) -> None:
        self.numeri["pratiche"].setText(str(dati.pratiche))
        self.numeri["dipendenti"].setText(str(dati.dipendenti))
        self.numeri["giorni"].setText(str(dati.giorni))
        minuti = dati.tempo.media_min
        self.numeri["tempo"].setText(f"{round(minuti)} min" if minuti is not None else "—")
        mesi = list(dati.giorni_per_mese.items())[-MESI_NEL_GRAFICO:]
        self.mesi.imposta([(MESI[int(chiave[5:]) - 1], giorni) for chiave, giorni in mesi])
        self.stati.imposta(
            [
                (str(stato), quante, COLORI_STATO[str(stato)])
                for stato, quante in dati.per_stato.items()
            ]
        )
        self.lunghi.setText(
            f"Episodi oltre la soglia della mail all'ufficio: {dati.episodi_lunghi} "
            f"({dati.percentuale_episodi_lunghi:g}%)"
        )
        for tabella, righe in (
            (self.clienti, dati.per_cliente),
            (self.dipendenti, dati.per_dipendente),
        ):
            tabella.setRowCount(min(len(righe), CLASSIFICA))
            for numero, (nome, giorni, pratiche) in enumerate(righe[:CLASSIFICA]):
                for colonna, testo in enumerate((nome, str(pratiche), str(giorni))):
                    voce = QTableWidgetItem(testo)
                    if colonna:
                        voce.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                    tabella.setItem(numero, colonna, voce)
