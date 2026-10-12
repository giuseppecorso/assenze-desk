"""Componenti riusabili: schede, pulsanti, segmenti, interruttore, campi con
l'origine del dato, avvisi e barra dei messaggi.

L'aspetto viene dal foglio di stile del tema (gui/tema.py): qui si assegnano
solo i ruoli. Il campo (`CampoDato`) mostra lo stato di un `Campo` del core:
valore, origine, avviso, valore automatico da ripristinare, scelte rapide.
"""

from collections.abc import Callable, Sequence
from datetime import date

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from assenze_desk.core import formati
from assenze_desk.core.campi import Campo, Origine
from assenze_desk.core.date import leggi_data
from assenze_desk.gui import icone, tema
from assenze_desk.gui.calendario import aggiungi_calendario

S1, S2, S3, S4, S5 = tema.SPAZIO


def pulsante(
    testo: str, icona: str = "", variante: str = "", suggerimento: str = ""
) -> QPushButton:
    bottone = QPushButton(testo)
    if variante:
        bottone.setProperty("variante", variante)
    if icona:
        ruolo = {"primario": "accento_testo", "piatto": "accento"}.get(variante, "testo")
        icone.metti(bottone, icona, ruolo)
    if suggerimento:
        bottone.setToolTip(suggerimento)
    bottone.setCursor(Qt.CursorShape.PointingHandCursor)
    return bottone


def mostra_portale(bottone: QPushButton, portale) -> None:
    """Il pulsante del portale aziendale ha il nome scelto e compare solo con un indirizzo."""
    bottone.setText(portale.nome)
    bottone.setToolTip(f"Apre {portale.indirizzo}" if portale.attivo else "")
    bottone.setHidden(not portale.attivo)


def etichetta(testo: str = "", ruolo: str = "", a_capo: bool = False) -> QLabel:
    label = QLabel(testo)
    if ruolo:
        label.setProperty("ruolo", ruolo)
    label.setWordWrap(a_capo)
    return label


def separatore() -> QFrame:
    linea = QFrame()
    linea.setProperty("ruolo", "separatore")
    linea.setFixedHeight(1)
    return linea


def badge(testo: str) -> QLabel:
    label = QLabel(testo)
    label.setProperty("badge", testo)
    return label


def imposta_badge(label: QLabel, testo: str) -> None:
    label.setText(testo)
    label.setProperty("badge", testo)
    tema.aggiorna_stile(label)


def riga(*widget: QWidget, spazio: int = S2, allunga: bool = True) -> QHBoxLayout:
    """Widget in fila; `None` diventa uno spazio che spinge a destra quelli dopo."""
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spazio)
    for elemento in widget:
        if elemento is None:
            layout.addStretch(1)
        else:
            layout.addWidget(elemento)
    if allunga and None not in widget:
        layout.addStretch(1)
    return layout


class Scheda(QFrame):
    """Riquadro con titolo facoltativo; i contenuti vanno in `corpo`."""

    def __init__(self, titolo: str = "", icona: str = "") -> None:
        super().__init__()
        self.setProperty("ruolo", "scheda")
        self.corpo = QVBoxLayout(self)
        self.corpo.setContentsMargins(S4, S4, S4, S4)
        self.corpo.setSpacing(S3)
        self._destra = QHBoxLayout()
        if titolo:
            testata = QHBoxLayout()
            testata.setSpacing(S2)
            if icona:
                testata.addWidget(icone.etichetta(icona))
            self.titolo = etichetta(titolo, "titolo-scheda")
            testata.addWidget(self.titolo)
            testata.addStretch(1)
            testata.addLayout(self._destra)
            self.corpo.addLayout(testata)

    def aggiungi_a_destra(self, widget: QWidget) -> None:
        self._destra.addWidget(widget)


class Segmenti(QFrame):
    """Scelta tra poche voci affiancate (per esempio Malattia | Giustificativo)."""

    cambiato = Signal(int)

    def __init__(self, voci: Sequence[str]) -> None:
        super().__init__()
        self.setProperty("ruolo", "segmenti")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self._gruppo = QButtonGroup(self)
        self._gruppo.setExclusive(True)
        for numero, voce in enumerate(voci):
            bottone = QPushButton(voce)
            bottone.setProperty("ruolo", "segmento")
            bottone.setCheckable(True)
            bottone.setCursor(Qt.CursorShape.PointingHandCursor)
            self._gruppo.addButton(bottone, numero)
            layout.addWidget(bottone)
        self._gruppo.button(0).setChecked(True)
        self._gruppo.idClicked.connect(self.cambiato.emit)

    def indice(self) -> int:
        return self._gruppo.checkedId()

    def seleziona(self, indice: int) -> None:
        """Cambia la voce senza emettere `cambiato` (lo emette solo il clic dell'utente)."""
        self._gruppo.button(indice).setChecked(True)

    def pulsante(self, indice: int) -> QAbstractButton:
        return self._gruppo.button(indice)


