"""Ambiente della modalità demo: una cartella dati completa, con soli dati finti.

`crea_ambiente_demo` scrive impostazioni, anagrafica Excel, archivio con pratiche
in tutti gli stati, righe di giustificativi e certificati PDF finti. Restituisce
una `PostaDemo`: al posto di Outlook dà le mail generate (malattie e permessi),
salva come allegato un certificato finto e registra bozze e spostamenti senza
aprire niente. Tutto è ripetibile con lo stesso seme.
"""

import logging
import random
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

from assenze_desk.adapters.file import nome_libero
from assenze_desk.adapters.outlook import ErroreOutlook, MailImportata
from assenze_desk.config import (
    CartelleOutlook,
    MailUfficio,
    impostazioni_predefinite,
    salva_impostazioni,
)
from assenze_desk.core.dipendenti import Dipendente
from assenze_desk.core.episodio import Certificato, calcola_episodio
from assenze_desk.core.giustificativi import TIPI_PREDEFINITI, righe_giustificativo
from assenze_desk.core.mail import dividi_mail
from assenze_desk.demo.certificati import CertificatoFinto, scrivi_certificato_finto
from assenze_desk.demo.generatore import DatiDemo, MailDemo, genera_dati
from assenze_desk.storage.anagrafica import scrivi_anagrafica
from assenze_desk.storage.archivio import Archivio, Pratica, RigaSalvata

log = logging.getLogger(__name__)

DIPENDENTI = 24
PRATICHE_IN_ARCHIVIO = 24
PERMESSI_IN_ARCHIVIO = 8
UFFICIO_DEMO = "ufficio.personale@example.com"
FLUSSI = ("malattia", "giustificativo")


@dataclass(frozen=True)
class BozzaDemo:
    a: tuple[str, ...]
    oggetto: str
    corpo_html: str
    cc: tuple[str, ...] = ()
    allegati: tuple[Path, ...] = ()
    risposta_a: str = ""  # EntryID della mail a cui risponde
    mittente: str = ""  # casella per conto della quale si risponde


class PostaDemo:
    """Stessi metodi dell'adapter di Outlook, ma con le mail della demo."""

    def __init__(
        self,
        mail_malattia: Sequence[MailDemo],
        mail_permesso: Sequence[MailDemo],
        anagrafica: Sequence[Dipendente],
    ) -> None:
        self._code = {"malattia": deque(mail_malattia), "giustificativo": deque(mail_permesso)}
        self._persone = {d.cf: d for d in anagrafica}
        self._importate: dict[str, MailDemo] = {}
        self.bozze: list[BozzaDemo] = []
        self.spostate: list[tuple[str, str]] = []

    def prossima(self, flusso: str) -> MailImportata:
        """La prossima mail del flusso; finite le mail si ricomincia dalla prima."""
        coda = self._code[flusso]
        if not coda:
            raise ErroreOutlook("La demo non ha mail di questo tipo.")
        demo = coda[0]
        coda.rotate(-1)
        entry_id = f"demo-{len(self._importate) + 1}"
        self._importate[entry_id] = demo
        parti = dividi_mail(demo.testo)
        return MailImportata(
            parti.oggetto, parti.corpo, demo.mittente, demo.ricevuta, entry_id, "demo"
        )

    def mail_selezionata(self) -> MailImportata:
        return self.prossima("malattia")

    def salva_allegati(self, mail: MailImportata, cartella: Path) -> list[Path]:
        demo = self._ritrova(mail)
        if "protocollo" not in demo.atteso:
            return []
        atteso = demo.atteso
        persona = self._persone[atteso["cf"]]
        certificato = CertificatoFinto(
            atteso["protocollo"],
            atteso["cf"],
            persona.cognome,
            persona.nome,
            atteso["inizio"],
            atteso["fine"],
        )
        destinazione = nome_libero(Path(cartella) / f"certificato_{atteso['protocollo']}.pdf")
        return [scrivi_certificato_finto(certificato, destinazione)]

    def bozza_risposta(
        self, mail: MailImportata, corpo_html: str, cc: Sequence[str] = (), mittente: str = ""
    ) -> None:
        demo = self._ritrova(mail)
        self.bozze.append(
            BozzaDemo(
                (demo.mittente,),
                f"R: {mail.oggetto}",
                corpo_html,
                tuple(cc),
                (),
                mail.entry_id,
                mittente,
            )
        )
        log.info("Demo: bozza di risposta pronta (Outlook non viene aperto)")

    def bozza_nuova(
        self,
        a: Sequence[str],
        oggetto: str,
        corpo_html: str,
        cc: Sequence[str] = (),
        allegati: Sequence[Path] = (),
    ) -> None:
        self.bozze.append(BozzaDemo(tuple(a), oggetto, corpo_html, tuple(cc), tuple(allegati)))
        log.info(
            "Demo: nuova bozza pronta con %d allegati (Outlook non viene aperto)", len(allegati)
        )

    def sposta(self, mail: MailImportata, percorso_cartella: str) -> str:
        self._ritrova(mail)
        self.spostate.append((mail.entry_id, percorso_cartella))
        return percorso_cartella

    def _ritrova(self, mail: MailImportata) -> MailDemo:
        if mail.entry_id not in self._importate:
            raise ErroreOutlook("La mail importata non è più disponibile: importala di nuovo.")
        return self._importate[mail.entry_id]


