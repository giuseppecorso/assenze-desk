"""Icone dell'app: tratti SVG semplici disegnati per questo progetto (come nel mockup).

Il colore viene dal tema attivo. Un pulsante con icona ha la property "icona"
(e facoltativamente "icona_ruolo"): al cambio di tema `ricolora` la ridisegna.
"""

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

from assenze_desk.gui import tema

TRATTI = {
    "nuova": '<path d="M6 3h8l4 4v14H6z"/><path d="M12 10v7M8.5 13.5h7"/>',
    "archivio": (
        '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10h14V9M10 13h4"/>'
    ),
    "statistiche": '<path d="M5 20V11M12 20V5M19 20v-7"/>',
    "impostazioni": (
        '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1'
        'M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>'
    ),
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "incolla": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9z"/>',
    "selezione": '<path d="M9 4h6M9 20h6M12 4v16"/>',
    "ocr": (
        '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3'
        'M8 20H5a1 1 0 0 1-1-1v-3M8 12h8"/>'
    ),
    "analizza": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "cerca": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    "ripristina": '<path d="M4 9h11a5 5 0 0 1 0 10H9M4 9l4-4M4 9l4 4"/>',
    "avviso": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17v.5"/>',
    "file": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
    "copia": (
        '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V5a1 1 0 0 1 1-1h11"/>'
    ),
    "esterno": (
        '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>'
    ),
    "scarica": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    "cartella": (
        '<path d="M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>'
    ),
    "salva": '<path d="M5 12l5 5 9-10"/>',
    "log": '<path d="M4 6h16M4 12h16M4 18h10"/>',
    "persona": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "calendario": (
        '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>'
    ),
    "sposta": (
        '<path d="M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>'
        '<path d="M10 13h6M13 10l3 3-3 3"/>'
    ),
    "chiudi": '<path d="M6 6l12 12M18 6L6 18"/>',
    "elimina": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
}
LATO = 16


def pixmap(nome: str, colore: str, lato: int = LATO, scala: float = 2.0) -> QPixmap:
    """L'icona come immagine, disegnata al doppio della risoluzione per gli schermi nitidi."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{colore}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f"{TRATTI[nome]}</svg>"
    )
    immagine = QPixmap(QSize(round(lato * scala), round(lato * scala)))
    immagine.fill(Qt.GlobalColor.transparent)
    pittore = QPainter(immagine)
    QSvgRenderer(QByteArray(svg.encode())).render(pittore, QRectF(immagine.rect()))
    pittore.end()
    immagine.setDevicePixelRatio(scala)
    return immagine


def icona(nome: str, ruolo: str = "testo", ruolo_attivo: str | None = None) -> QIcon:
    """Icona nei colori del tema attivo; `ruolo_attivo` per lo stato selezionato."""
    risultato = QIcon()
    risultato.addPixmap(pixmap(nome, tema.colore(ruolo)), QIcon.Mode.Normal, QIcon.State.Off)
    risultato.addPixmap(pixmap(nome, tema.colore("testo_2")), QIcon.Mode.Disabled, QIcon.State.Off)
    if ruolo_attivo:
        attivo = pixmap(nome, tema.colore(ruolo_attivo))
        risultato.addPixmap(attivo, QIcon.Mode.Normal, QIcon.State.On)
    return risultato


def metti(widget: QAbstractButton, nome: str, ruolo: str = "testo", ruolo_attivo: str = "") -> None:
    """Assegna l'icona e la ricorda per il prossimo cambio di tema."""
    widget.setProperty("icona", nome)
    widget.setProperty("icona_ruolo", ruolo)
    widget.setProperty("icona_ruolo_attivo", ruolo_attivo)
    widget.setIcon(icona(nome, ruolo, ruolo_attivo or None))
    widget.setIconSize(QSize(LATO, LATO))


def etichetta(nome: str, ruolo: str = "testo_2") -> QLabel:
    """Un'icona da sola, per esempio accanto al titolo di una scheda."""
    label = QLabel()
    label.setProperty("icona", nome)
    label.setProperty("icona_ruolo", ruolo)
    label.setPixmap(pixmap(nome, tema.colore(ruolo)))
    return label


def ricolora(radice: QWidget) -> None:
    """Ridisegna tutte le icone sotto `radice` con i colori del tema attivo."""
    for widget in [radice, *radice.findChildren(QWidget)]:
        nome = widget.property("icona")
        if not nome:
            continue
        ruolo = widget.property("icona_ruolo") or "testo"
        if isinstance(widget, QAbstractButton):
            attivo = widget.property("icona_ruolo_attivo") or None
            widget.setIcon(icona(nome, ruolo, attivo))
        elif isinstance(widget, QLabel):
            widget.setPixmap(pixmap(nome, tema.colore(ruolo)))
