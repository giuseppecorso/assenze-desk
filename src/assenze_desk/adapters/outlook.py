"""Outlook Classic via COM (pywin32): import della mail, allegati, bozze, spostamento.

Regole:
- tutto lavora sulla mail importata, ritrovata con il suo EntryID: se nel
  frattempo in Outlook si seleziona un'altra mail, la risposta va comunque alla
  mail importata (problema noto 3). Se la mail non si trova più, è un errore:
  mai ripiegare sulla selezione;
- si creano solo bozze (Display), mai invii (D2).

L'applicazione Outlook si può passare dall'esterno (nei test, un Outlook finto);
altrimenti si collega a quella aperta sul PC.
"""

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CARTELLA_POSTA_IN_ARRIVO = 6  # olFolderInbox
NUOVA_MAIL = 0  # olMailItem


class ErroreOutlook(Exception):
    """Problema con Outlook: il messaggio è pronto da mostrare all'utente."""


@dataclass(frozen=True)
class MailImportata:
    oggetto: str
    corpo: str
    mittente: str
    ricevuta: datetime
    entry_id: str
    store_id: str

    @property
    def testo(self) -> str:
        """Il testo da analizzare, con le intestazioni che il core riconosce."""
        return (
            f"OGG: {self.oggetto}\nDa: {self.mittente}\nData: {self.ricevuta:%d/%m/%Y %H:%M}\n\n"
            f"{self.corpo}"
        )


class Outlook:
    def __init__(self, applicazione: Any = None) -> None:
        self._applicazione = applicazione
        self._reale = applicazione is None

    # --- Lettura ---

    def mail_selezionata(self) -> MailImportata:
        with self._app() as app:
            explorer = app.ActiveExplorer()
            if explorer is None:
                raise ErroreOutlook(
                    "Outlook non mostra nessuna cartella: "
                    "apri la Posta in arrivo e seleziona una mail."
                )
            selezione = explorer.Selection
            if selezione is None or selezione.Count == 0:
                raise ErroreOutlook(
                    "Nessuna mail selezionata: seleziona una mail in Outlook e riprova."
                )
            mail = selezione.Item(1)
            ricevuta = mail.ReceivedTime
            return MailImportata(
                oggetto=str(mail.Subject or ""),
                corpo=str(mail.Body or ""),
                mittente=_mittente(mail),
                ricevuta=datetime(
                    ricevuta.year,
                    ricevuta.month,
                    ricevuta.day,
                    ricevuta.hour,
                    ricevuta.minute,
                    ricevuta.second,
                ),
                entry_id=str(mail.EntryID),
                store_id=str(getattr(mail.Parent, "StoreID", "") or ""),
            )

    def salva_allegati(self, mail: MailImportata, cartella: Path) -> list[Path]:
        cartella = Path(cartella)
        cartella.mkdir(parents=True, exist_ok=True)
        salvati = []
        with self._app() as app:
            originale = self._ritrova(app, mail)
            allegati = originale.Attachments
            for numero in range(1, allegati.Count + 1):
                allegato = allegati.Item(numero)
                destinazione = _nome_libero(
                    cartella / str(allegato.FileName or f"allegato_{numero}")
                )
                allegato.SaveAsFile(str(destinazione))
                salvati.append(destinazione)
        log.info("Salvati %d allegati della mail importata", len(salvati))
        return salvati

    # --- Bozze: mai invii ---

    def bozza_risposta(self, mail: MailImportata, corpo_html: str, cc: Sequence[str] = ()) -> None:
        with self._app() as app:
            risposta = self._ritrova(app, mail).Reply()
            risposta.HTMLBody = corpo_html + (risposta.HTMLBody or "")
            if cc:
                risposta.CC = "; ".join(cc)
            risposta.Display(False)

    def bozza_nuova(
        self,
        a: Sequence[str],
        oggetto: str,
        corpo_html: str,
        cc: Sequence[str] = (),
        allegati: Sequence[Path] = (),
    ) -> None:
        with self._app() as app:
            bozza = app.CreateItem(NUOVA_MAIL)
            bozza.To = "; ".join(a)
            if cc:
                bozza.CC = "; ".join(cc)
            bozza.Subject = oggetto
            bozza.HTMLBody = corpo_html
            for percorso in allegati:
                bozza.Attachments.Add(str(percorso))
            bozza.Display(False)

    # --- Spostamento ---

    def sposta(self, mail: MailImportata, percorso_cartella: str) -> str:
        """Sposta la mail importata; il percorso è relativo alla Posta in arrivo
        ("Gestite/Malattie") oppure completo ("\\\\casella\\Posta in arrivo\\...")."""
        with self._app() as app:
            namespace = app.GetNamespace("MAPI")
            destinazione = _cartella(namespace, percorso_cartella)
            self._ritrova(app, mail).Move(destinazione)
            return str(destinazione.FolderPath)

    # --- Interni ---

    @contextmanager
    def _app(self) -> Iterator[Any]:
        if not self._reale:
            yield self._applicazione
            return
        yield from _outlook_reale()  # pragma: no cover - solo su Windows con Outlook

    def _ritrova(self, app: Any, mail: MailImportata) -> Any:
        namespace = app.GetNamespace("MAPI")
        try:
            if mail.store_id:
                return namespace.GetItemFromID(mail.entry_id, mail.store_id)
            return namespace.GetItemFromID(mail.entry_id)  # pragma: no cover
        except Exception as errore:
            log.warning("Mail importata non trovata in Outlook: %s", errore)
            raise ErroreOutlook(
                "La mail importata non è più in Outlook (spostata o eliminata?): "
                "importala di nuovo."
            ) from errore


