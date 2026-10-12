"""Schermata Nuova pratica: a sinistra la mail, a destra dati e azioni del flusso.

Malattia o Giustificativo si sceglie con l'interruttore in alto, mai con una
finestra. Il testo arriva da Outlook, dagli appunti, dal testo selezionato in
un'altra finestra o dall'OCR; l'analisi parte solo quando lo decide l'utente
(Analizza, Ctrl+Invio, import, incolla) e non cambia mai schermata.
"""

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from assenze_desk.adapters.ocr import ErroreOcr, leggi_testo_immagine, trova_tesseract
from assenze_desk.adapters.testo_selezionato import premi_ctrl_c, testo_nuovo
from assenze_desk.core.analisi import intestazioni_mail
from assenze_desk.gui.cattura import SelezioneZona, in_pillow
from assenze_desk.gui.componenti import (
    BarraMessaggi,
    Segmenti,
    badge,
    etichetta,
    imposta_badge,
    pulsante,
)
from assenze_desk.gui.errori import esegui
from assenze_desk.gui.pannello_mail import PannelloMail
from assenze_desk.gui.pratica_giustificativo import PraticaGiustificativo
from assenze_desk.gui.pratica_malattia import InfoMail, PraticaMalattia
from assenze_desk.servizi import Contesto
from assenze_desk.storage.archivio import Pratica

log = logging.getLogger(__name__)

FLUSSI = ("malattia", "giustificativo")
ATTESA_SELEZIONE_MS = 2000  # tempo per tornare all'altra finestra prima del Ctrl+C
ATTESA_CATTURA_MS = 350  # tempo perché la finestra sparisca dalla cattura


