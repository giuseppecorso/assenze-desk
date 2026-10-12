"""Match del dipendente con l'anagrafica e ricerca manuale.

Una riga di anagrafica è un dipendente su un JobOrder: la stessa persona può
avere più righe (più JobOrder, più clienti). L'anagrafica arriva come dato.

Fonti, in ordine (ci si ferma alla prima che dà candidati):
1. JobOrder; 2. mittente, escluse le mail interne (se il mittente è interno si
cercano gli indirizzi nel testo); 3. codice fiscale; 4. nomi nel testo: nome e
cognome nell'oggetto o nel nome del mittente, poi nel corpo; il solo cognome dà
solo suggerimenti. Le righe di saluto ("Buongiorno Anna ...") si ignorano:
nominano chi riceve la mail.

Con più candidati: JobOrder attivo nel periodo, poi cliente citato nel testo,
altrimenti sceglie l'utente. Il CF non compare mai nei messaggi (privacy).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from assenze_desk.core.mail import dividi_mail
from assenze_desk.core.testo import normalizza

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SALUTO = re.compile(
    r"^\s*(?:ciao|buongiorno|buonasera|salve|gentile|gentili|egregio|spett|"
    r"alla\s+cortese|hello|hi)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Dipendente:
    cf: str
    cognome: str
    nome: str
    email: str = ""
    joborder: str = ""
    cliente: str = ""
    inizio_joborder: date | None = None
    fine_joborder: date | None = None
    copia_cliente: str = ""  # indirizzi del cliente in copia nelle risposte (lista DL)

    def __post_init__(self) -> None:
        if not self.cf.strip():
            raise ValueError("ogni riga di anagrafica deve avere il codice fiscale")


@dataclass(frozen=True)
class EsitoMatch:
    dipendente: Dipendente | None  # scelto in automatico, se il match è sicuro
    candidati: tuple[Dipendente, ...]  # da proporre all'utente
    motivo: str  # da dove viene il match, senza dati personali


Periodo = tuple[date, date]


def attivo_nel_periodo(dipendente: Dipendente, periodo: Periodo | None) -> bool:
    """Il JobOrder copre almeno un giorno del periodo (senza date: sempre attivo)."""
    if periodo is None:
        return True
    inizio, fine = periodo
    if dipendente.inizio_joborder and fine < dipendente.inizio_joborder:
        return False
    return not (dipendente.fine_joborder and inizio > dipendente.fine_joborder)


def trova_dipendente(
    anagrafica: Sequence[Dipendente],
    *,
    testo: str = "",
    mittente: str = "",
    cf: str = "",
    joborder: str = "",
    periodo: Periodo | None = None,
    domini_interni: Sequence[str] = (),
) -> EsitoMatch:
    fonti = [
        ("JobOrder", [d for d in anagrafica if joborder and d.joborder == joborder.strip()], True),
        ("mittente", _per_mittente(anagrafica, mittente, testo, domini_interni), True),
        ("codice fiscale", [d for d in anagrafica if cf and _cf(d.cf) == _cf(cf)], True),
    ]
    per_nome, sicuro = _per_nome(anagrafica, testo)
    fonti.append(("nome nel testo", per_nome, sicuro))

    for fonte, candidati, automatico in fonti:
        if candidati:
            return _scegli(candidati, testo, periodo, fonte, automatico)
    return EsitoMatch(None, (), "")


def cerca_dipendenti(anagrafica: Sequence[Dipendente], ricerca: str) -> list[Dipendente]:
    """Righe che contengono tutte le parole cercate (cognome, nome, CF, JobOrder, cliente)."""
    parole = normalizza(ricerca).split()
    if not parole:
        return []
    return [
        d
        for d in anagrafica
        if all(
            parola in normalizza(f"{d.cognome} {d.nome} {d.cf} {d.joborder} {d.cliente}")
            for parola in parole
        )
    ]


def _cf(valore: str) -> str:
    return valore.strip().upper()


def indirizzo_interno(email: str, domini_interni: Sequence[str]) -> bool:
    dominio = email.rpartition("@")[2].lower()
    return any(dominio == d.lower() or dominio.endswith("." + d.lower()) for d in domini_interni)


def _per_mittente(
    anagrafica: Sequence[Dipendente], mittente: str, testo: str, domini_interni: Sequence[str]
) -> list[Dipendente]:
    indirizzi = [mittente] if mittente.strip() else []
    indirizzi += _EMAIL.findall(testo)
    for indirizzo in indirizzi:
        indirizzo = indirizzo.strip().lower()
        if indirizzo_interno(indirizzo, domini_interni):
            continue
        trovati = [d for d in anagrafica if d.email and d.email.strip().lower() == indirizzo]
        if trovati:
            return trovati
    return []


def _per_nome(anagrafica: Sequence[Dipendente], testo: str) -> tuple[list[Dipendente], bool]:
    """Candidati dal nome, e se il match è abbastanza sicuro per sceglierlo da solo."""
    mail = dividi_mail(testo)
    corpo = "\n".join(riga for riga in mail.corpo.splitlines() if not _SALUTO.match(riga))
    oggetto = f" {normalizza(mail.oggetto)} {normalizza(_nome_mittente(mail.intestazioni))} "
    corpo = f" {normalizza(corpo)} "

    livelli: list[list[Dipendente]] = [[], [], [], []]
    for d in anagrafica:
        cognome, nome = normalizza(d.cognome), normalizza(d.nome)
        if not cognome:
            continue
        completi = [f" {cognome} {nome} ", f" {nome} {cognome} "] if nome else []
        if any(c in oggetto for c in completi):
            livelli[0].append(d)
        elif any(c in corpo for c in completi):
            livelli[1].append(d)
        elif f" {cognome} " in oggetto:
            livelli[2].append(d)
        elif f" {cognome} " in corpo:
            livelli[3].append(d)

    for numero, livello in enumerate(livelli):
        if livello:
            return livello, numero < 2  # il solo cognome non basta per scegliere
    return [], False


def _nome_mittente(intestazioni: str) -> str:
    for riga in intestazioni.splitlines():
        if re.match(r"^\s*(?:da|from)\s*:", riga, re.IGNORECASE):
            valore = riga.split(":", 1)[1]
            return _EMAIL.sub(" ", valore).replace("<", " ").replace(">", " ")
    return ""


def _scegli(
    candidati: list[Dipendente],
    testo: str,
    periodo: Periodo | None,
    fonte: str,
    automatico: bool,
) -> EsitoMatch:
    unici = list(dict.fromkeys(candidati))
    attivi = [d for d in unici if attivo_nel_periodo(d, periodo)] or unici
    if len(attivi) == 1 and automatico:
        motivo = f"{fonte}, JobOrder attivo nel periodo" if len(unici) > 1 else fonte
        return EsitoMatch(attivi[0], tuple(attivi), motivo)

    normalizzato = f" {normalizza(testo)} "
    citati = [d for d in attivi if d.cliente and f" {normalizza(d.cliente)} " in normalizzato]
    if len(citati) == 1 and automatico:
        return EsitoMatch(citati[0], tuple(citati), f"{fonte}, cliente citato nel testo")
    return EsitoMatch(None, tuple(citati or attivi), fonte)
