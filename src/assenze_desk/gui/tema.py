"""Design system: colori, misure e foglio di stile (QSS) dei temi chiaro e scuro.

I valori sono quelli del mockup approvato (docs/mockup/mockup.html). Si
definiscono una volta qui: le schermate indicano solo il ruolo di un widget
(property "ruolo", "variante", "origine", "badge"...), mai un colore. I widget
disegnati a mano (interruttore, grafici) leggono i colori con `colore()`.
"""

import tempfile
from collections.abc import Mapping
from pathlib import Path
from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QWidget

CHIARO = {
    "sfondo": "#f4f5f7",
    "superficie": "#ffffff",
    "superficie_2": "#f0f2f5",
    "bordo": "#dde1e6",
    "testo": "#1f2328",
    "testo_2": "#5f6b7a",
    "accento": "#2563eb",
    "accento_testo": "#ffffff",
    "accento_tenue": "#e8f0fe",
    "ok": "#1a7f37",
    "ok_tenue": "#e6f4ea",
    "attenzione": "#8a5a00",
    "attenzione_tenue": "#fff4d6",
    "attenzione_bordo": "#e0b000",
    "errore": "#cf222e",
    "errore_tenue": "#fdecee",
    "pdf": "#7c3aed",
    "pdf_tenue": "#f1ebff",
    "anagrafica": "#0e7c86",
    "anagrafica_tenue": "#e0f5f6",
    "manuale": "#5f6b7a",
    "manuale_tenue": "#eceef1",
}
SCURO = {
    "sfondo": "#16181c",
    "superficie": "#1f2228",
    "superficie_2": "#272b32",
    "bordo": "#353b44",
    "testo": "#e6e8eb",
    "testo_2": "#9aa4b2",
    "accento": "#5b9bff",
    "accento_testo": "#0b1220",
    "accento_tenue": "#1d2a40",
    "ok": "#4cc38a",
    "ok_tenue": "#16301f",
    "attenzione": "#e3b341",
    "attenzione_tenue": "#3a2f12",
    "attenzione_bordo": "#b8902a",
    "errore": "#ff7b7b",
    "errore_tenue": "#3d1d20",
    "pdf": "#b69cff",
    "pdf_tenue": "#2a2140",
    "anagrafica": "#4fd1c5",
    "anagrafica_tenue": "#123236",
    "manuale": "#b0b8c4",
    "manuale_tenue": "#2c3038",
}
TEMI = {"chiaro": CHIARO, "scuro": SCURO}

RAGGIO_PICCOLO = 6
RAGGIO_GRANDE = 10
SPAZIO = (4, 8, 12, 16, 24)  # le sole spaziature usate nei layout
CORPO_PUNTI = 10  # dimensione del testo; il font è quello di sistema

# Origine del dato (core/campi.py) → colori della sua etichetta
COLORI_ORIGINE = {
    "Testo": ("accento", "accento_tenue"),
    "PDF": ("pdf", "pdf_tenue"),
    "Anagrafica": ("anagrafica", "anagrafica_tenue"),
    "Manuale": ("manuale", "manuale_tenue"),
    "Archivio": ("ok", "ok_tenue"),
}
# Stato della pratica (core/stato.py) → colori del badge
COLORI_STATO = {
    "Incompleta": ("errore", "errore_tenue"),
    "Da inviare": ("attenzione", "attenzione_tenue"),
    "Parziale": ("accento", "accento_tenue"),
    "Chiusa": ("ok", "ok_tenue"),
}

