"""Sezione Archivio: pratiche di malattia e righe dei giustificativi, con filtri.

Si cerca su dipendente, CF, protocollo e cliente, si filtra per stato e
periodo. Da qui si riapre una pratica, si cambia lo stato a mano, si vede lo
storico, si esporta in Excel ciò che i filtri mostrano; per i giustificativi
si correggono le ore e si eliminano righe (con conferma).
"""

import logging
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from assenze_desk.core import formati
from assenze_desk.core.date import leggi_data
from assenze_desk.core.stato import Stato
from assenze_desk.core.testo import normalizza
from assenze_desk.gui import icone, tema
from assenze_desk.gui.calendario import aggiungi_calendario
from assenze_desk.gui.componenti import (
    BarraMessaggi,
    Scheda,
    Segmenti,
    etichetta,
    pulsante,
    riga,
)
from assenze_desk.gui.errori import esegui
from assenze_desk.servizi import Contesto
from assenze_desk.storage.archivio import Pratica, RigaSalvata

log = logging.getLogger(__name__)

STATO_AUTOMATICO = "Stato automatico"


def _cella(testo: str, dato: object = None) -> QTableWidgetItem:
    voce = QTableWidgetItem(testo)
    if dato is not None:
        voce.setData(Qt.ItemDataRole.UserRole, dato)
    return voce


def _tabella(intestazioni: Sequence[str]) -> QTableWidget:
    tabella = QTableWidget(0, len(intestazioni))
    tabella.setHorizontalHeaderLabels(list(intestazioni))
    tabella.verticalHeader().hide()
    tabella.setShowGrid(False)
    tabella.setAlternatingRowColors(True)
    tabella.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tabella.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    tabella.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    tabella.setSortingEnabled(True)
    return tabella


def _nel_periodo(giorno: date | None, dal: date | None, al: date | None) -> bool:
    if giorno is None:
        return dal is None and al is None
    return (dal is None or giorno >= dal) and (al is None or giorno <= al)


