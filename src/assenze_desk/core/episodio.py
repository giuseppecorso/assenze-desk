"""Episodio di malattia: certificati dello stesso CF contigui o sovrapposti.

Contigui = uno finisce il giorno prima dell'inizio dell'altro; un giorno di pausa
separa gli episodi. L'archivio dei certificati arriva come dato: il core non
legge database né file. La mail all'ufficio (oltre la soglia di giorni, vedi
stato.py) allega i PDF di tutti i certificati dell'episodio.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

UN_GIORNO = timedelta(days=1)


@dataclass(frozen=True)
class Certificato:
    protocollo: str
    cf: str
    inizio: date
    fine: date

    def __post_init__(self) -> None:
        if self.fine < self.inizio:
            raise ValueError(f"certificato {self.protocollo}: la fine viene prima dell'inizio")

    @property
    def cf_pulito(self) -> str:
        return self.cf.strip().upper()


@dataclass(frozen=True)
class Episodio:
    certificati: tuple[Certificato, ...]  # in ordine di inizio

    @property
    def inizio(self) -> date:
        return min(c.inizio for c in self.certificati)

    @property
    def fine(self) -> date:
        return max(c.fine for c in self.certificati)

    @property
    def giorni(self) -> int:
        return (self.fine - self.inizio).days + 1

    @property
    def protocolli(self) -> tuple[str, ...]:
        """Protocolli dei certificati da allegare alla mail all'ufficio."""
        return tuple(c.protocollo for c in self.certificati)


def calcola_episodio(certificato: Certificato, archivio: Iterable[Certificato]) -> Episodio:
    """L'episodio del certificato, allargato finché trova certificati che lo toccano."""
    candidati = {
        c.protocollo: c
        for c in archivio
        if c.cf_pulito == certificato.cf_pulito and c.protocollo != certificato.protocollo
    }
    dentro = [certificato]
    inizio, fine = certificato.inizio, certificato.fine
    allargato = True
    while allargato:
        allargato = False
        for protocollo, altro in list(candidati.items()):
            if altro.fine >= inizio - UN_GIORNO and altro.inizio <= fine + UN_GIORNO:
                dentro.append(candidati.pop(protocollo))
                inizio, fine = min(inizio, altro.inizio), max(fine, altro.fine)
                allargato = True
    return Episodio(tuple(sorted(dentro, key=lambda c: (c.inizio, c.protocollo))))


def certificato_precedente(
    certificato: Certificato, archivio: Iterable[Certificato]
) -> Certificato | None:
    """Il certificato dello stesso CF che finisce il giorno prima (il più recente)."""
    precedenti = [
        c
        for c in archivio
        if c.cf_pulito == certificato.cf_pulito
        and c.protocollo != certificato.protocollo
        and c.fine == certificato.inizio - UN_GIORNO
    ]
    return max(precedenti, key=lambda c: (c.inizio, c.protocollo), default=None)
