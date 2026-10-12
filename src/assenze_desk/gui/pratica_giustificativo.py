"""Nuova pratica, flusso Giustificativo: dipendente, richiesta, righe e azioni.

Tipo, giorni e ore vengono dalla lettura del permesso (core/permessi.py) e si
correggono a mano. Il weekend nei periodi si decide con un interruttore (D48).
Le righe si ricalcolano a ogni modifica: una per giorno, con le ore scritte o
quelle dell'orario del cliente; sopra la capienza residua compare un avviso.
"""

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from assenze_desk.core import formati
from assenze_desk.core.analisi import proposta_dipendente, proposte_permesso
from assenze_desk.core.bozze import valori_giustificativo
from assenze_desk.core.campi import Modulo, Origine
from assenze_desk.core.date_utente import controlla_giorni
from assenze_desk.core.dipendenti import Dipendente, trova_dipendente
from assenze_desk.core.giustificativi import (
    RigaGiustificativo,
    TipoGiustificativo,
    eccedenza_capienza,
    righe_giustificativo,
)
from assenze_desk.core.permessi import leggi_permesso
from assenze_desk.gui.componenti import (
    Avviso,
    BarraMessaggi,
    CampoDato,
    Interruttore,
    Scheda,
    etichetta,
    mostra_portale,
    pulsante,
    riga,
)
from assenze_desk.gui.errori import esegui
from assenze_desk.gui.pannello_dipendente import PannelloDipendente
from assenze_desk.gui.pratica_malattia import InfoMail
from assenze_desk.servizi import Contesto

CAMPI = ("tipo", "giorni", "minuti", "weekend")


