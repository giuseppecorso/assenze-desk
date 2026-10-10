"""Tipi di giustificativo e riconoscimento del tipo dal testo della mail.

Le parole chiave si cercano a parola intera, senza badare a maiuscole, accenti e
punteggiatura. Una parola che fa parte di una frase chiave più lunga trovata
nello stesso punto non conta da sola ("permesso" dentro "permesso 104").

Il risultato è l'elenco dei tipi trovati, in ordine di comparsa: con un solo
tipo il riconoscimento è riuscito; con nessuno o più di uno sceglie l'utente.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from assenze_desk.core.testo import normalizza
from assenze_desk.core.turni import OrarioSettimanale


@dataclass(frozen=True)
class TipoGiustificativo:
    nome: str
    codice: str
    parole_chiave: tuple[str, ...] = ()
    # Si conta a giornate: senza ore scritte valgono le ore del turno (es. Ferie)
    a_giornata: bool = False

    def __post_init__(self) -> None:
        if not self.nome.strip() or not self.codice.strip():
            raise ValueError("nome e codice del tipo sono obbligatori")
        for parola in self.parole_chiave:
            if not normalizza(parola):
                raise ValueError(f"parola chiave vuota nel tipo {self.nome!r}")


# Codici di esempio: quelli veri si impostano nella configurazione.
# "permesso" da solo non è una parola chiave: non decide il tipo.
TIPI_PREDEFINITI = (
    TipoGiustificativo(
        "Ferie",
        "FER",
        ("ferie", "giorno di ferie", "chiedo ferie", "vorrei ferie", "assenza per ferie"),
        a_giornata=True,
    ),
    TipoGiustificativo(
        "ROL",
        "ROL",
        (
            "rol",
            "permesso rol",
            "ore di rol",
            "permesso orario",
            "uscita anticipata",
            "uscire prima",
            "entrata posticipata",
            "ingresso posticipato",
            "ritardo",
            "ritardato",
            "ritardo entrata",
            "ritardare l'entrata",
            "ritardato l'entrata",
            "tardato l'entrata",
            "tardo l'entrata",
            "entro più tardi",
            "entrerò più tardi",
        ),
    ),
    TipoGiustificativo(
        "Permesso visita medica",
        "PVM",
        (
            "visita medica",
            "permesso visita",
            "permesso visita medica",
            "visita specialistica",
            "visita ospedaliera",
            "controllo medico",
            "appuntamento medico",
            "devo fare una visita",
        ),
    ),
)


@dataclass(frozen=True)
class RigaGiustificativo:
    """Una riga per giorno, come si esporta verso il gestionale."""

    giorno: date
    tipo: str
    codice: str
    minuti: int | None  # None = da compilare a mano

    @property
    def ore(self) -> float | None:
        return self.minuti / 60 if self.minuti is not None else None


def righe_giustificativo(
    tipo: TipoGiustificativo,
    giorni: Sequence[date],
    minuti: int | None,
    orario: OrarioSettimanale | None,
) -> list[RigaGiustificativo]:
    """Ore scritte (o proposte e confermate) uguali per ogni giorno; senza ore, per i
    tipi a giornata valgono le ore dell'orario del cliente in quel giorno."""
    righe = []
    for giorno in giorni:
        minuti_giorno = minuti
        if minuti_giorno is None and tipo.a_giornata and orario:
            minuti_giorno = orario.minuti_del_giorno(giorno)
        righe.append(RigaGiustificativo(giorno, tipo.nome, tipo.codice, minuti_giorno))
    return righe


def eccedenza_capienza(
    righe: Sequence[RigaGiustificativo], capienza_minuti: int | None
) -> int | None:
    """Minuti oltre la capienza residua (0 se ci sta); None se la capienza non è nota.
    Le righe ancora da compilare non contano."""
    if capienza_minuti is None:
        return None
    richiesti = sum(riga.minuti for riga in righe if riga.minuti is not None)
    return max(0, richiesti - capienza_minuti)


def classifica_giustificativo(
    testo: str, tipi: Sequence[TipoGiustificativo] = TIPI_PREDEFINITI
) -> list[TipoGiustificativo]:
    """Tipi trovati nel testo, in ordine di prima comparsa."""
    normalizzato = normalizza(testo)
    trovate = [  # (inizio, fine, posizione del tipo nell'elenco)
        (corrispondenza.start(), corrispondenza.end(), indice)
        for indice, tipo in enumerate(tipi)
        for parola in tipo.parole_chiave
        for corrispondenza in _pattern(parola).finditer(normalizzato)
    ]
    valide = [t for t in trovate if not _dentro_una_piu_lunga(t, trovate)]

    risultato: list[TipoGiustificativo] = []
    for _inizio, _fine, indice in sorted(valide):
        if tipi[indice] not in risultato:
            risultato.append(tipi[indice])
    return risultato


def _pattern(parola: str) -> re.Pattern[str]:
    # Il testo è già normalizzato: parole separate da un solo spazio
    return re.compile(rf"(?<![0-9a-z]){re.escape(normalizza(parola))}(?![0-9a-z])")


def _dentro_una_piu_lunga(trovata: tuple[int, int, int], tutte: list[tuple[int, int, int]]) -> bool:
    inizio, fine, _ = trovata
    return any(
        altra_inizio <= inizio and fine <= altra_fine and altra_fine - altra_inizio > fine - inizio
        for altra_inizio, altra_fine, _ in tutte
    )
