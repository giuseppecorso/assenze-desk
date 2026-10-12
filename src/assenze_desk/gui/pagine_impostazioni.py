"""Pagine della sezione Impostazioni.

Ogni pagina mostra una parte delle impostazioni (`carica`) e restituisce le
impostazioni con le sue modifiche (`applica`). Un valore non valido dà un
`ValueError` con un messaggio che dice dove correggere. Tutto quello che nella
v6.20 era scritto nel codice si cambia da qui.
"""

import re
from dataclasses import fields, replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from assenze_desk.adapters.ocr import trova_tesseract
from assenze_desk.config import (
    CartelleOutlook,
    Impostazioni,
    MailUfficio,
    Ocr,
    Percorsi,
    PortaleAziendale,
    Risposte,
    indirizzo_apribile,
)
from assenze_desk.core.giustificativi import TipoGiustificativo
from assenze_desk.core.identificativi import RegolaNumero
from assenze_desk.core.vocabolario import VOCABOLARIO, Vocabolario
from assenze_desk.gui.componenti import Scheda, etichetta, pulsante, riga
from assenze_desk.servizi import Contesto
from assenze_desk.storage.anagrafica import scrivi_anagrafica


def elenco(testo: str) -> tuple[str, ...]:
    """ "a, b; c" → ("a", "b", "c")"""
    return tuple(parte.strip() for parte in re.split(r"[,;\n]", testo) if parte.strip())


def testo_elenco(valori: tuple[str, ...]) -> str:
    return ", ".join(valori)


def _modulo(scheda: Scheda) -> QFormLayout:
    forma = QFormLayout()
    forma.setHorizontalSpacing(16)
    forma.setVerticalSpacing(8)
    forma.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    scheda.corpo.addLayout(forma)
    return forma


def _numero(minimo: int, massimo: int) -> QSpinBox:
    casella = QSpinBox()
    casella.setRange(minimo, massimo)
    casella.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    casella.setMaximumWidth(90)
    return casella


class Pagina(QWidget):
    titolo = ""

    def __init__(self) -> None:
        super().__init__()
        self.corpo = QVBoxLayout(self)
        self.corpo.setContentsMargins(0, 0, 0, 0)
        self.corpo.setSpacing(12)

    def carica(self, imp: Impostazioni) -> None:
        raise NotImplementedError

    def applica(self, imp: Impostazioni) -> Impostazioni:
        raise NotImplementedError


class PaginaGenerali(Pagina):
    titolo = "Generali"
    TEMI = (("Come Windows", "sistema"), ("Chiaro", "chiaro"), ("Scuro", "scuro"))
    POSTA = (("Outlook Classic", "outlook"), ("Programma di posta predefinito (mailto)", "mailto"))
    CARTELLE = (
        ("archivio", "Archivio (file)", False),
        ("anagrafica", "Anagrafica Excel (file)", False),
        ("certificati", "Certificati PDF", True),
        ("export", "Export Excel", True),
        ("download", "Download del browser", True),
        ("log", "Log", True),
        ("backup", "Copie di sicurezza", True),
    )

    def __init__(self) -> None:
        super().__init__()
        aspetto = Scheda("Aspetto e posta")
        forma = _modulo(aspetto)
        self.tema, self.posta = QComboBox(), QComboBox()
        for testo, valore in self.TEMI:
            self.tema.addItem(testo, valore)
        for testo, valore in self.POSTA:
            self.posta.addItem(testo, valore)
        forma.addRow("Tema", self.tema)
        forma.addRow("Bozze delle mail", self.posta)
        self.corpo.addWidget(aspetto)

        cartelle = Scheda("Cartelle e file", "cartella")
        forma = _modulo(cartelle)
        self.percorsi: dict[str, QLineEdit] = {}
        for nome, testo, cartella in self.CARTELLE:
            casella = QLineEdit()
            self.percorsi[nome] = casella
            sfoglia = pulsante("Sfoglia…")
            sfoglia.clicked.connect(lambda _=False, c=casella, d=cartella: self._sfoglia(c, d))
            forma.addRow(testo, riga(casella, sfoglia, allunga=False))
        self.corpo.addWidget(cartelle)

    def _sfoglia(self, casella: QLineEdit, cartella: bool) -> None:
        if cartella:
            scelta = QFileDialog.getExistingDirectory(self, "Scegli la cartella", casella.text())
        else:
            scelta, _filtro = QFileDialog.getSaveFileName(
                self,
                "Scegli il file",
                casella.text(),
                options=QFileDialog.Option.DontConfirmOverwrite,
            )
        if scelta:
            casella.setText(scelta)

    def carica(self, imp: Impostazioni) -> None:
        self.tema.setCurrentIndex(max(self.tema.findData(imp.tema), 0))
        self.posta.setCurrentIndex(max(self.posta.findData(imp.posta), 0))
        for nome, casella in self.percorsi.items():
            casella.setText(str(getattr(imp.percorsi, nome)))

    def applica(self, imp: Impostazioni) -> Impostazioni:
        percorsi = {}
        for nome, testo, _cartella in self.CARTELLE:
            valore = self.percorsi[nome].text().strip()
            if not valore:
                raise ValueError(f"Generali: il percorso «{testo}» non può essere vuoto.")
            percorsi[nome] = Path(valore)
        return replace(
            imp,
            tema=self.tema.currentData(),
            posta=self.posta.currentData(),
            percorsi=Percorsi(**percorsi),
        )


