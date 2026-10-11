"""Pannello del dipendente, uguale nei due flussi (problema noto 7).

Mostra il dipendente scelto e da dove viene, i suggeriti con cliente e periodo
del JobOrder, la ricerca su cognome, nome, CF, JobOrder e cliente, e
l'inserimento a mano anche senza anagrafica caricata.
"""

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QLineEdit, QListWidget, QListWidgetItem, QWidget

from assenze_desk.core import formati
from assenze_desk.core.campi import Campo
from assenze_desk.core.codice_fiscale import cf_valido
from assenze_desk.core.dipendenti import Dipendente, cerca_dipendenti
from assenze_desk.gui import icone
from assenze_desk.gui.componenti import (
    EtichettaOrigine,
    Scheda,
    etichetta,
    pulsante,
    riga,
)

RISULTATI_MASSIMI = 20


def descrizione(dipendente: Dipendente) -> str:
    """Cliente, JobOrder e periodo: quello che serve per distinguere due righe uguali."""
    parti = [dipendente.cliente or "cliente non indicato"]
    if dipendente.joborder:
        parti.append(f"JobOrder {dipendente.joborder}")
    if dipendente.inizio_joborder or dipendente.fine_joborder:
        parti.append(
            f"{formati.data(dipendente.inizio_joborder) or '…'} → "
            f"{formati.data(dipendente.fine_joborder) or '…'}"
        )
    return " · ".join(parti)


def nome_completo(dipendente: Dipendente) -> str:
    return f"{dipendente.nome} {dipendente.cognome}".strip()


class PannelloDipendente(Scheda):
    scelto = Signal(object)  # il Dipendente scelto dall'utente

    def __init__(self, anagrafica: Callable[[], Sequence[Dipendente]]) -> None:
        super().__init__("Dipendente", "persona")
        self._anagrafica = anagrafica

        self.cerca = QLineEdit()
        self.cerca.setPlaceholderText("Cerca per cognome, nome, CF, JobOrder o cliente")
        icone.in_casella(self.cerca, "cerca", QLineEdit.ActionPosition.LeadingPosition)
        self.cerca.textChanged.connect(self._cerca)
        self.corpo.addWidget(self.cerca)
        self.risultati = self._elenco()
        self.corpo.addWidget(self.risultati)

        self.nome = etichetta("Nessun dipendente scelto", "titolo-scheda")
        self.origine = EtichettaOrigine()
        self.dettagli = etichetta("", "secondario", a_capo=True)
        self.corpo.addLayout(riga(self.nome, self.origine))
        self.corpo.addWidget(self.dettagli)
        self.avviso = etichetta("", "avviso-campo", a_capo=True)
        self.avviso.hide()
        self.corpo.addWidget(self.avviso)

        self.titolo_suggeriti = etichetta("Possibili", "secondario")
        self.suggeriti = self._elenco()
        self.corpo.addWidget(self.titolo_suggeriti)
        self.corpo.addWidget(self.suggeriti)

        self.a_mano = pulsante("Inserisci a mano (senza anagrafica)", "persona", "piatto")
        self.a_mano.setCheckable(True)
        self.a_mano.toggled.connect(self._mostra_modulo)
        self.corpo.addLayout(riga(self.a_mano))
        self.modulo = self._modulo_manuale()
        self.corpo.addWidget(self.modulo)
        self._mostra_suggeriti(())

    # --- Dal core ---

    def mostra(self, campo: Campo, motivo: str = "") -> None:
        dipendente = campo.valore if isinstance(campo.valore, Dipendente) else None
        if dipendente is None:
            self.nome.setText("Nessun dipendente scelto")
            self.dettagli.setText("")
            self.origine.mostra(None)
        else:
            self.nome.setText(nome_completo(dipendente))
            self.dettagli.setText(descrizione(dipendente))
            self.origine.mostra(campo.origine, motivo)
        self.avviso.setText(campo.avviso)
        self.avviso.setVisible(bool(campo.avviso))
        self._mostra_suggeriti(campo.scelte if dipendente is None else ())

    # --- Ricerca e suggeriti ---

    def _elenco(self) -> QListWidget:
        elenco = QListWidget()
        elenco.setMaximumHeight(150)
        elenco.itemActivated.connect(self._scegli)
        elenco.itemClicked.connect(self._scegli)
        elenco.hide()
        return elenco

    def _riempi(self, elenco: QListWidget, dipendenti: Sequence[Dipendente]) -> None:
        elenco.clear()
        for dipendente in dipendenti:
            voce = QListWidgetItem(f"{nome_completo(dipendente)}  ·  {descrizione(dipendente)}")
            voce.setData(Qt.ItemDataRole.UserRole, dipendente)
            elenco.addItem(voce)
        elenco.setVisible(bool(dipendenti))

    def _cerca(self, testo: str) -> None:
        self._riempi(
            self.risultati, cerca_dipendenti(self._anagrafica(), testo)[:RISULTATI_MASSIMI]
        )

    def _mostra_suggeriti(self, scelte: Sequence[object]) -> None:
        candidati = [s for s in scelte if isinstance(s, Dipendente)]
        self._riempi(self.suggeriti, candidati)
        self.titolo_suggeriti.setVisible(bool(candidati))

    def _scegli(self, voce: QListWidgetItem) -> None:
        dipendente = voce.data(Qt.ItemDataRole.UserRole)
        self.cerca.clear()
        self.scelto.emit(dipendente)

    # --- Inserimento a mano ---

    def _modulo_manuale(self) -> QWidget:
        riquadro = QWidget()
        forma = QFormLayout(riquadro)
        forma.setContentsMargins(0, 0, 0, 0)
        self.manuali = {}
        for nome, titolo in (
            ("cognome", "Cognome"),
            ("nome", "Nome"),
            ("cf", "Codice fiscale"),
            ("email", "Email"),
            ("cliente", "Cliente"),
            ("joborder", "JobOrder"),
        ):
            casella = QLineEdit()
            self.manuali[nome] = casella
            forma.addRow(titolo, casella)
        self.errore_manuale = etichetta("", "avviso-campo", a_capo=True)
        self.errore_manuale.hide()
        usa = pulsante("Usa questi dati", "salva")
        usa.clicked.connect(self._usa_manuale)
        forma.addRow(self.errore_manuale)
        forma.addRow(usa)
        riquadro.hide()
        return riquadro

    def _mostra_modulo(self, aperto: bool) -> None:
        self.modulo.setVisible(aperto)

    def _usa_manuale(self) -> None:
        valori = {nome: casella.text().strip() for nome, casella in self.manuali.items()}
        valori["cf"] = valori["cf"].replace(" ", "").upper()
        errore = ""
        if not valori["cognome"] or not valori["nome"]:
            errore = "Servono cognome e nome."
        elif not cf_valido(valori["cf"]):
            errore = "Codice fiscale non valido: controlla le lettere e il carattere finale."
        self.errore_manuale.setText(errore)
        self.errore_manuale.setVisible(bool(errore))
        if errore:
            return
        self.a_mano.setChecked(False)
        for casella in self.manuali.values():
            casella.clear()
        self.scelto.emit(Dipendente(**valori))
