"""Risposta alla mail di malattia: a chi, con chi in copia, da quale casella.

- Al lavoratore: il suo indirizzo (o il mittente, senza anagrafica), la lista
  del cliente (DL) in copia e, se l'utente lo ha scelto, la risposta dalla
  casella del cliente, il primo indirizzo della lista. Come nella v6.20.
- A un collega che ha girato il certificato: risposta breve a lui, senza il
  cliente in copia, dalla casella scelta per i colleghi (vuota = predefinita).

La modalità collega si propone quando il mittente ha un dominio interno e non
è il lavoratore; l'utente può sempre cambiarla.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from assenze_desk.core.dipendenti import Dipendente, indirizzo_interno

_SEPARATORI = re.compile(r"[;,]")


@dataclass(frozen=True)
class Risposta:
    a: tuple[str, ...]
    cc: tuple[str, ...]
    mittente: str  # vuoto = la casella predefinita di Outlook
    collega: bool


def indirizzi(testo: str) -> tuple[str, ...]:
    """Indirizzi separati da ";" o ",", senza vuoti e senza doppioni (maiuscole indifferenti)."""
    visti: dict[str, str] = {}
    for pezzo in _SEPARATORI.split(testo):
        indirizzo = pezzo.strip()
        if indirizzo and indirizzo.lower() not in visti:
            visti[indirizzo.lower()] = indirizzo
    return tuple(visti.values())


def scegli_risposta(
    *,
    dipendente: Dipendente | None,
    mittente_mail: str,
    collega: bool = False,
    dalla_lista_cliente: bool = False,
    mittente_collega: str = "",
) -> Risposta:
    if collega:
        return Risposta(indirizzi(mittente_mail), (), mittente_collega.strip(), True)
    destinatario = (dipendente.email if dipendente else "") or mittente_mail
    copia = indirizzi(dipendente.copia_cliente) if dipendente else ()
    mittente = copia[0] if dalla_lista_cliente and copia else ""
    return Risposta(indirizzi(destinatario), copia, mittente, False)


def da_collega(
    mittente_mail: str, dipendente: Dipendente | None, domini_interni: Sequence[str]
) -> bool:
    mittente = mittente_mail.strip().lower()
    if not mittente or not indirizzo_interno(mittente, domini_interni):
        return False
    return not (dipendente and dipendente.email.strip().lower() == mittente)