class NuovaPratica(QWidget):
    archivio_cambiato = Signal()

    def __init__(self, contesto: Contesto, messaggi: BarraMessaggi) -> None:
        super().__init__()
        self.contesto, self.messaggi = contesto, messaggi
        self.info = InfoMail()
        self.analisi_eseguite = 0
        self._appunti_prima = ""
        self._selezione_zona: SelezioneZona | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 12)
        layout.setSpacing(12)
        self.segmenti = Segmenti(["Malattia", "Giustificativo"])
        self.stato = badge("Incompleta")
        self.vuota = pulsante("Nuova pratica vuota", "nuova", "piatto")
        intestazione = QHBoxLayout()
        intestazione.setSpacing(12)
        intestazione.addWidget(etichetta("Nuova pratica", "titolo"))
        intestazione.addWidget(self.segmenti)
        intestazione.addStretch(1)
        intestazione.addWidget(self.stato)
        intestazione.addWidget(self.vuota)
        layout.addLayout(intestazione)

        corpo = QHBoxLayout()
        corpo.setSpacing(12)
        self.mail = PannelloMail()
        corpo.addWidget(self.mail, 5)
        self.malattia = PraticaMalattia(contesto, messaggi)
        self.giustificativo = PraticaGiustificativo(contesto, messaggi)
        self.flussi = QStackedWidget()
        self.flussi.addWidget(self.malattia)
        self.flussi.addWidget(self.giustificativo)
        scorrimento = QScrollArea()
        scorrimento.setWidgetResizable(True)
        scorrimento.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scorrimento.setFrameShape(QScrollArea.Shape.NoFrame)
        scorrimento.setWidget(self.flussi)
        corpo.addWidget(scorrimento, 6)
        layout.addLayout(corpo, 1)

        self.segmenti.cambiato.connect(self._cambia_flusso)
        self.vuota.clicked.connect(self.nuova_vuota)
        self.mail.analisi_richiesta.connect(self.analizza)
        self.mail.testo_nuovo.connect(self._testo_nuovo)
        self.mail.importa_richiesto.connect(self._importa)
        self.mail.selezione_richiesta.connect(self._testo_selezionato)
        self.mail.ocr_richiesto.connect(self._ocr)
        self.mail.pdf_richiesto.connect(self._apri_pdf)
        self.malattia.stato_cambiato.connect(lambda stato: imposta_badge(self.stato, stato))
        self.malattia.pdf_cambiato.connect(self.mail.mostra_pdf)
        self.malattia.rianalisi_richiesta.connect(self.analizza)
        self.malattia.salvata.connect(self.archivio_cambiato)
        self.giustificativo.salvata.connect(self.archivio_cambiato)
        self.mail.importa.setEnabled(contesto.outlook_disponibile)
        self._cambia_flusso(0)
        imposta_badge(self.stato, "Incompleta")

    def flusso(self) -> str:
        return FLUSSI[self.flussi.currentIndex()]

    # --- Analisi ---

    def analizza(self) -> None:
        testo = self.mail.testo()
        if not testo.strip():
            self.messaggi.mostra("Prima inserisci il testo della mail.", "attenzione")
            return
        if self.info.mail is None:
            self.info.mittente, self.info.ricevuta = intestazioni_mail(testo)
        if self.info.iniziata is None:
            self.info.iniziata = self.contesto.adesso()
        pannello = self.malattia if self.flusso() == "malattia" else self.giustificativo
        pannello.analizza(testo, self.info)
        self.analisi_eseguite += 1
        log.info("Analisi della mail (%s)", self.flusso())

    def _testo_nuovo(self) -> None:
        """Testo incollato o arrivato da selezione e OCR: non è più la mail importata."""
        self.info = InfoMail(iniziata=self.contesto.adesso())

    # --- Da dove arriva il testo ---

    def _importa(self) -> None:
        mail = esegui(self.messaggi, lambda: self.contesto.importa_mail(self.flusso()))
        if mail is None:
            return
        self.info = InfoMail(mail, mail.mittente, mail.ricevuta, self.contesto.adesso())
        mittente = mail.mittente or "mittente sconosciuto"
        self.mail.imposta_testo(
            mail.testo,
            f"Da {mittente} · ricevuta {mail.ricevuta:%d/%m/%Y %H:%M} · importata da Outlook",
        )
        if self.flusso() == "malattia":
            self.malattia.svuota()
            for pdf in esegui(self.messaggi, lambda: self.contesto.allegati_pdf(mail)) or []:
                if self.malattia.carica_pdf(pdf):
                    break
        log.info("Mail importata da Outlook")
        self.analizza()

    def _incolla_da(self, testo: str, provenienza: str) -> None:
        self._testo_nuovo()
        self.mail.imposta_testo(testo, provenienza)
        self.analizza()

    def _testo_selezionato(self) -> None:
        if sys.platform != "win32":
            self.messaggi.mostra(
                "Il testo selezionato funziona solo su Windows: copia il testo e usa Incolla.",
                "attenzione",
            )
            return
        self._appunti_prima = QGuiApplication.clipboard().text()
        self.window().showMinimized()
        QTimer.singleShot(ATTESA_SELEZIONE_MS, self._copia_selezione)

    def _copia_selezione(self) -> None:  # pragma: no cover - tastiera vera, solo Windows
        premi_ctrl_c()
        QTimer.singleShot(300, self._leggi_selezione)

    def _leggi_selezione(self) -> None:
        self._riporta_finestra()
        testo = testo_nuovo(self._appunti_prima, QGuiApplication.clipboard().text())
        if testo is None:
            self.messaggi.mostra(
                "Nessun testo nuovo copiato: seleziona il testo nell'altra finestra e riprova "
                "senza cambiare finestra durante l'attesa. In alternativa copialo e usa Incolla.",
                "attenzione",
            )
            return
        self._incolla_da(testo, "Testo selezionato in un'altra finestra")

    def _ocr(self) -> None:
        tesseract = trova_tesseract(self.contesto.impostazioni.ocr.tesseract)
        if tesseract is None:
            self.messaggi.mostra(
                "Tesseract OCR non trovato: installalo oppure indica dove si trova in "
                "Impostazioni > OCR e portali.",
                "errore",
            )
            return
        self.window().hide()
        QTimer.singleShot(ATTESA_CATTURA_MS, lambda: self._cattura(tesseract))

    def _cattura(self, tesseract: Path) -> None:
        schermo = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        self._selezione_zona = SelezioneZona(schermo.grabWindow(0), schermo.geometry())
        self._selezione_zona.scelta.connect(lambda zona: self._leggi_zona(zona, tesseract))
        self._selezione_zona.annullata.connect(self._riporta_finestra)
        self._selezione_zona.show()
        self._selezione_zona.activateWindow()

    def _leggi_zona(self, zona, tesseract: Path) -> None:
        self._riporta_finestra()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            testo = leggi_testo_immagine(
                in_pillow(zona), tesseract, self.contesto.impostazioni.ocr.parole_rumore
            )
        except ErroreOcr as errore:
            log.warning("OCR non riuscito: %s", errore)
            self.messaggi.mostra(str(errore), "errore")
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._incolla_da(testo, "Letta con l'OCR: controlla il testo prima di salvare")

    def _riporta_finestra(self) -> None:
        finestra = self.window()
        finestra.showNormal()
        finestra.raise_()
        finestra.activateWindow()

    def _apri_pdf(self) -> None:
        percorso, _filtro = QFileDialog.getOpenFileName(
            self, "Certificato di malattia", str(Path.home()), "PDF (*.pdf)"
        )
        if percorso:
            self.carica_pdf_scelto(Path(percorso))

    def carica_pdf_scelto(self, percorso: Path) -> None:
        copia = esegui(self.messaggi, lambda: self.contesto.prepara_pdf(percorso))
        if copia is not None and self.malattia.carica_pdf(copia):
            if self.mail.testo().strip():
                self.analizza()
            else:
                self.malattia.analizza("", self.info)

    # --- Flussi e pratiche ---

    def _cambia_flusso(self, indice: int) -> None:
        self.flussi.setCurrentIndex(indice)
        malattia = indice == 0
        self.stato.setVisible(malattia)
        self.mail.riga_pdf.setVisible(malattia)

    def mostra_flusso(self, flusso: str) -> None:
        indice = FLUSSI.index(flusso)
        self.segmenti.seleziona(indice)
        self._cambia_flusso(indice)

    def impostazioni_cambiate(self) -> None:
        self.mail.importa.setEnabled(self.contesto.outlook_disponibile)
        self.malattia.aggiorna()
        self.giustificativo.aggiorna()

    def nuova_vuota(self) -> None:
        self.info = InfoMail()
        self.mail.imposta_testo("")
        self.malattia.svuota()
        self.giustificativo.svuota()

    def carica_pratica(self, pratica: Pratica) -> None:
        """Pratica riaperta dall'Archivio: i dati salvati restano protetti."""
        self.mostra_flusso("malattia")
        self.info = InfoMail()
        self.mail.imposta_testo("", f"Pratica {pratica.protocollo} riaperta dall'archivio")
        self.malattia.carica_pratica(pratica)