_QSS = Template(
    """
QWidget { color: $testo; font-size: ${corpo}pt; }
QMainWindow, QWidget#principale, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {
    background: $sfondo;
}
QFrame#laterale { background: $superficie; border-right: 1px solid $bordo; }
QLabel#marchio { font-size: 12pt; font-weight: 600; }
QPushButton[ruolo="voce"] {
    text-align: left; padding: 8px 10px; border: none; border-radius: ${r1}px;
    color: $testo_2; background: transparent;
}
QPushButton[ruolo="voce"]:hover { background: $superficie_2; }
QPushButton[ruolo="voce"]:checked { background: $accento_tenue; color: $accento; font-weight: 600; }
QLabel#demo {
    background: $attenzione_tenue; color: $attenzione; border-radius: ${r1}px; padding: 6px 10px;
    font-size: 9pt;
}

QFrame[ruolo="scheda"] {
    background: $superficie; border: 1px solid $bordo; border-radius: ${r2}px;
}
QFrame[ruolo="scheda"] QLabel { background: transparent; }
QLabel[ruolo="titolo"] { font-size: 15pt; font-weight: 600; }
QLabel[ruolo="titolo-scheda"] { font-weight: 600; }
QLabel[ruolo="secondario"] { color: $testo_2; font-size: 9pt; }
QLabel[ruolo="numero"] { font-size: 20pt; font-weight: 600; }
QLabel[ruolo="avviso-campo"] { color: $attenzione; font-size: 9pt; }
QFrame[ruolo="separatore"] { background: $bordo; max-height: 1px; border: none; }

QPushButton {
    background: $superficie; border: 1px solid $bordo; border-radius: ${r1}px; padding: 5px 12px;
}
QPushButton:hover { background: $superficie_2; }
QPushButton:pressed { background: $bordo; }
QPushButton:disabled { color: $testo_2; background: $superficie_2; }
QPushButton[variante="primario"] {
    background: $accento; border-color: $accento; color: $accento_testo; font-weight: 600;
}
QPushButton[variante="primario"]:disabled {
    background: $bordo; border-color: $bordo; color: $testo_2;
}
QPushButton[variante="piatto"] {
    border: none; background: transparent; color: $accento; padding: 4px 6px;
}
QPushButton[variante="piatto"]:hover { background: $accento_tenue; }
QPushButton[variante="piatto"]:disabled { color: $testo_2; background: transparent; }

QFrame[ruolo="segmenti"] {
    background: $superficie_2; border: 1px solid $bordo; border-radius: 8px;
}
QPushButton[ruolo="segmento"] {
    border: none; background: transparent; color: $testo_2; padding: 5px 14px;
    border-radius: ${r1}px;
}
QPushButton[ruolo="segmento"]:checked { background: $superficie; color: $testo; font-weight: 600; }
QFrame[compatto="true"] QPushButton[ruolo="segmento"] { padding: 4px 4px; font-size: 9pt; }

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: $superficie; border: 1px solid $bordo; border-radius: ${r1}px; padding: 5px 8px;
    selection-background-color: $accento; selection-color: $accento_testo;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: $accento; }
QLineEdit:disabled, QComboBox:disabled { color: $testo_2; background: $superficie_2; }
QLineEdit[incerto="true"], QComboBox[incerto="true"] {
    border-color: $attenzione_bordo; background: $attenzione_tenue;
}
QLineEdit[mono="true"] { font-family: "Cascadia Mono", Consolas, monospace; }
QComboBox::drop-down { border: none; background: transparent; width: 22px; }
$freccia
QComboBox QAbstractItemView {
    background: $superficie; border: 1px solid $bordo; selection-background-color: $accento_tenue;
    selection-color: $testo;
}

QLabel[origine] { border-radius: 4px; padding: 1px 6px; font-size: 8pt; font-weight: 600; }
$origini
QLabel[badge] { border-radius: 9px; padding: 2px 9px; font-size: 9pt; font-weight: 600; }
$stati

QFrame[avviso="attenzione"] { background: $attenzione_tenue; border-radius: ${r1}px; }
QFrame[avviso="ok"] { background: $ok_tenue; border-radius: ${r1}px; }
QFrame[avviso="info"] { background: $accento_tenue; border-radius: ${r1}px; }
QFrame[avviso="errore"] { background: $errore_tenue; border-radius: ${r1}px; }
QFrame[avviso] QLabel { background: transparent; }
QFrame[avviso="attenzione"] QLabel[ruolo="icona-avviso"] { color: $attenzione; }
QFrame[avviso="errore"] QLabel[ruolo="testo-avviso"] { color: $errore; font-weight: 600; }

QTableWidget, QListWidget {
    background: $superficie; border: none; gridline-color: $bordo;
    selection-background-color: $accento_tenue; selection-color: $testo;
    alternate-background-color: $superficie_2;
}
QFrame[ruolo="scheda"] QTableWidget, QFrame[ruolo="scheda"] QListWidget { background: transparent; }
QListWidget#sottomenu::item { padding: 7px 10px; border-radius: ${r1}px; color: $testo_2; }
QListWidget#sottomenu::item:selected {
    background: $accento_tenue; color: $accento; font-weight: 600;
}
QHeaderView::section {
    background: transparent; color: $testo_2; border: none; border-bottom: 1px solid $bordo;
    padding: 6px 8px; font-weight: 600; font-size: 9pt;
}
QTableCornerButton::section { background: transparent; border: none; }
QTableWidget::indicator, QCheckBox::indicator {
    width: 14px; height: 14px; border: 1px solid $testo_2; border-radius: 4px;
    background: $superficie;
}
QTableWidget::indicator:checked, QCheckBox::indicator:checked {
    background: $accento; border-color: $accento;
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: $bordo; border-radius: 5px;
}
QScrollBar::handle:vertical { min-height: 28px; }
QScrollBar::handle:horizontal { min-width: 28px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QFrame#log { background: $superficie; border-top: 1px solid $bordo; }
QPlainTextEdit#testo-log {
    border: none; background: $superficie; color: $testo_2;
    font-family: "Cascadia Mono", Consolas, monospace; font-size: 9pt;
}
QToolTip { background: $superficie; color: $testo; border: 1px solid $bordo; padding: 4px; }

QFrame[ruolo="calendario"] { background: $superficie; border: 1px solid $bordo; }
QCalendarWidget QWidget#qt_calendar_navigationbar { background: $superficie; }
QCalendarWidget QToolButton {
    background: transparent; border: none; border-radius: ${r1}px; padding: 4px 8px;
    color: $testo; font-weight: 600;
}
QCalendarWidget QToolButton:hover { background: $superficie_2; }
QCalendarWidget QToolButton::menu-indicator { image: none; width: 0; }
QCalendarWidget QAbstractItemView {
    background: $superficie; outline: 0;
    selection-background-color: $accento; selection-color: $accento_testo;
}
QCalendarWidget[multipli="true"] QAbstractItemView {
    selection-background-color: $superficie; selection-color: $testo;
}
QCalendarWidget QSpinBox { padding: 2px 4px; }
"""
)


