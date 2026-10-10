"""Divisione del testo di una mail in oggetto, corpo e intestazioni.

Il testo può arrivare da Outlook, da un incolla o dall'OCR, quindi le righe
"Oggetto:", "Da:", "Data:"... si riconoscono ovunque, anche dentro una mail
inoltrata. Le altre regole cercano i dati per sezione: per esempio il protocollo
si cerca prima nel corpo, il JobOrder prima nell'oggetto.
"""

import re
from dataclasses import dataclass

_OGGETTO = re.compile(r"^(?:oggetto|ogg|subject)\s*:\s*(.*)$", re.IGNORECASE)
# Prima riga di una risposta o di un inoltro: "R: ...", "RE: ...", "I: ...", "FW: ..."
_RISPOSTA = re.compile(r"^(?:r|re|i|fw|fwd)\s*:\s*(.+)$", re.IGNORECASE)
_INTESTAZIONE = re.compile(
    r"^(?:da|from|a|to|cc|ccn|bcc|data|date|inviato|sent)\s*:", re.IGNORECASE
)
# Indirizzi interni di Exchange: "/o=.../ou=.../cn=..."
_EXCHANGE = re.compile(r"^/o=|/ou=|/cn=", re.IGNORECASE)


@dataclass(frozen=True)
class MailStrutturata:
    oggetto: str
    corpo: str
    intestazioni: str


def dividi_mail(testo: str) -> MailStrutturata:
    """Il primo "Oggetto:" è l'oggetto; i successivi finiscono tra le intestazioni."""
    oggetto = ""
    corpo: list[str] = []
    intestazioni: list[str] = []
    prima_riga = True

    for riga in testo.replace("\r\n", "\n").split("\n"):
        pulita = riga.strip()
        if not pulita:
            corpo.append("")
            continue
        era_la_prima, prima_riga = prima_riga, False

        nuovo_oggetto = None
        if not oggetto:
            nuovo_oggetto = _OGGETTO.match(pulita) or (era_la_prima and _RISPOSTA.match(pulita))

        if nuovo_oggetto:
            oggetto = nuovo_oggetto.group(1).strip()
        elif _OGGETTO.match(pulita) or _INTESTAZIONE.match(pulita) or _EXCHANGE.search(pulita):
            intestazioni.append(pulita)
        else:
            corpo.append(riga.rstrip())

    return MailStrutturata(oggetto, "\n".join(corpo).strip(), "\n".join(intestazioni))
