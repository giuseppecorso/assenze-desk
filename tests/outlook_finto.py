"""Outlook finto per i test: imita gli oggetti COM usati dall'adapter.

Non invia mai: chiamare Send() fa fallire il test (le mail restano bozze, D2).
"""

from datetime import datetime


class Raccolta:
    """Come le collezioni COM: Count, Item(1-based o per nome)."""

    def __init__(self, elementi=()):
        self.elementi = list(elementi)

    @property
    def Count(self):
        return len(self.elementi)

    def Item(self, chiave):
        if isinstance(chiave, int):
            return self.elementi[chiave - 1]
        for elemento in self.elementi:
            if elemento.Name.lower() == chiave.lower():
                return elemento
        raise LookupError(chiave)  # come l'errore COM


class Allegato:
    def __init__(self, nome, contenuto=b"%PDF-finto"):
        self.FileName = nome
        self.contenuto = contenuto

    def SaveAsFile(self, percorso):
        with open(percorso, "wb") as file:
            file.write(self.contenuto)


class Cartella:
    def __init__(self, nome, sottocartelle=()):
        self.Name = nome
        self.madre = None
        self.Folders = Raccolta(sottocartelle)
        for sottocartella in sottocartelle:
            sottocartella.madre = self

    @property
    def FolderPath(self):
        if self.madre is None:
            return f"\\\\{self.Name}"  # la casella di posta: \\casella
        return f"{self.madre.FolderPath}\\{self.Name}"


class Bozza:
    def __init__(self):
        self.To = ""
        self.CC = ""
        self.SentOnBehalfOfName = ""
        self.Subject = ""
        self.HTMLBody = ""
        self.Attachments = RaccoltaAllegatiBozza()
        self.mostrata = False

    def Display(self, modale=False):
        self.mostrata = True

    def Send(self):
        raise AssertionError("una bozza non deve mai essere inviata")


class RaccoltaAllegatiBozza:
    def __init__(self):
        self.percorsi = []

    def Add(self, percorso):
        self.percorsi.append(percorso)


class Mittente:
    def __init__(self, smtp):
        self.smtp = smtp

    def GetExchangeUser(self):
        return type("UtenteExchange", (), {"PrimarySmtpAddress": self.smtp})()


class Mail:
    def __init__(self, entry_id, oggetto, corpo="testo", mittente="a@example.com", allegati=()):
        self.EntryID = entry_id
        self.Subject = oggetto
        self.Body = corpo
        self.SenderEmailAddress = mittente
        self.Sender = Mittente("persona@example.com")
        self.ReceivedTime = datetime(2026, 10, 7, 9, 15, 30)
        self.Parent = type("Cartella", (), {"StoreID": "STORE-1"})()
        self.Attachments = Raccolta(allegati)
        self.risposte = []
        self.spostata_in = None

    def Reply(self):
        bozza = Bozza()
        bozza.Subject = f"R: {self.Subject}"
        bozza.HTMLBody = "<p>messaggio originale</p>"
        self.risposte.append(bozza)
        return bozza

    def Move(self, destinazione):
        self.spostata_in = destinazione
        return self


class Namespace:
    def __init__(self, app):
        self.app = app
        self.posta_in_arrivo = Cartella(
            "Posta in arrivo", [Cartella("Gestite", [Cartella("Malattie")])]
        )
        self.Folders = Raccolta([Cartella("casella", [self.posta_in_arrivo])])

    def GetItemFromID(self, entry_id, store_id=None):
        for mail in self.app.mail:
            if mail.EntryID == entry_id:
                return mail
        raise LookupError("elemento non trovato")  # come l'errore COM

    def GetDefaultFolder(self, numero):
        assert numero == 6  # olFolderInbox
        return self.posta_in_arrivo


class OutlookFinto:
    def __init__(self, *mail):
        self.mail = list(mail)
        self.selezione = Raccolta(mail[:1])
        self.explorer_attivo = True
        self.bozze_nuove = []
        self.namespace = Namespace(self)

    def ActiveExplorer(self):
        if not self.explorer_attivo:
            return None
        return type("Explorer", (), {"Selection": self.selezione})()

    def GetNamespace(self, nome):
        assert nome == "MAPI"
        return self.namespace

    def CreateItem(self, tipo):
        assert tipo == 0  # olMailItem
        bozza = Bozza()
        self.bozze_nuove.append(bozza)
        return bozza

    def seleziona(self, mail):
        self.selezione = Raccolta([mail])