def foglio_di_stile(colori: Mapping[str, str], freccia: str = "") -> str:
    """Il QSS del tema; `freccia` è il file dell'icona dei menu a tendina."""
    origini = "\n".join(
        f'QLabel[origine="{nome}"] {{ color: {colori[testo]}; background: {colori[sfondo]}; }}'
        for nome, (testo, sfondo) in COLORI_ORIGINE.items()
    )
    stati = "\n".join(
        f'QLabel[badge="{nome}"] {{ color: {colori[testo]}; background: {colori[sfondo]}; }}'
        for nome, (testo, sfondo) in COLORI_STATO.items()
    )
    return _QSS.substitute(
        colori,
        corpo=CORPO_PUNTI,
        r1=RAGGIO_PICCOLO,
        r2=RAGGIO_GRANDE,
        origini=origini,
        stati=stati,
        freccia=(
            f"QComboBox::down-arrow {{ image: url({freccia}); width: 12px; height: 12px; }}"
            if freccia
            else ""
        ),
    )


def tema_effettivo(scelta: str, sistema_scuro: bool) -> str:
    """ "sistema" segue Windows; gli altri valori sono già un tema."""
    if scelta == "sistema":
        return "scuro" if sistema_scuro else "chiaro"
    return scelta if scelta in TEMI else "chiaro"


_attivo: dict[str, str] = dict(CHIARO)


def colore(nome: str) -> str:
    """Colore del tema attivo, per i widget disegnati a mano."""
    return _attivo[nome]


def sistema_scuro(app: QApplication) -> bool:
    return app.styleHints().colorScheme() == Qt.ColorScheme.Dark


def applica_tema(app: QApplication, scelta: str) -> str:
    """Applica il tema scelto (sistema, chiaro, scuro) e restituisce quello effettivo."""
    nome = tema_effettivo(scelta, sistema_scuro(app))
    colori = TEMI[nome]
    _attivo.clear()
    _attivo.update(colori)
    # Ogni cambio ridisegna tutti i widget: si cambia solo ciò che è diverso
    if app.style().name().lower() != "fusion":
        app.setStyle("Fusion")
    if app.font().pointSize() != CORPO_PUNTI:
        font = QFont(app.font())
        font.setPointSize(CORPO_PUNTI)
        app.setFont(font)
    palette = _palette(colori)
    if app.palette() != palette:
        app.setPalette(palette)
    qss = foglio_di_stile(colori, _freccia(colori["testo_2"]))
    if app.styleSheet() != qss:
        app.setStyleSheet(qss)
    return nome


def _freccia(colore: str) -> str:
    """La freccia dei menu a tendina come file SVG: il QSS accetta immagini solo da file."""
    cartella = Path(tempfile.gettempdir()) / "assenze-desk"
    cartella.mkdir(exist_ok=True)
    file = cartella / f"freccia-{colore.lstrip('#')}.svg"
    if not file.is_file():
        file.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{colore}" stroke-width="2.2" stroke-linecap="round" '
            'stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>',
            encoding="utf-8",
        )
    return file.as_posix()


def aggiorna_stile(widget: QWidget) -> None:
    """Da chiamare dopo aver cambiato una property usata dal foglio di stile."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _palette(colori: Mapping[str, str]) -> QPalette:
    palette = QPalette()
    ruoli = {
        QPalette.ColorRole.Window: "sfondo",
        QPalette.ColorRole.Base: "superficie",
        QPalette.ColorRole.AlternateBase: "superficie_2",
        QPalette.ColorRole.Button: "superficie",
        QPalette.ColorRole.WindowText: "testo",
        QPalette.ColorRole.Text: "testo",
        QPalette.ColorRole.ButtonText: "testo",
        QPalette.ColorRole.PlaceholderText: "testo_2",
        QPalette.ColorRole.Highlight: "accento",
        QPalette.ColorRole.HighlightedText: "accento_testo",
        QPalette.ColorRole.Link: "accento",
        QPalette.ColorRole.ToolTipBase: "superficie",
        QPalette.ColorRole.ToolTipText: "testo",
        QPalette.ColorRole.Mid: "bordo",
    }
    for ruolo, nome in ruoli.items():
        palette.setColor(ruolo, QColor(colori[nome]))
    for ruolo in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, ruolo, QColor(colori["testo_2"]))
    return palette
