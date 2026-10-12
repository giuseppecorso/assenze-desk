"""Servizi dell'app: il collegamento tra le schermate e archivio, anagrafica, posta, file.

Le schermate non aprono file e non parlano con Outlook da sole: passano dal
`Contesto`, che tiene insieme impostazioni, archivio, anagrafica caricata e posta
(Outlook Classic, oppure la posta finta della demo). Così queste operazioni si
provano senza interfaccia. Gli errori da mostrare all'utente sono `ErroreServizi`.
"""

import logging
import shutil
import webbrowser
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from openpyxl.utils.exceptions import InvalidFileException

from assenze_desk.adapters.file import nome_libero
from assenze_desk.adapters.inps import (
    ErroreInps,
    apri_portale,
    archivia_certificato,
    pdf_scaricati_dopo,
)
from assenze_desk.adapters.mailto import apri_bozza_mailto, url_mailto
from assenze_desk.adapters.outlook import MailImportata, Outlook
from assenze_desk.adapters.pdf import leggi_certificato_pdf
from assenze_desk.config import Impostazioni, carica_impostazioni, salva_impostazioni
from assenze_desk.core.certificato import DatiCertificato
from assenze_desk.core.dipendenti import Dipendente
from assenze_desk.core.episodio import Certificato, Episodio, calcola_episodio
from assenze_desk.core.giustificativi import RigaGiustificativo, TipoGiustificativo
from assenze_desk.core.statistiche import PraticaStatistica
from assenze_desk.core.template import compila, compila_per_outlook
from assenze_desk.core.turni import OrarioSettimanale
from assenze_desk.demo.ambiente import PostaDemo, crea_ambiente_demo
from assenze_desk.registro import configura_log
from assenze_desk.storage.anagrafica import EsitoImport, importa_anagrafica
from assenze_desk.storage.archivio import Archivio, Pratica, RigaSalvata
from assenze_desk.storage.export import esporta_giustificativi, esporta_pratiche
from assenze_desk.storage.import_v620 import DatiV620, importa_in_archivio, leggi_file_v620
from assenze_desk.storage.import_v620 import EsitoImport as EsitoImportV620

log = logging.getLogger(__name__)

NOME_FILE_IMPOSTAZIONI = "impostazioni.json"
ANAGRAFICA_VUOTA = EsitoImport((), {}, {}, ())


class ErroreServizi(Exception):
    """Operazione non possibile: il messaggio è pronto da mostrare all'utente."""