class PaginaAnagrafica(Pagina):
    titolo = "Anagrafica"

    def __init__(self, contesto: Contesto) -> None:
        super().__init__()
        self.contesto = contesto
        scheda = Scheda("Anagrafica dei dipendenti", "persona")
        scheda.corpo.addWidget(
            etichetta(
                "Un file Excel con il foglio «Dipendenti» (cognome, nome, codice fiscale, email, "
                "JobOrder, cliente, inizio e fine del JobOrder) e, se servono, i fogli «Orari» "
                "(ore per giorno della settimana di ogni cliente) e «Capienze» (ore residue di "
                "ferie e ROL per JobOrder). Il percorso si cambia in Generali.",
                "secondario",
                a_capo=True,
            )
        )
        self.riepilogo = etichetta("", a_capo=True)
        scheda.corpo.addWidget(self.riepilogo)
        self.avvisi = etichetta("", "avviso-campo", a_capo=True)
        scheda.corpo.addWidget(self.avvisi)
        self.ricarica = pulsante("Ricarica l'anagrafica", "ripristina")
        self.modello = pulsante("Crea un modello vuoto…", "file")
        scheda.corpo.addLayout(riga(self.ricarica, self.modello))
        self.ricarica.clicked.connect(self._ricarica)
        self.modello.clicked.connect(self._crea_modello)
        self.corpo.addWidget(scheda)

    def carica(self, imp: Impostazioni) -> None:
        self.mostra(list(self.contesto.anagrafica.avvisi))

    def applica(self, imp: Impostazioni) -> Impostazioni:
        return imp

    def mostra(self, avvisi: list[str]) -> None:
        anagrafica = self.contesto.anagrafica
        self.riepilogo.setText(
            f"Caricati {len(anagrafica.dipendenti)} dipendenti, orari di {len(anagrafica.orari)} "
            f"clienti, capienze di {len(anagrafica.capienze)} JobOrder."
        )
        self.avvisi.setText("\n".join(avvisi))
        self.avvisi.setVisible(bool(avvisi))

    def _ricarica(self) -> None:
        self.mostra(self.contesto.ricarica_anagrafica())

    def _crea_modello(self) -> None:
        percorso, _filtro = QFileDialog.getSaveFileName(
            self, "Modello di anagrafica", "anagrafica.xlsx", "Excel (*.xlsx)"
        )
        if percorso:
            scrivi_anagrafica(Path(percorso), [], {}, {})