class Interruttore(QAbstractButton):
    """Interruttore acceso/spento con il testo accanto."""

    LARGHEZZA, ALTEZZA = 34, 20

    def __init__(self, testo: str = "") -> None:
        super().__init__()
        self.setText(testo)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        metrica = self.fontMetrics()
        return QSize(
            self.LARGHEZZA + S2 + metrica.horizontalAdvance(self.text()) + S1,
            max(self.ALTEZZA, metrica.height()) + 2,
        )

    def paintEvent(self, _evento) -> None:
        pittore = QPainter(self)
        pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
        alto = (self.height() - self.ALTEZZA) / 2
        binario = QRectF(0, alto, self.LARGHEZZA, self.ALTEZZA)
        pittore.setPen(Qt.PenStyle.NoPen)
        pittore.setBrush(QColor(tema.colore("accento" if self.isChecked() else "bordo")))
        pittore.drawRoundedRect(binario, self.ALTEZZA / 2, self.ALTEZZA / 2)
        pittore.setBrush(QColor("#ffffff"))
        sinistra = binario.x() + (self.LARGHEZZA - 18 if self.isChecked() else 2)
        pittore.drawEllipse(QRectF(sinistra, alto + 2, 16, 16))
        pittore.setPen(QColor(tema.colore("testo" if self.isEnabled() else "testo_2")))
        area = QRectF(self.LARGHEZZA + S2, 0, self.width() - self.LARGHEZZA - S2, self.height())
        pittore.drawText(
            area, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text()
        )
        pittore.end()


class EtichettaOrigine(QLabel):
    """ "Testo", "PDF", "Anagrafica", "Manuale" o "Archivio", con i colori dell'origine."""

    def __init__(self) -> None:
        super().__init__()
        self.hide()

    def mostra(self, origine: Origine | None, dettaglio: str = "") -> None:
        if origine is None:
            self.hide()
            return
        self.setText(f"{origine} · {dettaglio}" if dettaglio else str(origine))
        self.setProperty("origine", str(origine))
        tema.aggiorna_stile(self)
        self.show()


class Avviso(QFrame):
    """Riquadro colorato con un messaggio: attenzione, ok, info o errore."""

    def __init__(self, tipo: str = "info", testo: str = "", icona: str = "avviso") -> None:
        super().__init__()
        self.setProperty("avviso", tipo)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(S3, S2, S3, S2)
        layout.setSpacing(S2)
        self._icona = icone.etichetta(icona, "testo_2")
        self._icona.setProperty("ruolo", "icona-avviso")
        layout.addWidget(self._icona, 0, Qt.AlignmentFlag.AlignTop)
        self.testo = etichetta(testo, "testo-avviso", a_capo=True)
        layout.addWidget(self.testo, 1)
        self.extra = QHBoxLayout()
        layout.addLayout(self.extra)

    def mostra(self, testo: str, tipo: str | None = None) -> None:
        self.testo.setText(testo)
        if tipo:
            self.setProperty("avviso", tipo)
            tema.aggiorna_stile(self)
        self.setVisible(bool(testo))


class BarraMessaggi(Avviso):
    """Messaggi delle schermate in cima alla finestra: niente finestre che si aprono da sole.

    Informazioni e conferme spariscono da sole; avvisi ed errori restano finché
    non si chiudono o arriva un altro messaggio.
    """

    DURATA_MS = 8000

    def __init__(self) -> None:
        super().__init__("info", icona="avviso")
        self._azione = pulsante("", variante="piatto")
        self._azione.hide()
        self._funzione: Callable[[], object] | None = None
        self._azione.clicked.connect(self._esegui)
        chiudi = pulsante("", "chiudi", "piatto", "Chiudi il messaggio")
        chiudi.clicked.connect(self.hide)
        self.extra.addWidget(self._azione)
        self.extra.addWidget(chiudi)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def mostra(
        self, testo: str, tipo: str = "info", azione: tuple[str, Callable[[], object]] | None = None
    ) -> None:
        super().mostra(testo, tipo)
        self._funzione = azione[1] if azione else None
        self._azione.setText(azione[0] if azione else "")
        self._azione.setVisible(azione is not None)
        if tipo in ("info", "ok"):
            self._timer.start(self.DURATA_MS)
        else:
            self._timer.stop()

    def _esegui(self) -> None:
        if self._funzione is not None:
            self._funzione()