@dataclass
class Contesto:
    impostazioni: Impostazioni
    file_impostazioni: Path
    archivio: Archivio
    anagrafica: EsitoImport
    posta: Outlook | PostaDemo
    demo: bool = False
    adesso: Callable[[], datetime] = datetime.now
    apri_url: Callable[[str], object] = webbrowser.open
    _portale_aperto: datetime | None = field(default=None, repr=False)

    def chiudi(self) -> None:
        self.archivio.chiudi()

    @property
    def cartella_in_arrivo(self) -> Path:
        """Dove finiscono i PDF ricevuti, finché la pratica non li archivia."""
        return self.impostazioni.percorsi.certificati / "in_arrivo"

    @property
    def bozze_con_mailto(self) -> bool:
        """Bozze con il programma di posta predefinito: senza allegati né risposta."""
        return self.impostazioni.posta == "mailto"

    @property
    def outlook_disponibile(self) -> bool:
        """Import e spostamento delle mail: con Outlook Classic o con la posta della demo."""
        return self.demo or not self.bozze_con_mailto

    # --- Anagrafica ---

    def ricarica_anagrafica(self) -> list[str]:
        self.anagrafica, avvisi = _carica_anagrafica(self.impostazioni.percorsi.anagrafica)
        return avvisi

    def orario(self, dipendente: Dipendente) -> OrarioSettimanale | None:
        cliente = dipendente.cliente.strip().casefold()
        return next(
            (o for nome, o in self.anagrafica.orari.items() if nome.strip().casefold() == cliente),
            None,
        )

    def capienza(self, dipendente: Dipendente, tipo: TipoGiustificativo) -> int | None:
        """Minuti residui di quel tipo per il JobOrder, se l'anagrafica li riporta."""
        per_tipo = self.anagrafica.capienze.get(dipendente.joborder, {})
        nomi = {tipo.nome.casefold(), tipo.codice.casefold()}
        return next((m for nome, m in per_tipo.items() if nome.strip().casefold() in nomi), None)

    # --- Mail e certificati ---

    def importa_mail(self, flusso: str) -> MailImportata:
        if self.demo and isinstance(self.posta, PostaDemo):
            return self.posta.prossima(flusso)
        if not self.outlook_disponibile:
            raise ErroreServizi(
                "Import da Outlook non disponibile: nelle Impostazioni la posta è il programma "
                "predefinito (mailto). Incolla il testo della mail."
            )
        return self.posta.mail_selezionata()

    def allegati_pdf(self, mail: MailImportata) -> list[Path]:
        salvati = self.posta.salva_allegati(mail, self.cartella_in_arrivo)
        for altro in (p for p in salvati if p.suffix.lower() != ".pdf"):
            altro.unlink(missing_ok=True)  # firme, loghi: non servono
        return [p for p in salvati if p.suffix.lower() == ".pdf"]

    def prepara_pdf(self, percorso: Path) -> Path:
        """Copia di un PDF scelto dall'utente: l'originale resta dov'è."""
        self.cartella_in_arrivo.mkdir(parents=True, exist_ok=True)
        copia = nome_libero(self.cartella_in_arrivo / Path(percorso).name)
        shutil.copy2(percorso, copia)
        return copia

    def leggi_certificato(self, percorso: Path) -> DatiCertificato:
        return leggi_certificato_pdf(percorso, self.impostazioni.spunte_prima_della_voce)

    def episodio(self, certificato: Certificato) -> Episodio:
        return calcola_episodio(certificato, self.archivio.certificati(certificato.cf))

    def pdf_episodio(self, episodio: Episodio) -> tuple[tuple[Path, ...], tuple[str, ...]]:
        """I PDF archiviati dei certificati dell'episodio e i protocolli senza PDF."""
        cartella = self.impostazioni.percorsi.certificati
        trovati = [(p, cartella / f"{p}.pdf") for p in episodio.protocolli]
        return (
            tuple(file for _p, file in trovati if file.is_file()),
            tuple(p for p, file in trovati if not file.is_file()),
        )

    def salva_pratica(self, pratica: Pratica, pdf: Path | None) -> Path | None:
        """Salva la pratica e archivia il suo certificato come "<protocollo>.pdf"."""
        protocollo = pratica.protocollo.strip()
        if not protocollo:
            raise ErroreServizi("Serve il protocollo per salvare la pratica.")
        self.archivio.salva_pratica(pratica)
        stato = pratica.stato_per(self.impostazioni.soglia_ufficio)
        self.archivio.registra("Pratica salvata", protocollo, f"stato {stato}")
        if pdf is None:
            return None
        cartella = self.impostazioni.percorsi.certificati
        if Path(pdf).resolve() == (cartella / f"{protocollo}.pdf").resolve():
            return Path(pdf)
        return self._archivia(pdf, protocollo)

    # --- Assistente INPS ---

    def apri_portale(self) -> None:
        self._portale_aperto = self.adesso()
        apri_portale(self.impostazioni.portale_inps, self.apri_url)

    def pdf_scaricati(self) -> list[Path]:
        if self._portale_aperto is None:
            raise ErroreServizi("Apri prima il portale INPS, poi scarica il certificato.")
        return pdf_scaricati_dopo(self.impostazioni.percorsi.download, self._portale_aperto)

    def archivia_scaricato(self, percorso: Path, protocollo: str) -> Path:
        return self._archivia(percorso, protocollo)

    def apri_portale_aziendale(self) -> None:
        portale = self.impostazioni.portale_aziendale
        if not portale.attivo:
            raise ErroreServizi(
                "Scrivi l'indirizzo del portale aziendale in Impostazioni > OCR e portali."
            )
        self.apri_url(portale.indirizzo)

    # --- Bozze e spostamento: mai invii ---

    def crea_bozza(
        self,
        *,
        a: Sequence[str],
        oggetto: str,
        corpo: str,
        valori: Mapping[str, str | None],
        cc: Sequence[str] = (),
        allegati: Sequence[Path] = (),
        rispondi_a: MailImportata | None = None,
        mittente: str = "",
    ) -> tuple[str, ...]:
        """Apre una bozza e restituisce i segnaposti rimasti senza valore.

        `mittente` vale solo per le risposte in Outlook (per conto di un'altra casella);
        con il programma di posta predefinito non si può scegliere."""
        if not a and rispondi_a is None:
            raise ErroreServizi("Mancano i destinatari della mail: aggiungili nelle Impostazioni.")
        oggetto_compilato = compila(oggetto, valori)
        if self.bozze_con_mailto:
            testo = compila(corpo, valori)
            destinatari = list(a)
            if not destinatari and rispondi_a is not None:
                destinatari = [rispondi_a.mittente]
            apri_bozza_mailto(
                url_mailto(destinatari, oggetto_compilato.testo, testo.testo, cc), self.apri_url
            )
            return _senza_doppioni(oggetto_compilato.mancanti + testo.mancanti)
        html = compila_per_outlook(corpo, valori)
        if rispondi_a is not None:
            self.posta.bozza_risposta(rispondi_a, html.testo, cc, mittente)
            return _senza_doppioni(html.mancanti)
        self.posta.bozza_nuova(a, oggetto_compilato.testo, html.testo, cc, allegati)
        return _senza_doppioni(oggetto_compilato.mancanti + html.mancanti)

    def sposta_mail(self, mail: MailImportata, flusso: str) -> str:
        if not self.outlook_disponibile:
            raise ErroreServizi("Spostare la mail richiede Outlook Classic (vedi Impostazioni).")
        cartelle = self.impostazioni.cartelle_outlook
        cartella = cartelle.malattie if flusso == "malattia" else cartelle.giustificativi
        if not cartella.strip():
            raise ErroreServizi(
                "Scegli la cartella di Outlook per le mail gestite nelle Impostazioni."
            )
        return self.posta.sposta(mail, cartella)

    # --- Giustificativi ---

    def salva_righe(self, dipendente: Dipendente, righe: Sequence[RigaGiustificativo]) -> list[int]:
        if not righe:
            raise ErroreServizi("Nessun giorno da salvare: indica i giorni della richiesta.")
        senza_ore = sum(1 for riga in righe if riga.minuti is None)
        if senza_ore:
            raise ErroreServizi(f"Mancano le ore in {senza_ore} righe: compilale prima di salvare.")
        nome = f"{dipendente.cognome} {dipendente.nome}".strip()
        ids = self.archivio.aggiungi_righe(
            RigaSalvata(
                dipendente.cf,
                nome,
                dipendente.joborder,
                dipendente.cliente,
                riga.giorno,
                riga.tipo,
                riga.codice,
                riga.minuti,
            )
            for riga in righe
        )
        self.archivio.registra("Giustificativo salvato", "", f"{len(ids)} righe di {righe[0].tipo}")
        return ids

    # --- Export, statistiche, impostazioni ---

    def esporta_pratiche(self, pratiche: Sequence[Pratica]) -> Path:
        file = self._file_export("pratiche")
        esporta_pratiche(pratiche, file)
        return file

    def esporta_righe(self, righe: Sequence[RigaSalvata]) -> Path:
        file = self._file_export("giustificativi")
        esporta_giustificativi(righe, file)
        self.archivio.segna_esportate([r.id for r in righe if r.id is not None])
        return file

    def importa_v620(self, percorso: Path) -> tuple[DatiV620, EsitoImportV620]:
        """Pratiche o giustificativi dai file Excel della versione precedente."""
        try:
            dati = leggi_file_v620(percorso)
        except (ValueError, OSError, zipfile.BadZipFile, InvalidFileException) as errore:
            raise ErroreServizi(f"{percorso.name}: {errore}") from errore
        return dati, importa_in_archivio(self.archivio, dati)

    def pratiche_statistiche(self) -> list[PraticaStatistica]:
        soglia = self.impostazioni.soglia_ufficio
        return [
            PraticaStatistica(
                p.protocollo,
                p.cf,
                p.dipendente,
                p.cliente,
                p.inizio,
                p.fine,
                p.giorni_episodio,
                p.stato_per(soglia),
                p.tempo_gestione_sec,
            )
            for p in self.archivio.pratiche()
        ]

    def salva_impostazioni(self, nuove: Impostazioni) -> list[str]:
        """Salva e applica subito; restituisce gli avvisi (per esempio dell'anagrafica)."""
        salva_impostazioni(nuove, self.file_impostazioni)
        vecchie, self.impostazioni = self.impostazioni, nuove
        if nuove.percorsi.archivio != vecchie.percorsi.archivio:
            self.archivio.chiudi()
            self.archivio = Archivio(nuove.percorsi.archivio, soglia_ufficio=nuove.soglia_ufficio)
        self.archivio.soglia_ufficio = nuove.soglia_ufficio
        if nuove.percorsi.log != vecchie.percorsi.log:
            configura_log(nuove.percorsi.log)
        if nuove.percorsi.anagrafica != vecchie.percorsi.anagrafica:
            return self.ricarica_anagrafica()
        return []

    # --- Interni ---

    def _archivia(self, percorso: Path, protocollo: str) -> Path:
        try:
            return archivia_certificato(
                percorso, self.impostazioni.percorsi.certificati, protocollo
            )
        except (ErroreInps, OSError) as errore:
            log.warning("Certificato non archiviato: %s", errore)
            raise ErroreServizi(f"Certificato non archiviato: {errore}") from errore

    def _file_export(self, nome: str) -> Path:
        cartella = self.impostazioni.percorsi.export
        return nome_libero(cartella / f"{nome}_{self.adesso():%Y%m%d_%H%M%S}.xlsx")


