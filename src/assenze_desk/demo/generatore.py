"""Generatore di dati finti: anagrafica, orari dei clienti, mail di malattia e di permesso.

Privacy by design:
- i codici fiscali sono formalmente validi ma con luogo di nascita Z999, che non
  esiste: nessun CF generato può appartenere a una persona vera;
- le email sono tutte @example.com, i clienti sono nomi di fantasia;
- a parità di seme i dati sono sempre gli stessi (test ripetibili).

Ogni mail porta con sé i valori attesi (`atteso`), così i test verificano che il
core la legga correttamente. La data di riferimento arriva come argomento.
"""

import random
import string
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from typing import Any

from assenze_desk.core.codice_fiscale import carattere_di_controllo
from assenze_desk.core.dipendenti import Dipendente
from assenze_desk.core.turni import OrarioSettimanale

COGNOMI = (
    "Fittizio",
    "Esempio",
    "Inventato",
    "Simulato",
    "Ipotetico",
    "Provvisorio",
    "Fantasia",
    "Campione",
    "Immaginario",
    "Prototipo",
)
NOMI = (
    ("Luca", "M"),
    ("Marco", "M"),
    ("Paolo", "M"),
    ("Davide", "M"),
    ("Stefano", "M"),
    ("Anna", "F"),
    ("Giulia", "F"),
    ("Sara", "F"),
    ("Elena", "F"),
    ("Chiara", "F"),
)
COPIE_CLIENTI = {
    "Alfa Srl": "personale.alfa@example.com",
    "Beta Spa": "personale.beta@example.com",
    "Gamma Srl": "personale.gamma@example.com",
    "Delta Coop": "personale.delta@example.com",
}
ORARI_CLIENTI = {
    "Alfa Srl": OrarioSettimanale((480, 480, 480, 480, 480, 0, 0)),
    "Beta Spa": OrarioSettimanale((480, 480, 480, 480, 480, 240, 0)),
    "Gamma Srl": OrarioSettimanale((360, 360, 360, 360, 360, 0, 0)),
    "Delta Coop": OrarioSettimanale((420, 420, 420, 420, 420, 420, 0)),
}
LUOGO_INESISTENTE = "Z999"
_MESI_CF = "ABCDEHLMPRST"


@dataclass(frozen=True)
class MailDemo:
    mittente: str
    ricevuta: datetime
    testo: str
    atteso: dict[str, Any] = field(compare=True)


@dataclass(frozen=True)
class DatiDemo:
    anagrafica: tuple[Dipendente, ...]
    orari: dict[str, OrarioSettimanale]
    mail_malattia: tuple[MailDemo, ...]
    mail_permesso: tuple[MailDemo, ...]


def genera_dati(
    oggi: date,
    seme: int = 0,
    dipendenti: int = 20,
    mail_malattia: int = 15,
    mail_permesso: int = 15,
) -> DatiDemo:
    caso = random.Random(seme)
    anagrafica = _anagrafica(caso, oggi, dipendenti)
    return DatiDemo(
        anagrafica=anagrafica,
        orari=dict(ORARI_CLIENTI),
        mail_malattia=tuple(
            _mail_malattia(caso, oggi, caso.choice(anagrafica)) for _ in range(mail_malattia)
        ),
        mail_permesso=tuple(
            _mail_permesso(caso, oggi, caso.choice(anagrafica), n) for n in range(mail_permesso)
        ),
    )


def cf_finto(caso: random.Random, sesso: str) -> str:
    """CF valido con luogo di nascita inesistente (Z999)."""
    giorno = caso.randint(1, 28) + (40 if sesso == "F" else 0)
    primi_15 = (
        "".join(caso.choices(string.ascii_uppercase, k=6))
        + f"{caso.randint(60, 99):02d}"
        + caso.choice(_MESI_CF)
        + f"{giorno:02d}"
        + LUOGO_INESISTENTE
    )
    return primi_15 + carattere_di_controllo(primi_15)


def _anagrafica(caso: random.Random, oggi: date, quanti: int) -> tuple[Dipendente, ...]:
    righe: list[Dipendente] = []
    codici: set[str] = set()
    for numero in range(quanti):
        nome, sesso = caso.choice(NOMI)
        cognome = caso.choice(COGNOMI)
        cf = cf_finto(caso, sesso)
        while cf in codici:  # doppione: capita una volta su miliardi
            cf = cf_finto(caso, sesso)  # pragma: no cover
        codici.add(cf)
        dipendente = Dipendente(
            cf=cf,
            cognome=cognome,
            nome=nome,
            email=f"{nome}.{cognome}{numero}@example.com".lower(),
            joborder=f"20{caso.randint(0, 9_999_999):07d}",
            cliente=caso.choice(tuple(ORARI_CLIENTI)),
            inizio_joborder=oggi - timedelta(days=caso.randint(30, 300)),
            fine_joborder=oggi + timedelta(days=caso.randint(90, 300)),
        )
        # Lista del cliente in copia nelle risposte (colonna DL)
        righe.append(replace(dipendente, copia_cliente=COPIE_CLIENTI[dipendente.cliente]))
    return tuple(righe)