class PaginaMail(Pagina):
    titolo = "Mail e template"
    TEMPLATE = (
        ("lavoratore", "Risposta al lavoratore (malattia)"),
        ("ufficio", "Mail all'ufficio (malattia)"),
        ("giustificativo", "Risposta al lavoratore (giustificativo)"),
    )

    def __init__(self) -> None:
        super().__init__()
        destinatari = Scheda("Destinatari e cartelle", "mail")
        forma = _modulo(destinatari)
        self.destinatari, self.copia, self.domini = QLineEdit(), QLineEdit(), QLineEdit()
        self.cartella_malattie, self.cartella_giustificativi = QLineEdit(), QLineEdit()
        self.destinatari.setPlaceholderText("ufficio@azienda.example, …")
        self.domini.setPlaceholderText(
            "azienda.example (mittenti interni: si cerca il lavoratore nel testo)"
        )
        self.cartella_malattie.setPlaceholderText("Gestite/Malattie (dentro la Posta in arrivo)")
        self.cartella_giustificativi.setPlaceholderText("Gestite/Giustificativi")
        forma.addRow("Mail all'ufficio: a", self.destinatari)
        forma.addRow("Mail all'ufficio: copia", self.copia)
        forma.addRow("Domini interni", self.domini)
        forma.addRow("Cartella Outlook malattie", self.cartella_malattie)
        forma.addRow("Cartella Outlook giustificativi", self.cartella_giustificativi)
        self.corpo.addWidget(destinatari)

        risposte = Scheda("Risposte alle mail di malattia", "mail")
        forma = _modulo(risposte)
        self.dalla_lista_cliente = QCheckBox(
            "Rispondi al lavoratore dalla casella del cliente (primo indirizzo della colonna DL)"
        )
        self.mittente_collega = QLineEdit()
        self.mittente_collega.setPlaceholderText("vuoto = la tua casella predefinita")
        self.corpo_collega = QPlainTextEdit()
        self.corpo_collega.setFixedHeight(90)
        forma.addRow(self.dalla_lista_cliente)
        forma.addRow(
            etichetta(
                "Il cliente (colonna DL o foglio Clienti dell'anagrafica) va sempre in copia "
                "nella risposta al lavoratore. In Outlook serve il permesso di inviare per "
                "conto della sua casella.",
                "secondario",
                a_capo=True,
            )
        )
        forma.addRow("Risposte ai colleghi: da", self.mittente_collega)
        forma.addRow("Risposte ai colleghi: testo", self.corpo_collega)
        self.corpo.addWidget(risposte)

        template = Scheda("Template delle bozze", "file")
        template.corpo.addWidget(
            etichetta(
                "Segnaposti: {NOME} {COGNOME} {CANDIDATO} {CLIENTE} {PROTOCOLLO} {CF} {JOB} {DAL} "
                "{AL} {INIZIO_EPISODIO} {FINE_EPISODIO} {GIORNI_EPISODIO} {PROTOCOLLI} {TIPO} "
                "{GIORNI} {ORE}. Uno senza valore resta visibile nella bozza.",
                "secondario",
                a_capo=True,
            )
        )
        forma = _modulo(template)
        self.oggetti: dict[str, QLineEdit] = {}
        self.corpi: dict[str, QPlainTextEdit] = {}
        for nome, testo in self.TEMPLATE:
            self.oggetti[nome] = QLineEdit()
            self.corpi[nome] = QPlainTextEdit()
            self.corpi[nome].setFixedHeight(110)
            forma.addRow(etichetta(testo, "titolo-scheda"))
            forma.addRow("Oggetto", self.oggetti[nome])
            forma.addRow("Testo", self.corpi[nome])
        self.corpo.addWidget(template)

    def carica(self, imp: Impostazioni) -> None:
        self.destinatari.setText(testo_elenco(imp.ufficio.destinatari))
        self.copia.setText(testo_elenco(imp.ufficio.copia))
        self.domini.setText(testo_elenco(imp.domini_interni))
        self.cartella_malattie.setText(imp.cartelle_outlook.malattie)
        self.cartella_giustificativi.setText(imp.cartelle_outlook.giustificativi)
        self.dalla_lista_cliente.setChecked(imp.risposte.dalla_lista_cliente)
        self.mittente_collega.setText(imp.risposte.mittente_collega)
        self.corpo_collega.setPlainText(imp.template.corpo_collega)
        for nome, _testo in self.TEMPLATE:
            self.oggetti[nome].setText(getattr(imp.template, f"oggetto_{nome}"))
            self.corpi[nome].setPlainText(getattr(imp.template, f"corpo_{nome}"))

    def applica(self, imp: Impostazioni) -> Impostazioni:
        template = replace(
            imp.template,
            **{f"oggetto_{nome}": self.oggetti[nome].text() for nome, _t in self.TEMPLATE},
            **{f"corpo_{nome}": self.corpi[nome].toPlainText() for nome, _t in self.TEMPLATE},
            corpo_collega=self.corpo_collega.toPlainText(),
        )
        return replace(
            imp,
            ufficio=MailUfficio(elenco(self.destinatari.text()), elenco(self.copia.text())),
            domini_interni=elenco(self.domini.text()),
            cartelle_outlook=CartelleOutlook(
                self.cartella_malattie.text().strip(), self.cartella_giustificativi.text().strip()
            ),
            template=template,
            risposte=Risposte(
                self.dalla_lista_cliente.isChecked(), self.mittente_collega.text().strip()
            ),
        )