class Archivio(QWidget):
    apri_pratica = Signal(object)  # Pratica

    def __init__(
        self,
        contesto: Contesto,
        messaggi: BarraMessaggi,
        conferma: Callable[[str], bool] | None = None,
        chiedi_ore: Callable[[str], str | None] | None = None,
        scegli_file: Callable[[], list[Path]] | None = None,
    ) -> None:
        super().__init__()
        self.contesto, self.messaggi = contesto, messaggi
        # Finestre di dialogo aperte solo da un clic dell'utente; sostituibili nei test
        self._conferma = conferma or self._conferma_utente
        self._chiedi_ore = chiedi_ore or self._chiedi_ore_utente
        self._scegli_file = scegli_file or self._scegli_file_utente

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 12)
        layout.setSpacing(12)
        self.tipo = Segmenti(["Malattie", "Giustificativi"])
        self.esporta = pulsante("Esporta in Excel", "scarica")
        self.importa = pulsante(
            "Importa dalla versione precedente…",
            "cartella",
            "piatto",
            "Pratiche e giustificativi dai file Excel della vecchia versione",
        )
        self.conteggio = etichetta("", "secondario")
        layout.addLayout(
            riga(
                etichetta("Archivio", "titolo"),
                self.tipo,
                None,
                self.conteggio,
                self.importa,
                self.esporta,
            )
        )

        self.cerca = QLineEdit()
        self.cerca.setPlaceholderText("Cerca dipendente, CF, protocollo o cliente")
        icone.in_casella(self.cerca, "cerca", QLineEdit.ActionPosition.LeadingPosition)
        self.cerca.setMinimumWidth(300)
        self.stato = QComboBox()
        self.stato.addItem("Tutti gli stati", None)
        for stato in Stato:
            self.stato.addItem(str(stato), stato)
        self.dal, self.al = QLineEdit(), QLineEdit()
        for casella, testo in ((self.dal, "dal gg/mm/aaaa"), (self.al, "al gg/mm/aaaa")):
            casella.setPlaceholderText(testo)
            casella.setMaximumWidth(150)
            aggiungi_calendario(
                casella,
                lambda c=casella: [d] if (d := self._data(c)) else [],
                self._oggi,
                lambda giorni, c=casella: c.setText(formati.data(giorni[0])),
            )
            casella.textChanged.connect(lambda _testo, c=casella: self._segna_data(c))
        self.da_esportare = QCheckBox("Solo da esportare")
        layout.addLayout(riga(self.cerca, self.stato, self.dal, self.al, self.da_esportare))

        self.pagine = QStackedWidget()
        self.pagine.addWidget(self._pagina_malattie())
        self.pagine.addWidget(self._pagina_giustificativi())
        layout.addWidget(self.pagine, 1)

        self.tipo.cambiato.connect(self._cambia_tipo)
        self.esporta.clicked.connect(lambda: esegui(self.messaggi, self._esporta))
        self.importa.clicked.connect(lambda: esegui(self.messaggi, self._importa))
        for casella in (self.cerca, self.dal, self.al):
            casella.textChanged.connect(self.aggiorna)
        self.stato.currentIndexChanged.connect(self.aggiorna)
        self.da_esportare.toggled.connect(self.aggiorna)
        self._cambia_tipo(0)

    # --- Pagine ---

    def _pagina_malattie(self) -> QWidget:
        scheda = Scheda()
        self.pratiche = _tabella(
            ["Protocollo", "Dipendente", "Cliente", "Dal", "Al", "Giorni", "Stato", "Ricevuta"]
        )
        self.pratiche.itemDoubleClicked.connect(lambda _voce: self._apri())
        scheda.corpo.addWidget(self.pratiche, 1)
        self.apri = pulsante("Apri in Nuova pratica", "nuova")
        self.cambia_stato = QComboBox()
        self.cambia_stato.addItem("Cambia stato…", "")
        self.cambia_stato.addItem(STATO_AUTOMATICO, None)
        for stato in Stato:
            self.cambia_stato.addItem(str(stato), stato)
        self.mostra_storico = pulsante("Storico modifiche", "log")
        self.mostra_storico.setCheckable(True)
        self.elimina_pratiche = pulsante("Elimina", "elimina")
        scheda.corpo.addLayout(
            riga(
                self.apri,
                self.cambia_stato,
                self.mostra_storico,
                self.elimina_pratiche,
                None,
                etichetta("Doppio clic su una riga: Apri in Nuova pratica", "secondario"),
            )
        )
        self.storico = _tabella(["Quando", "Azione", "Protocollo", "Dettaglio"])
        self.storico.setSortingEnabled(False)
        self.storico.setMaximumHeight(180)
        self.storico.hide()
        scheda.corpo.addWidget(self.storico)
        self.apri.clicked.connect(self._apri)
        self.cambia_stato.activated.connect(
            lambda indice: esegui(self.messaggi, lambda: self._cambia_stato(indice))
        )
        self.mostra_storico.toggled.connect(self._mostra_storico)
        self.elimina_pratiche.clicked.connect(lambda: esegui(self.messaggi, self._elimina_pratiche))
        return scheda

    def _pagina_giustificativi(self) -> QWidget:
        scheda = Scheda()
        self.righe = _tabella(
            ["Giorno", "Dipendente", "Cliente", "Tipo", "Codice", "Ore", "Esportata"]
        )
        scheda.corpo.addWidget(self.righe, 1)
        self.modifica_ore = pulsante("Correggi le ore…", "calendario")
        self.elimina = pulsante("Elimina righe", "elimina")
        scheda.corpo.addLayout(riga(self.modifica_ore, self.elimina))
        self.modifica_ore.clicked.connect(lambda: esegui(self.messaggi, self._correggi_ore))
        self.elimina.clicked.connect(lambda: esegui(self.messaggi, self._elimina))
        return scheda

    # --- Filtri ---

    def _cambia_tipo(self, indice: int) -> None:
        self.pagine.setCurrentIndex(indice)
        self.stato.setVisible(indice == 0)
        self.da_esportare.setVisible(indice == 1)
        self.aggiorna()

    def _oggi(self) -> date:
        return self.contesto.adesso().date()

    def _data(self, casella: QLineEdit) -> date | None:
        return leggi_data(casella.text(), self._oggi())

    def _segna_data(self, casella: QLineEdit) -> None:
        """Una data del filtro che non si legge si evidenzia: il filtro non la usa."""
        sbagliata = bool(casella.text().strip()) and self._data(casella) is None
        casella.setToolTip(
            "Data non valida: scrivi gg/mm/aaaa o scegli dal calendario." if sbagliata else ""
        )
        if bool(casella.property("incerto")) != sbagliata:
            casella.setProperty("incerto", sbagliata)
            tema.aggiorna_stile(casella)

    def _periodo(self) -> tuple[date | None, date | None]:
        return self._data(self.dal), self._data(self.al)

    def _corrisponde(self, *campi: str) -> bool:
        parole = normalizza(self.cerca.text()).split()
        testo = normalizza(" ".join(campi))
        return all(parola in testo for parola in parole)

    def pratiche_filtrate(self) -> list[Pratica]:
        soglia = self.contesto.impostazioni.soglia_ufficio
        stato = self.stato.currentData()
        dal, al = self._periodo()
        return [
            p
            for p in reversed(self.contesto.archivio.pratiche())
            if (stato is None or p.stato_per(soglia) == stato)
            and _nel_periodo(p.inizio, dal, al)
            and self._corrisponde(p.dipendente, p.cf, p.protocollo, p.cliente)
        ]

    def righe_filtrate(self) -> list[RigaSalvata]:
        dal, al = self._periodo()
        return [
            r
            for r in self.contesto.archivio.righe(solo_da_esportare=self.da_esportare.isChecked())
            if _nel_periodo(r.giorno, dal, al)
            and self._corrisponde(r.dipendente, r.cf, r.cliente, r.tipo, r.codice)
        ]

    def aggiorna(self) -> None:
        if self.pagine.currentIndex() == 0:
            self._mostra_pratiche(self.pratiche_filtrate())
        else:
            self._mostra_righe(self.righe_filtrate())
        if self.mostra_storico.isChecked():
            self._mostra_storico(True)

    def _mostra_pratiche(self, pratiche: list[Pratica]) -> None:
        soglia = self.contesto.impostazioni.soglia_ufficio
        self.pratiche.setSortingEnabled(False)
        self.pratiche.setRowCount(len(pratiche))
        for numero, p in enumerate(pratiche):
            giorni = p.giorni_episodio or (
                (p.fine - p.inizio).days + 1 if p.inizio and p.fine else None
            )
            stato = p.stato_per(soglia)
            valori = [
                p.protocollo,
                p.dipendente,
                p.cliente,
                formati.data(p.inizio),
                formati.data(p.fine),
                str(giorni or ""),
                str(stato) + (" · a mano" if p.stato_manuale else ""),
                formati.data(p.data_presentazione),
            ]
            for colonna, testo in enumerate(valori):
                self.pratiche.setItem(numero, colonna, _cella(testo, p if colonna == 0 else None))
            cella_stato = self.pratiche.item(numero, 6)
            cella_stato.setForeground(QColor(tema.colore(tema.COLORI_STATO[str(stato)][0])))
            grassetto = QFont(cella_stato.font())
            grassetto.setBold(True)
            cella_stato.setFont(grassetto)
        self.pratiche.setSortingEnabled(True)
        self.conteggio.setText(f"{len(pratiche)} pratiche")

    def _mostra_righe(self, righe: list[RigaSalvata]) -> None:
        self.righe.setSortingEnabled(False)
        self.righe.setRowCount(len(righe))
        for numero, r in enumerate(righe):
            valori = [
                formati.data(r.giorno),
                r.dipendente,
                r.cliente,
                r.tipo,
                r.codice,
                formati.ore(r.minuti) or "da compilare",
                "sì" if r.esportata else "no",
            ]
            for colonna, testo in enumerate(valori):
                self.righe.setItem(numero, colonna, _cella(testo, r if colonna == 0 else None))
        self.righe.setSortingEnabled(True)
        self.conteggio.setText(f"{len(righe)} righe")

    # --- Malattie ---

    def _selezionate(self, tabella: QTableWidget) -> list:
        righe = sorted({indice.row() for indice in tabella.selectedIndexes()})
        return [tabella.item(numero, 0).data(Qt.ItemDataRole.UserRole) for numero in righe]

    def _apri(self) -> None:
        scelte = self._selezionate(self.pratiche)
        if not scelte:
            self.messaggi.mostra("Seleziona prima una pratica.", "attenzione")
            return
        self.apri_pratica.emit(scelte[0])

    def _cambia_stato(self, indice: int) -> None:
        if indice == 0:
            return
        self.cambia_stato.setCurrentIndex(0)
        scelte = self._selezionate(self.pratiche)
        if not scelte:
            self.messaggi.mostra("Seleziona prima una o più pratiche.", "attenzione")
            return
        # Qt restituisce lo stato come testo: si riconverte (vuoto = stato automatico)
        valore = self.cambia_stato.itemData(indice)
        stato = Stato(valore) if valore else None
        for pratica in scelte:
            self.contesto.archivio.aggiorna(pratica.protocollo, stato_manuale=stato)
            self.contesto.archivio.registra(
                "Stato cambiato a mano", pratica.protocollo, str(stato or STATO_AUTOMATICO)
            )
        self.aggiorna()
        self.messaggi.mostra(f"Stato aggiornato per {len(scelte)} pratiche.", "ok")

    def _mostra_storico(self, aperto: bool) -> None:
        self.storico.setVisible(aperto)
        if not aperto:
            return
        azioni = self.contesto.archivio.storico()
        self.storico.setRowCount(len(azioni))
        for numero, azione in enumerate(azioni):
            for colonna, testo in enumerate(
                (
                    f"{azione.quando:%d/%m/%Y %H:%M}",
                    azione.azione,
                    azione.protocollo,
                    azione.dettaglio,
                )
            ):
                self.storico.setItem(numero, colonna, _cella(testo))

    # --- Giustificativi ---

    def _correggi_ore(self) -> None:
        scelte = self._selezionate(self.righe)
        if not scelte:
            self.messaggi.mostra("Seleziona prima una o più righe.", "attenzione")
            return
        scritto = self._chiedi_ore(formati.ore(scelte[0].minuti))
        if scritto is None:
            return
        minuti = formati.leggi_ore(scritto)
        if minuti is None:
            self.messaggi.mostra("Ore non valide: scrivi per esempio 8 oppure 1:30.", "errore")
            return
        for riga_ in scelte:
            self.contesto.archivio.modifica_riga(riga_.id, minuti=minuti)
        self.aggiorna()
        self.messaggi.mostra(f"Ore corrette in {len(scelte)} righe.", "ok")

    def _elimina_pratiche(self) -> None:
        scelte = self._selezionate(self.pratiche)
        if not scelte:
            self.messaggi.mostra("Seleziona prima una o più pratiche.", "attenzione")
            return
        domanda = (
            f"Eliminare {len(scelte)} pratiche dall'archivio? L'operazione non si annulla. "
            "I PDF dei certificati restano nella loro cartella."
        )
        if not self._conferma(domanda):
            return
        self.contesto.archivio.elimina_pratiche([p.protocollo for p in scelte])
        for pratica in scelte:
            self.contesto.archivio.registra("Pratica eliminata", pratica.protocollo)
        self.aggiorna()
        self.messaggi.mostra(f"Eliminate {len(scelte)} pratiche.", "ok")

    def _elimina(self) -> None:
        scelte = self._selezionate(self.righe)
        if not scelte:
            self.messaggi.mostra("Seleziona prima una o più righe.", "attenzione")
            return
        if not self._conferma(f"Eliminare {len(scelte)} righe? L'operazione non si annulla."):
            return
        self.contesto.archivio.elimina_righe([r.id for r in scelte])
        self.contesto.archivio.registra("Righe eliminate", "", f"{len(scelte)} righe")
        self.aggiorna()
        self.messaggi.mostra(f"Eliminate {len(scelte)} righe.", "ok")

    # --- Export ---

    def _esporta(self) -> None:
        if self.pagine.currentIndex() == 0:
            elementi = self.pratiche_filtrate()
            esporta = self.contesto.esporta_pratiche
        else:
            elementi = self.righe_filtrate()
            esporta = self.contesto.esporta_righe
        if not elementi:
            self.messaggi.mostra("Niente da esportare con i filtri attuali.", "attenzione")
            return
        file = esporta(elementi)
        self.aggiorna()
        url = QUrl.fromLocalFile(str(file.parent))
        self.messaggi.mostra(
            f"Esportate {len(elementi)} righe in {file.name}.",
            "ok",
            ("Apri la cartella", lambda: QDesktopServices.openUrl(url)),
        )

    # --- Import dalla versione precedente ---

    def _importa(self) -> None:
        file = self._scegli_file()
        if not file:
            return
        esiti, scartate = [], 0
        for percorso in file:
            dati, esito = self.contesto.importa_v620(percorso)
            cosa = "pratiche" if dati.tipo == "malattie" else "righe di giustificativi"
            esiti.append(f"{esito.nuove} {cosa} nuove, {esito.gia_presenti} già presenti")
            for avviso in dati.avvisi:
                log.warning("Import da %s: %s", percorso.name, avviso)
            scartate += len(dati.avvisi)
        self.aggiorna()
        testo = f"Import completato: {'; '.join(esiti)}."
        if scartate:
            testo += f" {scartate} righe non importate: i motivi sono nel log."
        self.messaggi.mostra(testo, "attenzione" if scartate else "ok")

    # --- Dialoghi aperti solo da un clic ---

    def _conferma_utente(self, domanda: str) -> bool:
        risposta = QMessageBox.question(self, "Archivio", domanda)
        return risposta == QMessageBox.StandardButton.Yes

    def _scegli_file_utente(self) -> list[Path]:
        file, _filtro = QFileDialog.getOpenFileNames(
            self,
            "File della versione precedente (tracking malattie e giustificativi)",
            "",
            "Excel (*.xlsx *.xlsm)",
        )
        return [Path(f) for f in file]

    def _chiedi_ore_utente(self, attuali: str) -> str | None:
        testo, ok = QInputDialog.getText(
            self, "Correggi le ore", "Ore per ogni riga scelta:", text=attuali
        )
        return testo if ok else None
