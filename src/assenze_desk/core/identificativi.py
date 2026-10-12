"""Protocollo e JobOrder: numeri a cifre fisse, riconosciuti dal prefisso.

Un numero può essere scritto a pezzi separati da uno spazio o da un trattino
("412 345 678", "412-345-678"). Punti e barre no: si confondono con le date.

Con più numeri candidati si sceglie a livelli:
1. i numeri sulla riga di una parola chiave o sulla riga subito dopo,
   nell'ordine delle sezioni;
2. gli altri numeri, nell'ordine delle sezioni;
3. i numeri nelle intestazioni (Da, Data, ...).
A parità di livello vince il primo nel testo.
Ordine delle sezioni: protocollo corpo e oggetto; JobOrder oggetto e corpo.
Se non c'è nessun candidato il risultato è None: meglio vuoto che sbagliato.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass

from assenze_desk.core.mail import dividi_mail


@dataclass(frozen=True)
class RegolaNumero:
    """Impostazioni di un numero: lunghezza, prefissi ammessi, parole chiave."""

    lunghezza: int
    prefissi: tuple[str, ...]
    parole_chiave: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.lunghezza < 1:
            raise ValueError(f"lunghezza non valida: {self.lunghezza}")
        if not self.prefissi:
            raise ValueError("serve almeno un prefisso")
        for prefisso in self.prefissi:
            if not re.fullmatch(r"[0-9]+", prefisso) or len(prefisso) > self.lunghezza:
                raise ValueError(f"prefisso non valido: {prefisso!r}")


PROTOCOLLO = RegolaNumero(
    lunghezza=9,
    prefissi=("4",),
    parole_chiave=("protocollo", "prot", "puc", "certificato", "malattia", "inps"),
)
JOBORDER = RegolaNumero(
    lunghezza=9,
    prefissi=("20",),
    parole_chiave=("joborder", "job order", "job"),
)


def estrai_joborder(testo: str, regola: RegolaNumero = JOBORDER) -> str | None:
    mail = dividi_mail(testo)
    return _scegli((mail.oggetto, mail.corpo), mail.intestazioni, regola)


def estrai_protocollo(
    testo: str,
    regola: RegolaNumero = PROTOCOLLO,
    regola_joborder: RegolaNumero = JOBORDER,
) -> str | None:
    """Il protocollo non è mai uguale al JobOrder trovato nello stesso testo."""
    mail = dividi_mail(testo)
    joborder = estrai_joborder(testo, regola_joborder)
    return _scegli((mail.corpo, mail.oggetto), mail.intestazioni, regola, escluso=joborder)


def pulisci_protocollo(scritto: str) -> str:
    """Protocollo scritto a mano: via spazi, trattini e punti se resta solo un numero.
    Altrimenti resta com'è, così l'utente vede l'avviso e corregge."""
    scritto = scritto.strip()
    cifre = re.sub(r"[\s.\-]", "", scritto)
    return cifre if cifre.isdigit() else scritto


def _scegli(
    sezioni: tuple[str, ...],
    intestazioni: str,
    regola: RegolaNumero,
    escluso: str | None = None,
) -> str | None:
    parola_chiave = _pattern_parole_chiave(regola.parole_chiave)
    candidati: list[tuple[int, int, str]] = []  # (livello, posizione, numero)

    for indice, sezione in enumerate(sezioni):
        righe_con_chiave = {
            numero
            for numero, riga in enumerate(sezione.split("\n"))
            if parola_chiave and parola_chiave.search(riga)
        }
        for numero, inizio in _validi(sezione, regola, escluso):
            riga = sezione.count("\n", 0, inizio)
            vicino = riga in righe_con_chiave or (riga - 1) in righe_con_chiave
            livello = indice if vicino else len(sezioni) + indice
            candidati.append((livello, inizio, numero))

    for numero, inizio in _validi(intestazioni, regola, escluso):
        candidati.append((2 * len(sezioni), inizio, numero))

    return min(candidati)[2] if candidati else None


def _validi(testo: str, regola: RegolaNumero, escluso: str | None) -> Iterator[tuple[str, int]]:
    for numero, inizio in _numeri(testo, regola.lunghezza):
        if numero.startswith(regola.prefissi) and numero != escluso:
            yield numero, inizio


# Cifre separate al massimo da uno spazio (anche non separabile) o da un trattino
_SEQUENZA = re.compile(r"[0-9]+(?:[ \N{NO-BREAK SPACE}-][0-9]+)*")
_PEZZO = re.compile(r"[0-9]+")
MIN_CIFRE_PEZZO = 3


def _numeri(testo: str, lunghezza: int) -> Iterator[tuple[str, int]]:
    """Numeri di `lunghezza` cifre, con la loro posizione nel testo.

    Un numero a pezzi vale solo se occupa tutta la sequenza e ogni pezzo ha
    almeno 3 cifre: così "4-12-2025 10" (una data e un numero) non diventa un
    protocollo. Altrimenti valgono solo i pezzi della lunghezza giusta.
    """
    for sequenza in _SEQUENZA.finditer(testo):
        pezzi = list(_PEZZO.finditer(sequenza.group()))
        cifre = "".join(pezzo.group() for pezzo in pezzi)
        a_pezzi_valido = (
            len(pezzi) > 1
            and len(cifre) == lunghezza
            and all(len(pezzo.group()) >= MIN_CIFRE_PEZZO for pezzo in pezzi)
        )
        if a_pezzi_valido:
            yield cifre, sequenza.start()
            continue
        for pezzo in pezzi:
            if len(pezzo.group()) == lunghezza:
                yield pezzo.group(), sequenza.start() + pezzo.start()


def _pattern_parole_chiave(parole: tuple[str, ...]) -> re.Pattern[str] | None:
    """Parole chiave a parola intera, maiuscole indifferenti ("prot" non trova "protocollato")."""
    if not parole:
        return None
    alternative = "|".join(r"\s+".join(map(re.escape, parola.split())) for parola in parole)
    return re.compile(rf"\b(?:{alternative})\b", re.IGNORECASE)