def _ricevuta(caso: random.Random, oggi: date) -> datetime:
    """Una mattina di lunedì, martedì o mercoledì delle ultime settimane."""
    giorno = oggi - timedelta(days=caso.randint(0, 40))
    while giorno.weekday() > 2:
        giorno -= timedelta(days=1)
    return datetime.combine(giorno, time(caso.randint(8, 11), caso.randint(0, 59)))


def _intestazione(dipendente: Dipendente, ricevuta: datetime, oggetto: str) -> str:
    return (
        f"OGG: {oggetto}\n"
        f"Da: {dipendente.nome} {dipendente.cognome} <{dipendente.email}>\n"
        f"Data: {ricevuta:%d/%m/%Y %H:%M}\n\n"
    )


def _firma(dipendente: Dipendente) -> str:
    return f"\n\nCordiali saluti\n{dipendente.nome} {dipendente.cognome}"


def _mail_malattia(caso: random.Random, oggi: date, dipendente: Dipendente) -> MailDemo:
    ricevuta = _ricevuta(caso, oggi)
    protocollo = f"4{caso.randint(0, 99_999_999):08d}"
    scritto = caso.choice(
        (
            protocollo,
            f"{protocollo[:3]} {protocollo[3:6]} {protocollo[6:]}",
            f"{protocollo[:3]}-{protocollo[3:6]}-{protocollo[6:]}",
        )
    )
    dal = ricevuta.date() - timedelta(days=caso.randint(0, 2))
    al = dal + timedelta(days=caso.randint(0, 9))
    testo = (
        _intestazione(dipendente, ricevuta, f"Certificato di malattia {dipendente.cognome}")
        + "Buongiorno,\ninvio il certificato di malattia.\n"
        + f"Protocollo: {scritto}\n"
        + f"Codice fiscale: {dipendente.cf}\n"
        + f"JobOrder {dipendente.joborder}\n"
        + f"Periodo dal {dal:%d/%m/%Y} al {al:%d/%m/%Y}."
        + _firma(dipendente)
    )
    atteso = {
        "protocollo": protocollo,
        "cf": dipendente.cf,
        "joborder": dipendente.joborder,
        "inizio": dal,
        "fine": al,
    }
    return MailDemo(dipendente.email, ricevuta, testo, atteso)


def _mail_permesso(
    caso: random.Random, oggi: date, dipendente: Dipendente, numero: int
) -> MailDemo:
    ricevuta = _ricevuta(caso, oggi)
    domani = ricevuta.date() + timedelta(days=1)
    tra_due_giorni = ricevuta.date() + timedelta(days=2)
    lunedi_prossimo = ricevuta.date() + timedelta(days=7 - ricevuta.weekday())
    venerdi_prossimo = lunedi_prossimo + timedelta(days=4)

    modelli = [
        (
            "Richiesta ROL",
            "chiedo un permesso ROL per domani dalle 9 alle 11.",
            "ROL",
            (domani,),
            120,
        ),
        (
            "Richiesta ROL",
            f"vorrei 2 ore di ROL il {tra_due_giorni:%d/%m/%Y}.",
            "ROL",
            (tra_due_giorni,),
            120,
        ),
        (
            "Permesso visita medica",
            "domani ho una visita medica dalle 14:30 alle 16:30, chiedo il permesso.",
            "Permesso visita medica",
            (domani,),
            120,
        ),
        (
            "Richiesta ferie",
            f"chiedo le ferie dal {lunedi_prossimo:%d/%m/%Y} al {venerdi_prossimo:%d/%m/%Y}.",
            "Ferie",
            tuple(lunedi_prossimo + timedelta(days=n) for n in range(5)),
            None,
        ),
        (
            "Uscita anticipata",
            "domani avrei bisogno di un'uscita anticipata: esco alle 16 anziché alle 18.",
            "ROL",
            (domani,),
            120,
        ),
    ]
    oggetto, corpo, tipo, giorni, minuti = modelli[numero % len(modelli)]
    testo = (
        _intestazione(dipendente, ricevuta, oggetto) + "Buongiorno,\n" + corpo + _firma(dipendente)
    )
    atteso = {"cf": dipendente.cf, "tipo": tipo, "giorni": giorni, "minuti": minuti}
    return MailDemo(dipendente.email, ricevuta, testo, atteso)