class CampoDato(QWidget):
    """Un campo della pratica: etichetta con l'origine, casella, avviso, ripristino.

    Tipi: "testo", "data" (gg/mm/aaaa), "ore" ("1:30"), "giorni" (date separate
    da virgole), "scelta" (elenco). Date e giorni hanno il mini calendario. Il
    valore scritto dall'utente arriva con `modificato`; ciò che si mostra arriva
    sempre dal core con `mostra`.
    """

    modificato = Signal(str, object)
    ripristino = Signal(str)
    scritto_a_mano = Signal(str, object)  # testo finito di scrivere (Invio o uscita)

    def __init__(
        self,
        nome: str,
        titolo: str,
        tipo: str = "testo",
        scelte: Sequence[str] = (),
        mono: bool = False,
        segnaposto: str = "",
        riferimento: Callable[[], date] = date.today,
        oggi: Callable[[], date] = date.today,
        al_termine: Callable[[str], str] | None = None,
    ) -> None:
        super().__init__()
        self.nome, self.tipo = nome, tipo
        self._al_termine = al_termine  # pulizia del testo quando si finisce di scrivere
        self._scritto = False
        self._riferimento = riferimento
        self._errore_locale = ""
        self._scelte_rapide: tuple = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S1)

        self.titolo = etichetta(titolo, "secondario")
        self.origine = EtichettaOrigine()
        layout.addLayout(riga(self.titolo, self.origine))

        if tipo == "scelta":
            self.editor: QLineEdit | QComboBox = QComboBox()
            self.imposta_scelte(scelte)
            self.editor.activated.connect(self._scelta_utente)
        else:
            casella = QLineEdit()
            casella.setPlaceholderText(segnaposto)
            casella.setProperty("mono", mono)
            if tipo == "testo":
                casella.textEdited.connect(self._testo_utente)
                casella.textEdited.connect(lambda _testo: setattr(self, "_scritto", True))
                casella.editingFinished.connect(self._fine_scrittura)
            else:
                # Date e ore valgono con Invio o uscendo dalla casella: mentre si
                # scrive "12/10/20" non compaiono avvisi su una data a metà
                casella.editingFinished.connect(lambda: self._testo_utente(casella.text()))
            if tipo in ("data", "giorni"):
                aggiungi_calendario(
                    casella,
                    self._giorni_scritti,
                    oggi,
                    self._dal_calendario,
                    multipli=tipo == "giorni",
                )
            self.editor = casella
        layout.addWidget(self.editor)

        self.rapide = QHBoxLayout()
        self.rapide.setSpacing(S1)
        self._riquadro_rapide = QWidget()
        self._riquadro_rapide.setLayout(self.rapide)
        self._riquadro_rapide.hide()
        layout.addWidget(self._riquadro_rapide)

        self.avviso = etichetta("", "avviso-campo", a_capo=True)
        self.avviso.hide()
        layout.addWidget(self.avviso)

        self.automatico = etichetta("", "secondario")
        self.bottone_ripristina = pulsante("Ripristina", "ripristina", "piatto")
        self.bottone_ripristina.clicked.connect(lambda: self.ripristino.emit(self.nome))
        self._riga_automatico = QWidget()
        self._riga_automatico.setLayout(riga(self.automatico, self.bottone_ripristina, spazio=S1))
        self._riga_automatico.hide()
        layout.addWidget(self._riga_automatico)

    # --- Conversioni ---

    def valore_da_testo(self, testo: str) -> object:
        testo = testo.strip()
        if not testo:
            return None
        if self.tipo == "data":
            return leggi_data(testo, self._riferimento())
        if self.tipo == "ore":
            return formati.leggi_ore(testo)
        if self.tipo == "giorni":
            return formati.leggi_giorni(testo, self._riferimento())
        return testo

    def testo_da_valore(self, valore: object) -> str:
        if valore is None:
            return ""
        if self.tipo == "data" and isinstance(valore, date):
            return formati.data(valore)
        if self.tipo == "ore" and isinstance(valore, int):
            return formati.ore(valore)
        if self.tipo == "giorni" and isinstance(valore, tuple):
            return ", ".join(formati.data(giorno) for giorno in valore)
        return str(valore)

    # --- Dall'utente ---

    def _fine_scrittura(self) -> None:
        """Testo scritto a mano e finito: la pulizia (se c'è) si fa qui, non a ogni
        tasto, così mentre si scrive il cursore non salta."""
        if not self._scritto:
            return
        self._scritto = False
        editor = self.editor
        testo = editor.text()
        pulito = self._al_termine(testo) if self._al_termine else testo
        if pulito != testo:
            editor.setText(pulito)
            self._testo_utente(pulito)
        self.scritto_a_mano.emit(self.nome, self.valore_da_testo(pulito))

    def _testo_utente(self, testo: str) -> None:
        valore = self.valore_da_testo(testo)
        self._errore_locale = ""
        if testo.strip() and valore is None:
            self._errore_locale = {
                "data": "Data non valida: scrivi gg/mm/aaaa o scegli dal calendario.",
                "ore": "Ore non valide: scrivi per esempio 8 oppure 1:30.",
                "giorni": "Giorni non validi: scrivi le date separate da virgole "
                "o sceglile dal calendario.",
            }.get(self.tipo, "")
        self.modificato.emit(self.nome, valore)

    def _giorni_scritti(self) -> tuple[date, ...]:
        """Le date già nella casella, da cui parte il calendario."""
        editor = self.editor
        valore = self.valore_da_testo(editor.text()) if isinstance(editor, QLineEdit) else None
        if isinstance(valore, date):
            return (valore,)
        return valore if isinstance(valore, tuple) else ()

    def _dal_calendario(self, giorni: tuple[date, ...]) -> None:
        editor = self.editor
        if not isinstance(editor, QLineEdit):
            return
        valore = giorni[0] if self.tipo == "data" and giorni else giorni or None
        editor.setText(self.testo_da_valore(valore))
        self._testo_utente(editor.text())

    def _scelta_utente(self, indice: int) -> None:
        self.modificato.emit(self.nome, self.editor.itemData(indice))

    def imposta_scelte(self, scelte: Sequence[str]) -> None:
        editor = self.editor
        if not isinstance(editor, QComboBox):
            return
        attuale = editor.currentData()
        editor.clear()
        editor.addItem("— scegli —", None)
        for scelta in scelte:
            editor.addItem(scelta, scelta)
        posizione = editor.findData(attuale)
        editor.setCurrentIndex(max(posizione, 0))

    # --- Dal core ---

    def mostra(self, campo: Campo, dettaglio_origine: str = "") -> None:
        editor = self.editor
        if isinstance(editor, QComboBox):
            posizione = editor.findData(campo.valore) if campo.valore is not None else 0
            editor.setCurrentIndex(max(posizione, 0))
        elif self._da_riscrivere(campo):
            editor.setText(self.testo_da_valore(campo.valore))
            self._errore_locale = ""

        self.origine.mostra(campo.origine, dettaglio_origine)
        messaggio = self._errore_locale or campo.avviso
        self.avviso.setText(messaggio)
        self.avviso.setVisible(bool(messaggio))
        if bool(editor.property("incerto")) != bool(messaggio):
            editor.setProperty("incerto", bool(messaggio))
            tema.aggiorna_stile(editor)

        if campo.automatico_diverso:
            self.automatico.setText(f"Automatico: {self.testo_da_valore(campo.proposta.valore)}")
        self._riga_automatico.setVisible(campo.automatico_diverso)
        self._mostra_rapide(campo.scelte if campo.valore is None else ())

    def _da_riscrivere(self, campo: Campo) -> bool:
        """Il testo scritto a mano resta com'è (anche "12/10" o una data sbagliata,
        con il suo avviso) finché il core non porta un valore diverso; negli altri
        casi la casella mostra il valore del core."""
        editor = self.editor
        if not isinstance(editor, QLineEdit):
            return False
        if campo.manuale or self._errore_locale:
            return self.valore_da_testo(editor.text()) != campo.valore
        return editor.text() != self.testo_da_valore(campo.valore)

    def pulisci(self) -> None:
        """Pratica nuova: via anche il testo non valido scritto a mano."""
        self._errore_locale = ""
        if isinstance(self.editor, QLineEdit):
            self.editor.clear()

    def _mostra_rapide(self, scelte: tuple) -> None:
        if scelte == self._scelte_rapide:
            return
        self._scelte_rapide = scelte
        while self.rapide.count():
            elemento = self.rapide.takeAt(0)
            if elemento.widget():
                elemento.widget().deleteLater()
        if scelte:
            self.rapide.addWidget(etichetta("Trovati:", "secondario"))
            for scelta in scelte:
                bottone = pulsante(str(scelta))
                bottone.clicked.connect(
                    lambda _=False, s=scelta: self.modificato.emit(self.nome, s)
                )
                self.rapide.addWidget(bottone)
            self.rapide.addStretch(1)
        self._riquadro_rapide.setVisible(bool(scelte))