def _outlook_reale() -> Iterator[Any]:  # pragma: no cover - solo su Windows con Outlook
    try:
        import pythoncom
        import win32com.client
    except ImportError as errore:
        raise ErroreOutlook(
            "Manca pywin32: l'integrazione con Outlook funziona solo su Windows."
        ) from errore
    pythoncom.CoInitialize()
    try:
        try:
            app = win32com.client.GetActiveObject("Outlook.Application")
        except Exception:  # noqa: BLE001 - Outlook non aperto: si prova ad avviarlo
            try:
                app = win32com.client.Dispatch("Outlook.Application")
            except Exception as errore:
                raise ErroreOutlook("Outlook Classic non è disponibile su questo PC.") from errore
        yield app
    finally:
        pythoncom.CoUninitialize()


def _mittente(mail: Any) -> str:
    indirizzo = str(mail.SenderEmailAddress or "").strip()
    if indirizzo.lower().startswith("/o="):  # indirizzo interno di Exchange
        try:
            indirizzo = str(mail.Sender.GetExchangeUser().PrimarySmtpAddress or "")
        except Exception:  # noqa: BLE001 - utente Exchange non risolvibile
            log.info("Indirizzo Exchange del mittente non risolto")
            indirizzo = ""
    return indirizzo.lower()


def _cartella(namespace: Any, percorso: str) -> Any:
    parti = [p for p in percorso.replace("/", "\\").split("\\") if p]
    if percorso.startswith("\\\\"):
        cartella, parti = _sottocartella(namespace.Folders, parti[0], percorso), parti[1:]
    else:
        cartella = namespace.GetDefaultFolder(CARTELLA_POSTA_IN_ARRIVO)
    for nome in parti:
        cartella = _sottocartella(cartella.Folders, nome, percorso)
    return cartella


def _sottocartella(cartelle: Any, nome: str, percorso: str) -> Any:
    try:
        return cartelle.Item(nome)
    except Exception as errore:
        raise ErroreOutlook(
            f"Cartella di Outlook non trovata: '{nome}' in '{percorso}'."
        ) from errore


def _nome_libero(percorso: Path) -> Path:
    """Il percorso, oppure "nome (2).pdf", "nome (3).pdf"... se esiste già."""
    numero = 2
    libero = percorso
    while libero.exists():
        libero = percorso.with_name(f"{percorso.stem} ({numero}){percorso.suffix}")
        numero += 1
    return libero
