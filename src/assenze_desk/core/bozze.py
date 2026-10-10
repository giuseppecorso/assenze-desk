"""Valori dei segnaposti delle bozze: {NOME}, {PROTOCOLLO}, {GIORNI}...

Un valore mancante è None: il segnaposto resta visibile nella bozza e
l'interfaccia lo elenca tra i mancanti (D33).
"""

from collections.abc import Sequence
from datetime import date

from assenze_desk.core import formati
from assenze_desk.core.dipendenti import Dipendente
from assenze_desk.core.episodio import Episodio

Valori = dict[str, str | None]


def valori_malattia(
    *,
    dipendente: Dipendente | None,
    protocollo: str | None,
    cf: str | None,
    joborder: str | None,
    inizio: date | None,
    fine: date | None,
    episodio: Episodio | None = None,
) -> Valori:
    valori = _persona(dipendente)
    valori.update(
        {
            "PROTOCOLLO": protocollo or None,
            "CF": cf or None,
            "JOB": joborder or None,
            "DAL": formati.data(inizio) or None,
            "AL": formati.data(fine) or None,
            "INIZIO_EPISODIO": formati.data(episodio.inizio) if episodio else None,
            "FINE_EPISODIO": formati.data(episodio.fine) if episodio else None,
            "GIORNI_EPISODIO": str(episodio.giorni) if episodio else None,
            "PROTOCOLLI": ", ".join(episodio.protocolli) if episodio else None,
        }
    )
    return valori


def valori_giustificativo(
    *,
    dipendente: Dipendente | None,
    tipo: str | None,
    giorni: Sequence[date],
    minuti: int | None,
) -> Valori:
    valori = _persona(dipendente)
    valori.update(
        {
            "TIPO": tipo or None,
            "GIORNI": formati.elenco_giorni(giorni) or None,
            "ORE": formati.durata_in_parole(minuti) or None,
        }
    )
    return valori


def _persona(dipendente: Dipendente | None) -> Valori:
    if dipendente is None:
        return {"NOME": None, "COGNOME": None, "CANDIDATO": None, "CLIENTE": None}
    return {
        "NOME": dipendente.nome or None,
        "COGNOME": dipendente.cognome or None,
        "CANDIDATO": f"{dipendente.cognome} {dipendente.nome}".strip() or None,
        "CLIENTE": dipendente.cliente or None,
    }