class PaginaRegole(Pagina):
    titolo = "Regole"

    def __init__(self) -> None:
        super().__init__()
        self.regole: dict[str, tuple[QSpinBox, QLineEdit, QLineEdit]] = {}
        for nome, titolo in (("protocollo", "Protocollo"), ("joborder", "JobOrder")):
            scheda = Scheda(titolo)
            forma = _modulo(scheda)
            caselle = (_numero(1, 30), QLineEdit(), QLineEdit())
            forma.addRow("Cifre", caselle[0])
            forma.addRow("Prefissi ammessi", caselle[1])
            forma.addRow("Parole chiave vicine", caselle[2])
            self.regole[nome] = caselle
            self.corpo.addWidget(scheda)
        scheda = Scheda("Pratiche e permessi")
        forma = _modulo(scheda)
        self.soglia, self.giorni_avanti, self.oltre_media = (
            _numero(0, 60),
            _numero(0, 365),
            _numero(1, 240),
        )
        forma.addRow("Mail all'ufficio oltre (giorni di episodio)", self.soglia)
        forma.addRow("Permessi chiesti in anticipo fino a (giorni)", self.giorni_avanti)
        forma.addRow("Tempo anomalo oltre la media di (minuti)", self.oltre_media)
        self.corpo.addWidget(scheda)

    def carica(self, imp: Impostazioni) -> None:
        for nome, (cifre, prefissi, parole) in self.regole.items():
            regola: RegolaNumero = getattr(imp, nome)
            cifre.setValue(regola.lunghezza)
            prefissi.setText(testo_elenco(regola.prefissi))
            parole.setText(testo_elenco(regola.parole_chiave))
        self.soglia.setValue(imp.soglia_ufficio)
        self.giorni_avanti.setValue(imp.giorni_avanti_permessi)
        self.oltre_media.setValue(imp.minuti_oltre_la_media)

    def applica(self, imp: Impostazioni) -> Impostazioni:
        regole = {}
        for nome, (cifre, prefissi, parole) in self.regole.items():
            try:
                regole[nome] = RegolaNumero(
                    cifre.value(), elenco(prefissi.text()), elenco(parole.text())
                )
            except ValueError as errore:
                raise ValueError(f"Regole, {nome}: {errore}.") from None
        return replace(
            imp,
            **regole,
            soglia_ufficio=self.soglia.value(),
            giorni_avanti_permessi=self.giorni_avanti.value(),
            minuti_oltre_la_media=self.oltre_media.value(),
        )