def crea_ambiente_demo(cartella: Path, oggi: date, seme: int = 0) -> PostaDemo:
    cartella = Path(cartella)
    caso = random.Random(seme)
    dati = genera_dati(
        oggi,
        seme,
        dipendenti=DIPENDENTI,
        mail_malattia=PRATICHE_IN_ARCHIVIO + 12,
        mail_permesso=PERMESSI_IN_ARCHIVIO + 15,
    )
    imp = replace(
        impostazioni_predefinite(cartella),
        ufficio=MailUfficio(destinatari=(UFFICIO_DEMO,)),
        domini_interni=("azienda.example",),
        cartelle_outlook=CartelleOutlook("Gestite/Malattie", "Gestite/Giustificativi"),
    )
    salva_impostazioni(imp, cartella / "impostazioni.json")
    capienze = {
        d.joborder: {"Ferie": caso.randint(5, 20) * 480, "ROL": caso.randint(2, 10) * 60}
        for d in dati.anagrafica
    }
    scrivi_anagrafica(imp.percorsi.anagrafica, dati.anagrafica, dati.orari, capienze)

    with Archivio(imp.percorsi.archivio) as archivio:
        _pratiche_demo(archivio, dati, imp.percorsi.certificati, caso)
        _righe_demo(archivio, dati)
    log.info("Ambiente demo creato con dati finti")
    return PostaDemo(
        dati.mail_malattia[PRATICHE_IN_ARCHIVIO:],
        dati.mail_permesso[PERMESSI_IN_ARCHIVIO:],
        dati.anagrafica,
    )


def _pratiche_demo(
    archivio: Archivio, dati: DatiDemo, certificati: Path, caso: random.Random
) -> None:
    """Pratiche in tutti gli stati: incompleta, da inviare, parziale, chiusa (anche a mano)."""
    persone = {d.cf: d for d in dati.anagrafica}
    salvati: list[Certificato] = []
    for numero, mail in enumerate(dati.mail_malattia[:PRATICHE_IN_ARCHIVIO]):
        atteso, persona = mail.atteso, persone[mail.atteso["cf"]]
        inizio, fine = atteso["inizio"], atteso["fine"]
        if numero % 8 == 2:
            fine = max(fine, inizio + timedelta(days=5))  # parziale: serve la mail all'ufficio
        if numero % 8 == 0:
            fine = None  # incompleta: manca la data di fine
        giorni_episodio = None
        if fine is not None:
            certificato = Certificato(atteso["protocollo"], persona.cf, inizio, fine)
            giorni_episodio = calcola_episodio(certificato, salvati).giorni
            salvati.append(certificato)
            scrivi_certificato_finto(
                CertificatoFinto(
                    certificato.protocollo, persona.cf, persona.cognome, persona.nome, inizio, fine
                ),
                certificati / f"{certificato.protocollo}.pdf",
            )
        lunga = (giorni_episodio or 0) > archivio.soglia_ufficio
        archivio.salva_pratica(
            Pratica(
                protocollo=atteso["protocollo"],
                cf=persona.cf,
                dipendente=f"{persona.cognome} {persona.nome}",
                joborder=persona.joborder,
                cliente=persona.cliente,
                inizio=inizio,
                fine=fine,
                data_presentazione=mail.ricevuta.date(),
                giorni_episodio=giorni_episodio,
                mail_lavoratore=numero % 8 != 1,
                mail_ufficio=lunga and numero % 8 != 2,
                tempo_gestione_sec=3600 if numero % 11 == 5 else caso.randint(150, 900),
            )
        )


def _righe_demo(archivio: Archivio, dati: DatiDemo) -> None:
    persone = {d.cf: d for d in dati.anagrafica}
    tipi = {t.nome: t for t in TIPI_PREDEFINITI}
    for numero, mail in enumerate(dati.mail_permesso[:PERMESSI_IN_ARCHIVIO]):
        atteso, persona = mail.atteso, persone[mail.atteso["cf"]]
        righe = righe_giustificativo(
            tipi[atteso["tipo"]],
            atteso["giorni"],
            atteso["minuti"],
            dati.orari.get(persona.cliente),
        )
        archivio.aggiungi_righe(
            RigaSalvata(
                cf=persona.cf,
                dipendente=f"{persona.cognome} {persona.nome}",
                joborder=persona.joborder,
                cliente=persona.cliente,
                giorno=riga.giorno,
                tipo=riga.tipo,
                codice=riga.codice,
                minuti=riga.minuti,
                esportata=numero < PERMESSI_IN_ARCHIVIO // 2,
            )
            for riga in righe
        )