class PraticaGiustificativo(QWidget):
    salvata = Signal()

    def __init__(self, contesto: Contesto, messaggi: BarraMessaggi) -> None:
        super().__init__()
        self.contesto, self.messaggi = contesto, messaggi
        self.modulo = Modulo(CAMPI)
        self.scelta = Modulo(["dipendente"])
        self._info = InfoMail()
        self._motivo = ""
        self._salvate = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.dipendente = PannelloDipendente(lambda: self.contesto.anagrafica.dipendenti)
        self.dipendente.scelto.connect(self._dipendente_scelto)
        layout.addWidget(self.dipendente)
        layout.addWidget(self._scheda_richiesta())
        layout.addWidget(self._scheda_righe())
        layout.addWidget(self._scheda_azioni())
        layout.addStretch(1)
        self._ridisegna()

    # --- Costruzione ---

    def _scheda_richiesta(self) -> Scheda:
        scheda = Scheda("Richiesta", "calendario")
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(16)
        griglia.setVerticalSpacing(12)
        riferimento = self._riferimento
        self.campi = {
            "tipo": CampoDato("tipo", "Tipo", "scelta", self._nomi_tipi()),
            "minuti": CampoDato(
                "minuti", "Ore al giorno", "ore", segnaposto="per esempio 2 oppure 1:30"
            ),
            "giorni": CampoDato(
                "giorni",
                "Giorni",
                "giorni",
                segnaposto="gg/mm/aaaa, gg/mm/aaaa",
                riferimento=riferimento,
                oggi=self._oggi,
            ),
        }
        griglia.addWidget(self.campi["tipo"], 0, 0, Qt.AlignmentFlag.AlignTop)
        griglia.addWidget(self.campi["minuti"], 0, 1, Qt.AlignmentFlag.AlignTop)
        griglia.addWidget(self.campi["giorni"], 1, 0, 1, 2)
        for campo in self.campi.values():
            campo.modificato.connect(self._campo_modificato)
            campo.ripristino.connect(self._ripristina)
        scheda.corpo.addLayout(griglia)
        self.giorni_mostrati = etichetta("", "secondario", a_capo=True)
        scheda.corpo.addWidget(self.giorni_mostrati)

        self.avviso_weekend = Avviso("info", icona="calendario")
        self.conta_weekend = Interruttore("Conta anche sabato e domenica")
        self.conta_weekend.toggled.connect(lambda _acceso: self._ridisegna())
        self.avviso_weekend.extra.addWidget(self.conta_weekend)
        scheda.corpo.addWidget(self.avviso_weekend)
        return scheda

    def _scheda_righe(self) -> Scheda:
        scheda = Scheda("Righe da registrare")
        self.tabella = QTableWidget(0, 4)
        self.tabella.setHorizontalHeaderLabels(["Giorno", "Tipo", "Codice", "Ore"])
        self.tabella.verticalHeader().hide()
        self.tabella.setShowGrid(False)
        self.tabella.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabella.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tabella.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabella.setMinimumHeight(140)
        scheda.corpo.addWidget(self.tabella)
        self.totale = etichetta("", "titolo-scheda")
        scheda.corpo.addLayout(riga(None, self.totale))
        self.avviso_capienza = Avviso("ok", icona="salva")
        scheda.corpo.addWidget(self.avviso_capienza)
        return scheda

    def _scheda_azioni(self) -> Scheda:
        scheda = Scheda()
        self.bozza_lavoratore = pulsante("Bozza al lavoratore", "mail")
        self.sposta = pulsante("Sposta mail", "sposta")
        self.salva = pulsante("Salva righe", "salva", "primario")
        self.portale_aziendale = pulsante("Portale aziendale", "esterno", "piatto")
        scheda.corpo.addLayout(
            riga(self.bozza_lavoratore, self.sposta, self.portale_aziendale, None, self.salva)
        )
        self.portale_aziendale.clicked.connect(
            lambda: esegui(self.messaggi, self.contesto.apri_portale_aziendale)
        )
        self.bozza_lavoratore.clicked.connect(lambda: esegui(self.messaggi, self._bozza))
        self.sposta.clicked.connect(lambda: esegui(self.messaggi, self._sposta))
        self.salva.clicked.connect(lambda: esegui(self.messaggi, self._salva))
        return scheda

    # --- Analisi ---

    def analizza(self, testo: str, info: InfoMail) -> None:
        self._info = info
        imp = self.contesto.impostazioni
        data_mail = (info.ricevuta or self.contesto.adesso()).date()
        permesso = leggi_permesso(
            testo, data_mail, None, imp.tipi, imp.vocabolario, imp.giorni_avanti_permessi
        )
        tutti = (*permesso.giorni, *permesso.giorni_weekend)
        esito = trova_dipendente(
            self.contesto.anagrafica.dipendenti,
            testo=testo,
            mittente=info.mittente,
            periodo=(min(tutti), max(tutti)) if tutti else None,
            domini_interni=imp.domini_interni,
        )
        self._motivo = esito.motivo
        self.scelta.proponi({"dipendente": proposta_dipendente(esito)})
        self.modulo.proponi(proposte_permesso(permesso))
        self.conta_weekend.setChecked(False)
        self._salvate = False
        self._ridisegna()

    def _riferimento(self) -> date:
        return (self._info.ricevuta or self.contesto.adesso()).date()

    def _oggi(self) -> date:
        return self.contesto.adesso().date()

    # --- Dall'utente ---

    def _campo_modificato(self, nome: str, valore: object) -> None:
        self.modulo.scrivi(nome, valore)
        self._salvate = False
        self._ridisegna()

    def _ripristina(self, nome: str) -> None:
        self.modulo.ripristina(nome)
        self._ridisegna()

    def _dipendente_scelto(self, dipendente: Dipendente) -> None:
        self.scelta.scrivi("dipendente", dipendente)
        self._salvate = False
        self._ridisegna()

    # --- Calcoli ---

    def _nomi_tipi(self) -> list[str]:
        return [tipo.nome for tipo in self.contesto.impostazioni.tipi]

    def _tipo(self) -> TipoGiustificativo | None:
        nome = self.modulo["tipo"].valore
        return next((t for t in self.contesto.impostazioni.tipi if t.nome == nome), None)

    def _dipendente(self) -> Dipendente | None:
        valore = self.scelta["dipendente"].valore
        return valore if isinstance(valore, Dipendente) else None

    def _giorni(self) -> tuple[date, ...]:
        giorni = set(self.modulo["giorni"].valore or ())
        if self.conta_weekend.isChecked():
            giorni |= set(self.modulo["weekend"].valore or ())
        return tuple(sorted(giorni))

    def righe(self) -> list[RigaGiustificativo]:
        tipo = self._tipo()
        if tipo is None:
            return []
        dipendente = self._dipendente()
        orario = self.contesto.orario(dipendente) if dipendente else None
        minuti = self.modulo["minuti"].valore
        return righe_giustificativo(
            tipo, self._giorni(), minuti if isinstance(minuti, int) else None, orario
        )

    # --- Mostra ---

    def aggiorna(self) -> None:
        """Ridisegna dopo un cambio di impostazioni (tipi, orari, posta)."""
        self._ridisegna()

    def _ridisegna(self) -> None:
        mostra_portale(self.portale_aziendale, self.contesto.impostazioni.portale_aziendale)
        self.campi["tipo"].imposta_scelte(self._nomi_tipi())
        controllati = {"giorni": controlla_giorni(self.modulo["giorni"], self._oggi())}
        for nome, widget in self.campi.items():
            widget.mostra(controllati.get(nome, self.modulo[nome]))
        campo_dipendente = self.scelta["dipendente"]
        automatico = campo_dipendente.origine is Origine.ANAGRAFICA
        self.dipendente.mostra(
            campo_dipendente, f"dal {self._motivo}" if automatico and self._motivo else ""
        )

        tipo = self._tipo()
        if tipo is not None and tipo.a_giornata and self.modulo["minuti"].valore is None:
            self.campi["minuti"].editor.setPlaceholderText("dall'orario del cliente")
        else:
            self.campi["minuti"].editor.setPlaceholderText("per esempio 2 oppure 1:30")

        weekend = tuple(self.modulo["weekend"].valore or ())
        contati = self.conta_weekend.isChecked()
        giorni = [formati.giorno_breve(g) for g in self._giorni()]
        esclusi = [] if contati else [f"{formati.giorno_breve(g)} (escluso)" for g in weekend]
        self.giorni_mostrati.setText(" · ".join(giorni + esclusi))
        self.giorni_mostrati.setVisible(bool(giorni or esclusi))
        nomi_weekend = " e ".join(formati.giorno_breve(g) for g in weekend)
        self.avviso_weekend.mostra(
            f"Nel periodo ci sono {nomi_weekend}: "
            + ("sono conteggiati." if contati else "ora non sono conteggiati.")
            if weekend
            else ""
        )

        righe = self.righe()
        self._mostra_righe(righe)
        self._mostra_capienza(righe, tipo)
        self.salva.setEnabled(bool(righe) and not self._salvate)
        self.sposta.setEnabled(self._info.mail is not None and self.contesto.outlook_disponibile)

    def _mostra_righe(self, righe: list[RigaGiustificativo]) -> None:
        self.tabella.setRowCount(len(righe))
        for numero, riga_ in enumerate(righe):
            ore = formati.ore(riga_.minuti) or "da compilare"
            for colonna, testo in enumerate(
                (
                    f"{formati.giorno_breve(riga_.giorno)}/{riga_.giorno:%Y}",
                    riga_.tipo,
                    riga_.codice,
                    ore,
                )
            ):
                self.tabella.setItem(numero, colonna, QTableWidgetItem(testo))
        totale = sum(r.minuti or 0 for r in righe)
        self.totale.setText(f"Totale {formati.ore(totale)}" if righe else "")

    def _mostra_capienza(
        self, righe: list[RigaGiustificativo], tipo: TipoGiustificativo | None
    ) -> None:
        dipendente = self._dipendente()
        capienza = self.contesto.capienza(dipendente, tipo) if dipendente and tipo else None
        oltre = eccedenza_capienza(righe, capienza)
        if oltre is None or capienza is None or tipo is None:
            self.avviso_capienza.mostra("")
            return
        richieste = sum(r.minuti or 0 for r in righe)
        if oltre:
            self.avviso_capienza.mostra(
                f"{tipo.nome}: la richiesta supera di {formati.ore(oltre)} h le ore residue "
                f"({formati.ore(capienza)} h). Puoi salvare lo stesso.",
                "attenzione",
            )
        else:
            self.avviso_capienza.mostra(
                f"{tipo.nome} residue: {formati.ore(capienza)} h. "
                f"Dopo questa richiesta: {formati.ore(capienza - richieste)} h.",
                "ok",
            )

    # --- Azioni ---

    def _bozza(self) -> None:
        dipendente = self._dipendente()
        destinatario = (dipendente.email if dipendente else "") or self._info.mittente
        template = self.contesto.impostazioni.template
        minuti = self.modulo["minuti"].valore
        mancanti = self.contesto.crea_bozza(
            a=[destinatario] if destinatario else [],
            oggetto=template.oggetto_giustificativo,
            corpo=template.corpo_giustificativo,
            valori=valori_giustificativo(
                dipendente=dipendente,
                tipo=self.modulo["tipo"].valore,
                giorni=self._giorni(),
                minuti=minuti if isinstance(minuti, int) else None,
            ),
            rispondi_a=self._info.mail,
        )
        testo = "Bozza al lavoratore aperta."
        if mancanti:
            testo += f" Segnaposti senza valore: {', '.join(mancanti)}."
        self.messaggi.mostra(testo, "attenzione" if mancanti else "ok")

    def _sposta(self) -> None:
        if self._info.mail is None:
            self.messaggi.mostra(
                "Solo una mail importata da Outlook si può spostare.", "attenzione"
            )
            return
        cartella = self.contesto.sposta_mail(self._info.mail, "giustificativo")
        self.sposta.setEnabled(False)
        self.messaggi.mostra(f"Mail spostata in {cartella}.", "ok")

    def _salva(self) -> None:
        dipendente = self._dipendente()
        if dipendente is None:
            self.messaggi.mostra("Scegli prima il dipendente.", "errore")
            return
        righe = self.righe()
        ids = self.contesto.salva_righe(dipendente, righe)
        self._salvate = True
        self.salvata.emit()
        self._ridisegna()
        self.messaggi.mostra(f"Salvate {len(ids)} righe di {righe[0].tipo}.", "ok")

    def svuota(self) -> None:
        self.modulo.svuota()
        self.scelta.svuota()
        for campo in self.campi.values():
            campo.pulisci()
        self._info, self._motivo, self._salvate = InfoMail(), "", False
        self.conta_weekend.setChecked(False)
        self._ridisegna()