class PaginaTipi(Pagina):
    titolo = "Tipi di giustificativo"

    def __init__(self) -> None:
        super().__init__()
        scheda = Scheda("Tipi di giustificativo", "calendario")
        scheda.corpo.addWidget(
            etichetta(
                "Parole chiave cercate a parola intera, separate da virgole. «A giornata»: "
                "senza ore scritte valgono le ore dell'orario del cliente. I codici predefiniti "
                "sono solo esempi: usa quelli del tuo gestionale.",
                "secondario",
                a_capo=True,
            )
        )
        self.tabella = QTableWidget(0, 4)
        self.tabella.setHorizontalHeaderLabels(["Nome", "Codice", "Parole chiave", "A giornata"])
        self.tabella.verticalHeader().hide()
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        intestazione = self.tabella.horizontalHeader()
        intestazione.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        intestazione.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabella.setMinimumHeight(220)
        scheda.corpo.addWidget(self.tabella)
        self.aggiungi = pulsante("Aggiungi tipo", "nuova", "piatto")
        self.rimuovi = pulsante("Rimuovi i selezionati", "elimina", "piatto")
        scheda.corpo.addLayout(riga(self.aggiungi, self.rimuovi))
        self.aggiungi.clicked.connect(lambda: self._riga(TipoGiustificativo("Nuovo tipo", "XX")))
        self.rimuovi.clicked.connect(self._rimuovi)
        self.corpo.addWidget(scheda)

    def _riga(self, tipo: TipoGiustificativo) -> None:
        numero = self.tabella.rowCount()
        self.tabella.insertRow(numero)
        for colonna, testo in enumerate((tipo.nome, tipo.codice, testo_elenco(tipo.parole_chiave))):
            self.tabella.setItem(numero, colonna, QTableWidgetItem(testo))
        spunta = QTableWidgetItem()
        spunta.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        spunta.setCheckState(Qt.CheckState.Checked if tipo.a_giornata else Qt.CheckState.Unchecked)
        self.tabella.setItem(numero, 3, spunta)

    def _rimuovi(self) -> None:
        for numero in sorted({i.row() for i in self.tabella.selectedIndexes()}, reverse=True):
            self.tabella.removeRow(numero)

    def carica(self, imp: Impostazioni) -> None:
        self.tabella.setRowCount(0)
        for tipo in imp.tipi:
            self._riga(tipo)

    def applica(self, imp: Impostazioni) -> Impostazioni:
        tipi = []
        for numero in range(self.tabella.rowCount()):
            testi = [
                (
                    self.tabella.item(numero, c).text() if self.tabella.item(numero, c) else ""
                ).strip()
                for c in range(3)
            ]
            if not any(testi):
                continue
            a_giornata = self.tabella.item(numero, 3).checkState() == Qt.CheckState.Checked
            try:
                tipi.append(TipoGiustificativo(testi[0], testi[1], elenco(testi[2]), a_giornata))
            except ValueError as errore:
                raise ValueError(f"Tipi di giustificativo, riga {numero + 1}: {errore}.") from None
        if not tipi:
            raise ValueError("Tipi di giustificativo: serve almeno un tipo.")
        return replace(imp, tipi=tuple(tipi))


NOMI_VOCABOLARIO = {
    "unita_ore": "Ore (come «ore», «h»)",
    "unita_minuti": "Minuti",
    "inizio_fascia": "Inizio fascia («dalle»)",
    "fine_fascia": "Fine fascia («alle»)",
    "invece": "Orario spostato («anziché»)",
    "inizio_periodo": "Inizio periodo («dal»)",
    "fine_periodo": "Fine periodo («al»)",
    "oggi": "Oggi",
    "domani": "Domani",
    "dopodomani": "Dopodomani",
    "ieri": "Ieri",
    "mattina": "Mattina",
    "pomeriggio": "Pomeriggio",
    "giornata_intera": "Giornata intera",
}


class PaginaVocabolario(Pagina):
    titolo = "Vocabolario dei permessi"

    def __init__(self) -> None:
        super().__init__()
        scheda = Scheda("Parole aggiunte al vocabolario")
        scheda.corpo.addWidget(
            etichetta(
                "Le parole comuni ci sono già (tra parentesi alcune): qui aggiungi solo quelle "
                "nuove, separate da virgole.",
                "secondario",
                a_capo=True,
            )
        )
        forma = _modulo(scheda)
        self.aggiunte: dict[str, QLineEdit] = {}
        for campo in fields(Vocabolario):
            casella = QLineEdit()
            predefinite = getattr(VOCABOLARIO, campo.name)
            casella.setPlaceholderText(
                ", ".join(predefinite[:4]) + ("…" if len(predefinite) > 4 else "")
            )
            self.aggiunte[campo.name] = casella
            forma.addRow(NOMI_VOCABOLARIO.get(campo.name, campo.name), casella)
        self.corpo.addWidget(scheda)

    def carica(self, imp: Impostazioni) -> None:
        for nome, casella in self.aggiunte.items():
            predefinite = getattr(VOCABOLARIO, nome)
            casella.setText(
                testo_elenco(
                    tuple(p for p in getattr(imp.vocabolario, nome) if p not in predefinite)
                )
            )

    def applica(self, imp: Impostazioni) -> Impostazioni:
        return replace(
            imp,
            vocabolario=VOCABOLARIO.estendi(
                **{nome: elenco(casella.text()) for nome, casella in self.aggiunte.items()}
            ),
        )