def apri_contesto(
    cartella_dati: Path,
    *,
    demo: bool = False,
    oggi: date | None = None,
    adesso: Callable[[], datetime] = datetime.now,
    apri_url: Callable[[str], object] = webbrowser.open,
) -> tuple[Contesto, list[str]]:
    """Apre l'app sulla cartella dati; in demo la riempie prima con dati finti."""
    cartella_dati = Path(cartella_dati)
    file = cartella_dati / NOME_FILE_IMPOSTAZIONI
    posta: Outlook | PostaDemo = Outlook()
    if demo:
        posta = crea_ambiente_demo(cartella_dati, oggi or adesso().date())
    impostazioni, avvisi = carica_impostazioni(file, cartella_dati)
    if not file.is_file():
        salva_impostazioni(impostazioni, file)  # così l'utente trova il file da modificare
    configura_log(impostazioni.percorsi.log)
    anagrafica, avvisi_anagrafica = _carica_anagrafica(impostazioni.percorsi.anagrafica)
    archivio = Archivio(impostazioni.percorsi.archivio, soglia_ufficio=impostazioni.soglia_ufficio)
    log.info("App aperta%s", " in modalità demo" if demo else "")
    contesto = Contesto(impostazioni, file, archivio, anagrafica, posta, demo, adesso, apri_url)
    return contesto, avvisi + avvisi_anagrafica


def _carica_anagrafica(percorso: Path) -> tuple[EsitoImport, list[str]]:
    if not Path(percorso).is_file():
        return ANAGRAFICA_VUOTA, [
            "Anagrafica non trovata: caricala dalle Impostazioni. "
            "Il dipendente si può sempre inserire a mano."
        ]
    try:
        esito = importa_anagrafica(percorso)
    except (ValueError, OSError, zipfile.BadZipFile, InvalidFileException) as errore:
        log.warning("Anagrafica non leggibile: %s", errore)
        return ANAGRAFICA_VUOTA, [f"Anagrafica non leggibile: {errore}"]
    return esito, list(esito.avvisi)


def _senza_doppioni(nomi: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(nomi))
