"""Finestra "Modifica dati del dipendente": correzioni salvate nell'app, sopra l'Excel.

CF e JobOrder identificano la riga e si vedono soltanto. "Altre email" sono gli
indirizzi da cui il dipendente scrive oltre a quello principale: l'app li
ricorda da sola quando si salva una pratica e qui si possono togliere o
aggiungere. "Torna ai dati dell'Excel" toglie la correzione.
"""

from dataclasses import replace
from enum import Enum

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from assenze_desk.core import formati
from assenze_desk.core.date import leggi_data
from assenze_desk.core.dipendenti import Dipendente
from assenze_desk.gui.componenti import etichetta, pulsante, riga


class Esito(Enum):
    ANNULLATA = "annullata"
    SALVATA = "salvata"
    RIPRISTINATA = "ripristinata"


class ModificaDipendente(QDialog):
    def __init__(
        self,
        dipendente: Dipendente,
        altre_email: list[str],
        corretto: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modifica dati del dipendente")
        self.setMinimumWidth(460)
        self._dipendente = dipendente
        self.esito = Esito.ANNULLATA
        self.corretto: Dipendente = dipendente
        self.altre_email: list[str] = list(altre_email)

        layout = QVBoxLayout(self)
        forma = QFormLayout()
        forma.addRow("Codice fiscale", QLabel(dipendente.cf))
        forma.addRow("JobOrder", QLabel(dipendente.joborder or "—"))
        self.caselle = {
            "cognome": QLineEdit(dipendente.cognome),
            "nome": QLineEdit(dipendente.nome),
            "email": QLineEdit(dipendente.email),
            "altre_email": QLineEdit(", ".join(altre_email)),
            "cliente": QLineEdit(dipendente.cliente),
            "copia_cliente": QLineEdit(dipendente.copia_cliente),
            "inizio_joborder": QLineEdit(formati.data(dipendente.inizio_joborder)),
            "fine_joborder": QLineEdit(formati.data(dipendente.fine_joborder)),
        }
        self.caselle["altre_email"].setPlaceholderText("indirizzi separati da virgola")
        self.caselle["copia_cliente"].setPlaceholderText("lista del cliente in copia (DL)")
        for nome in ("inizio_joborder", "fine_joborder"):
            self.caselle[nome].setPlaceholderText("gg/mm/aaaa")
        etichette = {
            "cognome": "Cognome",
            "nome": "Nome",
            "email": "Email",
            "altre_email": "Altre email",
            "cliente": "Cliente",
            "copia_cliente": "Cliente in copia",
            "inizio_joborder": "JobOrder dal",
            "fine_joborder": "JobOrder al",
        }
        for nome, casella in self.caselle.items():
            forma.addRow(etichette[nome], casella)
        layout.addLayout(forma)
        layout.addWidget(
            etichetta(
                "Le modifiche restano in Assenze Desk: il file Excel non cambia. "
                "Valgono anche dopo aver aggiornato l'Excel, finché non torni ai suoi dati.",
                "secondario",
                a_capo=True,
            )
        )
        self.errore = etichetta("", "avviso-campo", a_capo=True)
        self.errore.hide()
        layout.addWidget(self.errore)

        self.salva = pulsante("Salva", "salva", "primario")
        self.annulla = pulsante("Annulla", "chiudi")
        self.ripristina = pulsante("Torna ai dati dell'Excel", "ripristina", "piatto")
        self.ripristina.setVisible(corretto)
        layout.addLayout(riga(self.ripristina, None, self.annulla, self.salva))
        self.salva.clicked.connect(self._salva)
        self.annulla.clicked.connect(self.reject)
        self.ripristina.clicked.connect(self._ripristina)

    def _salva(self) -> None:
        testo = {nome: casella.text().strip() for nome, casella in self.caselle.items()}
        if not testo["cognome"]:
            self._mostra_errore("Il cognome non può restare vuoto.")
            return
        date_lette = {}
        for nome in ("inizio_joborder", "fine_joborder"):
            date_lette[nome] = leggi_data(testo[nome]) if testo[nome] else None
            if testo[nome] and date_lette[nome] is None:
                self._mostra_errore(f"Data non valida: {testo[nome]} (serve gg/mm/aaaa).")
                return
        altre = [e.strip() for e in testo["altre_email"].replace(";", ",").split(",")]
        indirizzi = [testo["email"], *altre]
        if any(e and "@" not in e for e in indirizzi):
            self._mostra_errore("Controlla le email: ogni indirizzo deve contenere @.")
            return
        self.corretto = replace(
            self._dipendente,
            cognome=testo["cognome"],
            nome=testo["nome"],
            email=testo["email"],
            cliente=testo["cliente"],
            copia_cliente=testo["copia_cliente"],
            **date_lette,
        )
        self.altre_email = [e for e in altre if e]
        self.esito = Esito.SALVATA
        self.accept()

    def _ripristina(self) -> None:
        self.esito = Esito.RIPRISTINATA
        self.accept()

    def _mostra_errore(self, testo: str) -> None:
        self.errore.setText(testo)
        self.errore.show()


def _mostra(finestra: ModificaDipendente) -> None:
    finestra.exec()


mostra_finestra = _mostra  # i test la sostituiscono: la finestra non si apre davvero


def apri_modifica(parent, contesto, dipendente: Dipendente, messaggi) -> Dipendente | None:
    """Apre la finestra e applica la scelta; restituisce il dipendente aggiornato
    (None se l'utente annulla o se non è un dipendente dell'anagrafica)."""
    if contesto.originale(dipendente) is None:
        messaggi.mostra("Si possono modificare solo i dipendenti dell'anagrafica.", "attenzione")
        return None
    finestra = ModificaDipendente(
        dipendente, contesto.archivio.email_di(dipendente.cf), contesto.corretto(dipendente), parent
    )
    mostra_finestra(finestra)
    if finestra.esito is Esito.ANNULLATA:
        return None
    nome = f"{dipendente.nome} {dipendente.cognome}".strip()
    if finestra.esito is Esito.SALVATA:
        contesto.correggi_dipendente(finestra.corretto, finestra.altre_email)
        messaggi.mostra(f"Dati di {nome} salvati in Assenze Desk (l'Excel non cambia).", "ok")
    else:
        contesto.togli_correzione(dipendente)
        messaggi.mostra(f"Per {nome} valgono di nuovo i dati dell'Excel.", "ok")
    return contesto.aggiornato(dipendente)


def aggiorna_scelta(scelta, nuovo: Dipendente) -> None:
    """Dopo una modifica la pratica mostra i dati nuovi, con la stessa origine:
    se il dipendente era proposto in automatico resta automatico."""
    campo = scelta["dipendente"]
    if campo.protetto or campo.proposta is None or campo.proposta.valore is None:
        scelta.scrivi("dipendente", nuovo)
    else:
        scelta.proponi({"dipendente": replace(campo.proposta, valore=nuovo)})


def modifica_nella_pratica(schermata, dipendente: Dipendente) -> bool:
    """ "Modifica dati" dal riquadro Dipendente di una pratica; True se è cambiato."""
    nuovo = apri_modifica(schermata, schermata.contesto, dipendente, schermata.messaggi)
    if nuovo is None:
        return False
    aggiorna_scelta(schermata.scelta, nuovo)
    return True


def nota_mittente(contesto, dipendente: Dipendente | None, mittente: str) -> str:
    """Ricorda l'indirizzo da cui ha scritto il dipendente (se è nuovo) e dice quale."""
    if dipendente is None or not mittente:
        return ""
    indirizzo = contesto.ricorda_mittente(dipendente, mittente)
    if not indirizzo:
        return ""
    nome = f"{dipendente.nome} {dipendente.cognome}".strip()
    return f" D'ora in poi riconosco {nome} anche da {indirizzo}."
