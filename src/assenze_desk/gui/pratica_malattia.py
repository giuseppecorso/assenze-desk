"""Nuova pratica, flusso Malattia: dipendente, certificato, episodio, INPS e azioni.

I valori stanno in un `Modulo` del core: l'analisi propone, l'utente corregge
(i campi manuali restano), la schermata mostra. Episodio e stato si ricalcolano
a ogni modifica. Le mail restano bozze; salvare archivia anche il PDF.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QGridLayout, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from assenze_desk.adapters.outlook import MailImportata
from assenze_desk.config import regole_analisi
from assenze_desk.core import formati
from assenze_desk.core.analisi import (
    completa_con_dipendente,
    proposta_dipendente,
    proposte_certificato,
    proposte_malattia,
    unisci,
)
from assenze_desk.core.bozze import valori_malattia
from assenze_desk.core.campi import Modulo, Origine, Proposta
from assenze_desk.core.certificato import TIPI, DatiCertificato
from assenze_desk.core.date_utente import AVVISO_FINE_PRIMA, controlla_periodo
from assenze_desk.core.dipendenti import Dipendente, trova_dipendente
from assenze_desk.core.episodio import Certificato, Episodio
from assenze_desk.core.stato import Stato, calcola_stato, serve_mail_ufficio
from assenze_desk.gui.componenti import (
    Avviso,
    BarraMessaggi,
    CampoDato,
    Scheda,
    etichetta,
    pulsante,
    riga,
    separatore,
)
from assenze_desk.gui.errori import esegui
from assenze_desk.gui.pannello_dipendente import PannelloDipendente
from assenze_desk.servizi import Contesto
from assenze_desk.storage.archivio import Pratica

log = logging.getLogger(__name__)

CAMPI = ("protocollo", "cf", "joborder", "inizio", "fine", "tipo_certificato")


@dataclass
class InfoMail:
    """Da dove arriva il testo in analisi: la mail importata (se c'è), mittente e data."""

    mail: MailImportata | None = None
    mittente: str = ""
    ricevuta: datetime | None = None
    iniziata: datetime | None = None  # inizio della lavorazione, per il tempo di gestione


class PraticaMalattia(QWidget):
    salvata = Signal()
    stato_cambiato = Signal(str)
    pdf_cambiato = Signal(object)  # Path | None
    rianalisi_richiesta = Signal()

    def __init__(self, contesto: Contesto, messaggi: BarraMessaggi) -> None:
        super().__init__()
        self.contesto, self.messaggi = contesto, messaggi
        self.modulo = Modulo(CAMPI)
        self.scelta = Modulo(["dipendente"])
        self._base: dict[str, Proposta] = {}
        self._info = InfoMail()
        self._testo = ""
        self._motivo = ""
        self._pdf: Path | None = None
        self._dati_pdf: DatiCertificato | None = None
        self._mail_lavoratore = self._mail_ufficio = False
        self._episodio: Episodio | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.dipendente = PannelloDipendente(lambda: self.contesto.anagrafica.dipendenti)
        self.dipendente.scelto.connect(self._dipendente_scelto)
        layout.addWidget(self.dipendente)
        layout.addWidget(self._scheda_certificato())
        layout.addWidget(self._scheda_inps())
        layout.addWidget(self._scheda_azioni())
        layout.addStretch(1)
        self._ridisegna()

    # --- Costruzione ---

    def _scheda_certificato(self) -> Scheda:
        scheda = Scheda("Certificato", "file")
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(16)
        griglia.setVerticalSpacing(12)
        per_le_date = {"segnaposto": "gg/mm/aaaa", "riferimento": self._oggi, "oggi": self._oggi}
        self.campi = {
            "protocollo": CampoDato("protocollo", "Protocollo", mono=True),
            "cf": CampoDato("cf", "Codice fiscale", mono=True),
            "inizio": CampoDato("inizio", "Dal", "data", **per_le_date),
            "fine": CampoDato("fine", "Al", "data", **per_le_date),
            "tipo_certificato": CampoDato(
                "tipo_certificato", "Tipo di certificato", "scelta", TIPI
            ),
        }
        for numero, campo in enumerate(self.campi.values()):
            griglia.addWidget(campo, numero // 2, numero % 2, Qt.AlignmentFlag.AlignTop)
            campo.modificato.connect(self._campo_modificato)
            campo.ripristino.connect(self._ripristina)
        scheda.corpo.addLayout(griglia)
        scheda.corpo.addWidget(separatore())
        self.episodio = etichetta("", a_capo=True)
        scheda.corpo.addWidget(self.episodio)
        self.avviso_ufficio = Avviso("info", icona="calendario")
        scheda.corpo.addWidget(self.avviso_ufficio)
        return scheda

    def _scheda_inps(self) -> Scheda:
        scheda = Scheda("Certificato dal portale INPS", "esterno")
        self.apri_portale = pulsante("Apri il portale", "esterno")
        self.copia_cf = pulsante("Copia CF", "copia", "piatto")
        self.copia_protocollo = pulsante("Copia protocollo", "copia", "piatto")
        scheda.corpo.addLayout(riga(self.apri_portale, self.copia_cf, self.copia_protocollo))
        scheda.corpo.addWidget(
            etichetta(
                "Sul portale inserisci il codice di controllo e scarica il PDF; poi:",
                "secondario",
                a_capo=True,
            )
        )
        self.scaricato = pulsante("Ho scaricato il PDF", "scarica")
        spiegazione = etichetta(
            "lo cerco nei Download, lo salvo con il nome del protocollo e lo leggo",
            "secondario",
            a_capo=True,
        )
        scheda.corpo.addLayout(riga(self.scaricato, spiegazione, allunga=False))
        self.scaricati = QListWidget()
        self.scaricati.setMaximumHeight(110)
        self.scaricati.itemActivated.connect(self._usa_scaricato_scelto)
        self.scaricati.itemClicked.connect(self._usa_scaricato_scelto)
        self.scaricati.hide()
        scheda.corpo.addWidget(self.scaricati)
        self.apri_portale.clicked.connect(lambda: esegui(self.messaggi, self.contesto.apri_portale))
        self.copia_cf.clicked.connect(lambda: self._copia("cf", "Codice fiscale copiato."))
        self.copia_protocollo.clicked.connect(
            lambda: self._copia("protocollo", "Protocollo copiato.")
        )
        self.scaricato.clicked.connect(self._cerca_scaricati)
        return scheda

    def _scheda_azioni(self) -> Scheda:
        scheda = Scheda("Azioni")
        self.bozza_lavoratore = pulsante("Bozza al lavoratore", "mail")
        self.bozza_ufficio = pulsante("Bozza all'ufficio", "mail")
        self.sposta = pulsante("Sposta mail", "sposta")
        self.salva = pulsante("Salva pratica", "salva", "primario")
        scheda.corpo.addLayout(riga(self.bozza_lavoratore, self.bozza_ufficio, self.sposta))
        nota = etichetta("Le mail restano bozze: le invii tu.", "secondario")
        scheda.corpo.addLayout(riga(nota, None, self.salva))
        self.bozza_lavoratore.clicked.connect(lambda: esegui(self.messaggi, self._bozza_lavoratore))
        self.bozza_ufficio.clicked.connect(lambda: esegui(self.messaggi, self._bozza_ufficio))
        self.sposta.clicked.connect(lambda: esegui(self.messaggi, self._sposta))
        self.salva.clicked.connect(lambda: esegui(self.messaggi, self._salva_e_conferma))
        return scheda

    # --- Analisi ---

    def analizza(self, testo: str, info: InfoMail) -> None:
        self._testo, self._info = testo, info
        data_mail = (info.ricevuta or self.contesto.adesso()).date()
        proposte = proposte_malattia(testo, data_mail, regole_analisi(self.contesto.impostazioni))
        if self._dati_pdf is not None:
            proposte = unisci(proposte, proposte_certificato(self._dati_pdf))
        self._base = proposte
        self._trova_dipendente()
        self._ridisegna()

    def carica_pdf(self, percorso: Path) -> bool:
        """Legge il certificato; la nuova analisi la chiede chi chiama."""
        self._pdf = percorso
        self.pdf_cambiato.emit(percorso)
        dati = esegui(self.messaggi, lambda: self.contesto.leggi_certificato(percorso))
        self._dati_pdf = dati
        return dati is not None

    def _trova_dipendente(self) -> None:
        imp = self.contesto.impostazioni
        cf = self._valore_effettivo("cf")
        inizio, fine = self._valore_effettivo("inizio"), self._valore_effettivo("fine")
        esito = trova_dipendente(
            self.contesto.anagrafica.dipendenti,
            testo=self._testo,
            mittente=self._info.mittente,
            cf=cf or "",
            joborder=self._valore_effettivo("joborder") or "",
            periodo=(inizio, fine) if inizio and fine else None,
            domini_interni=imp.domini_interni,
        )
        self._motivo = esito.motivo
        self.scelta.proponi({"dipendente": proposta_dipendente(esito)})
        self._proponi()

    def _valore_effettivo(self, nome: str) -> object:
        campo = self.modulo[nome]
        if campo.protetto:
            return campo.valore
        return self._base[nome].valore if nome in self._base else None

    def _proponi(self) -> None:
        dipendente = self.scelta["dipendente"].valore
        self.modulo.proponi(completa_con_dipendente(self._base, dipendente))

    # --- Dall'utente ---

    def _campo_modificato(self, nome: str, valore: object) -> None:
        self.modulo.scrivi(nome, valore)
        self._ridisegna()

    def _ripristina(self, nome: str) -> None:
        self.modulo.ripristina(nome)
        self._ridisegna()

    def _dipendente_scelto(self, dipendente: Dipendente) -> None:
        self.scelta.scrivi("dipendente", dipendente)
        self._proponi()
        self._ridisegna()

    def _copia(self, nome: str, conferma: str) -> None:
        valore = self.modulo[nome].valore
        if not valore:
            self.messaggi.mostra("Il campo è vuoto: non c'è niente da copiare.", "attenzione")
            return
        QGuiApplication.clipboard().setText(str(valore))
        self.messaggi.mostra(conferma, "ok")

    # --- Assistente INPS ---

    def _cerca_scaricati(self) -> None:
        trovati = esegui(self.messaggi, self.contesto.pdf_scaricati)
        if trovati is None:
            return
        if not trovati:
            self.messaggi.mostra(
                "Nessun PDF nuovo nei Download dopo l'apertura del portale.", "attenzione"
            )
            return
        if len(trovati) == 1:
            self._usa_scaricato(trovati[0])
            return
        self.scaricati.clear()
        for percorso in trovati:
            voce = QListWidgetItem(percorso.name)
            voce.setData(Qt.ItemDataRole.UserRole, percorso)
            self.scaricati.addItem(voce)
        self.scaricati.show()
        self.messaggi.mostra("Più PDF nuovi nei Download: scegli quello del certificato.", "info")

    def _usa_scaricato_scelto(self, voce: QListWidgetItem) -> None:
        self.scaricati.hide()
        self._usa_scaricato(voce.data(Qt.ItemDataRole.UserRole))

    def _usa_scaricato(self, percorso: Path) -> None:
        protocollo = self.modulo["protocollo"].valore
        if not protocollo:
            self.messaggi.mostra(
                "Scrivi prima il protocollo: serve per il nome del file.", "errore"
            )
            return
        archiviato = esegui(
            self.messaggi, lambda: self.contesto.archivia_scaricato(percorso, str(protocollo))
        )
        if archiviato is not None and self.carica_pdf(archiviato):
            self.messaggi.mostra(f"Certificato salvato come {archiviato.name} e letto.", "ok")
            self.rianalisi_richiesta.emit()

    # --- Azioni ---

    def _dipendente(self) -> Dipendente | None:
        valore = self.scelta["dipendente"].valore
        return valore if isinstance(valore, Dipendente) else None

    def _valori_bozza(self) -> dict[str, str | None]:
        v = self.modulo.valori()
        return valori_malattia(
            dipendente=self._dipendente(),
            protocollo=v["protocollo"],
            cf=v["cf"],
            joborder=v["joborder"],
            inizio=v["inizio"],
            fine=v["fine"],
            episodio=self._episodio,
        )

    def _bozza_lavoratore(self) -> None:
        dipendente = self._dipendente()
        destinatario = (dipendente.email if dipendente else "") or self._info.mittente
        template = self.contesto.impostazioni.template
        mancanti = self.contesto.crea_bozza(
            a=[destinatario] if destinatario else [],
            oggetto=template.oggetto_lavoratore,
            corpo=template.corpo_lavoratore,
            valori=self._valori_bozza(),
            rispondi_a=self._info.mail,
        )
        self._mail_lavoratore = True
        self._dopo_bozza("Bozza al lavoratore aperta.", mancanti)

    def _bozza_ufficio(self) -> None:
        if self.modulo["protocollo"].valore:
            self._salva()  # archivia il PDF prima di allegarlo
        trovati, mancanti_pdf = (
            self.contesto.pdf_episodio(self._episodio) if self._episodio else ((), ())
        )
        imp = self.contesto.impostazioni
        mancanti = self.contesto.crea_bozza(
            a=imp.ufficio.destinatari,
            cc=imp.ufficio.copia,
            oggetto=imp.template.oggetto_ufficio,
            corpo=imp.template.corpo_ufficio,
            valori=self._valori_bozza(),
            allegati=trovati,
        )
        self._mail_ufficio = True
        testo = "Bozza all'ufficio aperta."
        if mancanti_pdf:
            testo += f" Mancano i PDF di: {', '.join(mancanti_pdf)}."
        azione = None
        if self.contesto.bozze_con_mailto and trovati:
            testo += " Con il programma di posta predefinito i PDF vanno allegati a mano."
            url = QUrl.fromLocalFile(str(imp.percorsi.certificati))
            azione = ("Apri la cartella", lambda: QDesktopServices.openUrl(url))
        self._dopo_bozza(testo, mancanti, azione, avviso=bool(mancanti_pdf or azione))

    def _dopo_bozza(self, testo, mancanti: tuple[str, ...], azione=None, avviso=False) -> None:
        if self.modulo["protocollo"].valore:
            self._salva()
        self._ridisegna()
        if mancanti:
            testo += f" Segnaposti senza valore: {', '.join(mancanti)}."
        self.messaggi.mostra(testo, "attenzione" if mancanti or avviso else "ok", azione)

    def _sposta(self) -> None:
        if self._info.mail is None:
            self.messaggi.mostra(
                "Solo una mail importata da Outlook si può spostare.", "attenzione"
            )
            return
        cartella = self.contesto.sposta_mail(self._info.mail, "malattia")
        self.sposta.setEnabled(False)
        self.messaggi.mostra(f"Mail spostata in {cartella}.", "ok")

    def _salva_e_conferma(self) -> None:
        self._salva()
        stato = self._stato()
        self.messaggi.mostra(f"Pratica salvata. Stato: {stato}.", "ok")

    def _salva(self) -> None:
        v = self.modulo.valori()
        protocollo = str(v["protocollo"] or "")
        esistente = self.contesto.archivio.pratica(protocollo) if protocollo else None
        dipendente = self._dipendente()
        tempo = esistente.tempo_gestione_sec if esistente else None
        if tempo is None and self._info.iniziata is not None:
            tempo = (self.contesto.adesso() - self._info.iniziata).total_seconds()
        pratica = Pratica(
            protocollo=protocollo,
            cf=str(v["cf"] or ""),
            dipendente=(
                f"{dipendente.cognome} {dipendente.nome}".strip()
                if dipendente
                else (esistente.dipendente if esistente else "")
            ),
            joborder=(dipendente.joborder if dipendente else "") or str(v["joborder"] or ""),
            cliente=dipendente.cliente if dipendente else (esistente.cliente if esistente else ""),
            inizio=v["inizio"],
            fine=v["fine"],
            data_presentazione=(
                self._info.ricevuta.date()
                if self._info.ricevuta
                else (esistente.data_presentazione if esistente else None)
            ),
            giorni_episodio=self._episodio.giorni if self._episodio else None,
            mail_lavoratore=self._flag("mail_lavoratore"),
            mail_ufficio=self._flag("mail_ufficio"),
            stato_manuale=esistente.stato_manuale if esistente else None,
            tempo_gestione_sec=tempo,
            note=esistente.note if esistente else "",
        )
        archiviato = self.contesto.salva_pratica(pratica, self._pdf)
        if archiviato is not None and archiviato != self._pdf:
            self._pdf = archiviato
            self.pdf_cambiato.emit(archiviato)
        self.salvata.emit()
        self._ridisegna()

    # --- Stato mostrato ---

    def _flag(self, nome: str) -> bool:
        locale = self._mail_lavoratore if nome == "mail_lavoratore" else self._mail_ufficio
        protocollo = self.modulo["protocollo"].valore
        esistente = self.contesto.archivio.pratica(str(protocollo)) if protocollo else None
        return locale or bool(esistente and getattr(esistente, nome))

    def _stato(self) -> Stato:
        v = self.modulo.valori()
        protocollo = v["protocollo"]
        esistente = self.contesto.archivio.pratica(str(protocollo)) if protocollo else None
        return calcola_stato(
            protocollo=v["protocollo"],
            cf=v["cf"],
            inizio=v["inizio"],
            fine=v["fine"],
            mail_lavoratore=self._flag("mail_lavoratore"),
            mail_ufficio=self._flag("mail_ufficio"),
            giorni_episodio=self._episodio.giorni if self._episodio else None,
            stato_manuale=esistente.stato_manuale if esistente else None,
            soglia_ufficio=self.contesto.impostazioni.soglia_ufficio,
        )

    def _calcola_episodio(self) -> Episodio | None:
        v = self.modulo.valori()
        if not (v["protocollo"] and v["cf"] and v["inizio"] and v["fine"]):
            return None
        if v["fine"] < v["inizio"]:
            return None
        certificato = Certificato(str(v["protocollo"]), str(v["cf"]), v["inizio"], v["fine"])
        return self.contesto.episodio(certificato)

    def aggiorna(self) -> None:
        """Ridisegna dopo un cambio di impostazioni (soglia, posta, cartelle)."""
        self._ridisegna()

    def _oggi(self) -> date:
        return self.contesto.adesso().date()

    def _ridisegna(self) -> None:
        inizio, fine = controlla_periodo(self.modulo["inizio"], self.modulo["fine"], self._oggi())
        controllati = {"inizio": inizio, "fine": fine}
        for nome, widget in self.campi.items():
            widget.mostra(controllati.get(nome, self.modulo[nome]))
        campo_dipendente = self.scelta["dipendente"]
        automatico = campo_dipendente.origine is Origine.ANAGRAFICA
        self.dipendente.mostra(
            campo_dipendente, f"dal {self._motivo}" if automatico and self._motivo else ""
        )

        self._episodio = self._calcola_episodio()
        soglia = self.contesto.impostazioni.soglia_ufficio
        lungo = bool(self._episodio and serve_mail_ufficio(self._episodio.giorni, soglia))
        if self._episodio is None and AVVISO_FINE_PRIMA in fine.avviso:
            self.episodio.setText("Episodio: correggi le date, la fine viene prima dell'inizio.")
        elif self._episodio is None:
            self.episodio.setText("Episodio: servono protocollo, codice fiscale e date.")
        else:
            ep = self._episodio
            certificati = (
                "1 certificato"
                if len(ep.certificati) == 1
                else f"{len(ep.certificati)} certificati"
            )
            self.episodio.setText(
                f"Episodio {formati.data(ep.inizio)} → {formati.data(ep.fine)} · "
                f"{ep.giorni} giorni · {certificati}"
            )
        self.avviso_ufficio.mostra(
            f"Oltre {soglia} giorni: serve anche la mail all'ufficio." if lungo else ""
        )
        self.bozza_ufficio.setEnabled(lungo)
        self.sposta.setEnabled(self._info.mail is not None and self.contesto.outlook_disponibile)
        self.stato_cambiato.emit(str(self._stato()))

    # --- Nuova pratica o pratica riaperta ---

    def svuota(self) -> None:
        self.modulo.svuota()
        self.scelta.svuota()
        self._base, self._info, self._testo, self._motivo = {}, InfoMail(), "", ""
        self._pdf = self._dati_pdf = None
        self._mail_lavoratore = self._mail_ufficio = False
        self.scaricati.hide()
        self.pdf_cambiato.emit(None)
        self._ridisegna()

    def carica_pratica(self, pratica: Pratica) -> None:
        self.svuota()
        self.modulo.carica(
            {
                "protocollo": pratica.protocollo,
                "cf": pratica.cf,
                "joborder": pratica.joborder,
                "inizio": pratica.inizio,
                "fine": pratica.fine,
            }
        )
        dipendente = next(
            (
                d
                for d in self.contesto.anagrafica.dipendenti
                if d.cf == pratica.cf and (not pratica.joborder or d.joborder == pratica.joborder)
            ),
            None,
        )
        if dipendente is None and pratica.cf:
            dipendente = Dipendente(
                pratica.cf,
                pratica.dipendente,
                "",
                joborder=pratica.joborder,
                cliente=pratica.cliente,
            )
        if dipendente is not None:
            self.scelta.carica({"dipendente": dipendente})
        pdf = self.contesto.impostazioni.percorsi.certificati / f"{pratica.protocollo}.pdf"
        self._pdf = pdf if pdf.is_file() else None
        self.pdf_cambiato.emit(self._pdf)
        self._ridisegna()