class PaginaOcrInps(Pagina):
    titolo = "OCR e portali"
    SPUNTE = (
        ("Automatico", None),
        ("La X è prima della voce", True),
        ("La X è dopo la voce", False),
    )

    def __init__(self) -> None:
        super().__init__()
        ocr = Scheda("OCR di una zona dello schermo", "ocr")
        forma = _modulo(ocr)
        self.tesseract, self.rumore = QLineEdit(), QLineEdit()
        self.tesseract.setPlaceholderText("vuoto = cercato nei percorsi di installazione standard")
        self.rumore.setPlaceholderText("nomi di programmi visibili sullo schermo, da ignorare")
        self.verifica = pulsante("Verifica", "cerca")
        self.esito = etichetta("", "secondario", a_capo=True)
        forma.addRow("Programma Tesseract", riga(self.tesseract, self.verifica, allunga=False))
        forma.addRow("", self.esito)
        forma.addRow("Parole di disturbo", self.rumore)
        self.verifica.clicked.connect(self._verifica)
        self.corpo.addWidget(ocr)

        inps = Scheda("Certificati INPS", "esterno")
        forma = _modulo(inps)
        self.portale = QLineEdit()
        self.spunte = QComboBox()
        for testo, valore in self.SPUNTE:
            self.spunte.addItem(testo, valore)
        forma.addRow("Indirizzo del portale", self.portale)
        forma.addRow("Spunte nel PDF", self.spunte)
        self.corpo.addWidget(inps)

        aziendale = Scheda("Portale aziendale", "esterno")
        forma = _modulo(aziendale)
        self.nome_portale, self.indirizzo_portale = QLineEdit(), QLineEdit()
        self.indirizzo_portale.setPlaceholderText(
            "https://... oppure il percorso del programma; vuoto = nessun pulsante"
        )
        forma.addRow("Nome del pulsante", self.nome_portale)
        forma.addRow("Indirizzo", self.indirizzo_portale)
        forma.addRow(
            "",
            etichetta(
                "Il pulsante compare nelle Azioni della pratica e apre il portale con un clic. "
                "L'indirizzo resta solo su questo PC.",
                "secondario",
                a_capo=True,
            ),
        )
        self.corpo.addWidget(aziendale)

    def _verifica(self) -> None:
        trovato = trova_tesseract(self.tesseract.text().strip())
        self.esito.setText(
            f"Trovato: {trovato}"
            if trovato
            else "Non trovato: installa Tesseract oppure indica il percorso di tesseract.exe."
        )

    def carica(self, imp: Impostazioni) -> None:
        self.tesseract.setText(imp.ocr.tesseract)
        self.rumore.setText(testo_elenco(imp.ocr.parole_rumore))
        self.portale.setText(imp.portale_inps)
        self.spunte.setCurrentIndex(max(self.spunte.findData(imp.spunte_prima_della_voce), 0))
        self.nome_portale.setText(imp.portale_aziendale.nome)
        self.indirizzo_portale.setText(imp.portale_aziendale.indirizzo)

    def applica(self, imp: Impostazioni) -> Impostazioni:
        portale = self.portale.text().strip()
        if not portale.startswith(("https://", "http://")):
            raise ValueError(
                "OCR e portali: l'indirizzo del portale INPS deve iniziare con https://."
            )
        nome, indirizzo = self.nome_portale.text().strip(), self.indirizzo_portale.text().strip()
        if not indirizzo_apribile(indirizzo):
            raise ValueError(
                "OCR e portali: l'indirizzo del portale aziendale deve iniziare con https:// "
                "oppure essere il percorso di un programma (C:\\...)."
            )
        return replace(
            imp,
            ocr=Ocr(self.tesseract.text().strip(), elenco(self.rumore.text())),
            portale_inps=portale,
            spunte_prima_della_voce=self.spunte.currentData(),
            portale_aziendale=PortaleAziendale(nome or PortaleAziendale.nome, indirizzo),
        )
