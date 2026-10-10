"""Statistiche delle pratiche di malattia.

Tempo medio di gestione senza valori anomali: si scartano i tempi oltre
"media + 10 minuti" e si ricalcola, finché non si scarta più nulla (al massimo
6 giri, come nella v6.20). Le classifiche usano il CF solo per contare: le
etichette mostrano il nome.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from assenze_desk.core.stato import Stato, serve_mail_ufficio

MINUTI_OLTRE_LA_MEDIA = 10
GIRI = 6


@dataclass(frozen=True)
class TempoMedio:
    media_sec: float | None
    validi: tuple[float, ...]
    scartati: tuple[float, ...]  # nell'ordine in cui sono stati scartati

    @property
    def media_min(self) -> float | None:
        return round(self.media_sec / 60, 2) if self.media_sec is not None else None


@dataclass(frozen=True)
class PraticaStatistica:
    protocollo: str
    cf: str
    dipendente: str  # etichetta da mostrare (cognome e nome)
    cliente: str
    inizio: date | None
    fine: date | None
    giorni_episodio: int | None
    stato: Stato
    tempo_gestione_sec: float | None = None

    @property
    def giorni(self) -> int | None:
        if self.inizio and self.fine and self.fine >= self.inizio:
            return (self.fine - self.inizio).days + 1
        return None


@dataclass(frozen=True)
class Riepilogo:
    pratiche: int
    dipendenti: int
    clienti: int
    giorni: int
    media_giorni_per_pratica: float
    episodi_lunghi: int
    percentuale_episodi_lunghi: float
    per_stato: dict[Stato, int]
    giorni_per_mese: dict[str, int]  # "AAAA-MM" → giorni di certificato
    per_cliente: list[tuple[str, int, int]]  # (cliente, giorni, pratiche), più giorni prima
    per_dipendente: list[tuple[str, int, int]]
    tempo: TempoMedio


def tempo_medio(
    secondi: Sequence[float],
    minuti_oltre_la_media: float = MINUTI_OLTRE_LA_MEDIA,
    giri: int = GIRI,
) -> TempoMedio:
    validi = [s for s in secondi if s > 0]
    scartati: list[float] = []
    for _ in range(giri):
        if not validi:
            break
        soglia = sum(validi) / len(validi) + minuti_oltre_la_media * 60
        oltre = [s for s in validi if s > soglia]
        if not oltre:
            break
        scartati += oltre
        validi = [s for s in validi if s <= soglia]
    media = sum(validi) / len(validi) if validi else None
    return TempoMedio(media, tuple(validi), tuple(scartati))


def riepilogo(pratiche: Sequence[PraticaStatistica]) -> Riepilogo:
    con_date = [p for p in pratiche if p.giorni is not None]
    giorni = sum(p.giorni or 0 for p in con_date)
    lunghi = sum(1 for p in pratiche if serve_mail_ufficio(p.giorni_episodio or p.giorni or 0))

    per_mese: dict[str, int] = defaultdict(int)
    for p in con_date:
        if p.inizio:
            per_mese[f"{p.inizio:%Y-%m}"] += p.giorni or 0

    return Riepilogo(
        pratiche=len(pratiche),
        dipendenti=len({p.cf.strip().upper() for p in pratiche if p.cf.strip()}),
        clienti=len({p.cliente.strip().lower() for p in pratiche if p.cliente.strip()}),
        giorni=giorni,
        media_giorni_per_pratica=round(giorni / len(con_date), 2) if con_date else 0,
        episodi_lunghi=lunghi,
        percentuale_episodi_lunghi=round(lunghi / len(pratiche) * 100, 1) if pratiche else 0,
        per_stato={stato: sum(1 for p in pratiche if p.stato is stato) for stato in Stato},
        giorni_per_mese=dict(sorted(per_mese.items())),
        per_cliente=_classifica(pratiche, lambda p: p.cliente.strip().lower(), lambda p: p.cliente),
        per_dipendente=_classifica(
            pratiche, lambda p: p.cf.strip().upper(), lambda p: p.dipendente
        ),
        tempo=tempo_medio([p.tempo_gestione_sec for p in pratiche if p.tempo_gestione_sec]),
    )


def _classifica(pratiche, chiave, etichetta) -> list[tuple[str, int, int]]:
    gruppi: dict[str, list[PraticaStatistica]] = defaultdict(list)
    for p in pratiche:
        if chiave(p):
            gruppi[chiave(p)].append(p)
    righe = [
        (etichetta(gruppo[0]), sum(p.giorni or 0 for p in gruppo), len(gruppo))
        for gruppo in gruppi.values()
    ]
    return sorted(righe, key=lambda riga: (-riga[1], -riga[2], riga[0].lower()))
