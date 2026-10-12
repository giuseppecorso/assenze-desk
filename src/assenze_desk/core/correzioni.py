"""Correzioni dell'anagrafica fatte nell'app, sopra i dati dell'Excel.

Il file Excel resta com'è (lo aggiorna l'utente, anche con le sue macro): le
correzioni si salvano a parte, una riga per dipendente e JobOrder, e contengono
solo i campi diversi dall'Excel. CF e JobOrder identificano la riga e non si
correggono. Una correzione di una riga che non c'è più si ignora.
"""

from collections.abc import Mapping, Sequence
from dataclasses import fields, replace

from assenze_desk.core.dipendenti import Dipendente

CAMPI_MODIFICABILI = (
    "cognome",
    "nome",
    "email",
    "cliente",
    "copia_cliente",
    "inizio_joborder",
    "fine_joborder",
)

Chiave = tuple[str, str]  # (CF, JobOrder)


def chiave(dipendente: Dipendente) -> Chiave:
    return dipendente.cf.strip().upper(), dipendente.joborder.strip()


def differenze(originale: Dipendente, corretto: Dipendente) -> dict[str, object]:
    if chiave(originale) != chiave(corretto):
        raise ValueError("la correzione deve riguardare lo stesso dipendente e JobOrder")
    return {
        campo: getattr(corretto, campo)
        for campo in CAMPI_MODIFICABILI
        if getattr(corretto, campo) != getattr(originale, campo)
    }


def applica_correzioni(
    dipendenti: Sequence[Dipendente], correzioni: Mapping[Chiave, Mapping[str, object]]
) -> tuple[Dipendente, ...]:
    per_chiave = {(cf.strip().upper(), jo.strip()): campi for (cf, jo), campi in correzioni.items()}
    validi = {f.name for f in fields(Dipendente)} & set(CAMPI_MODIFICABILI)
    risultato = []
    for dipendente in dipendenti:
        campi = per_chiave.get(chiave(dipendente), {})
        nuovi = {campo: valore for campo, valore in campi.items() if campo in validi}
        risultato.append(replace(dipendente, **nuovi) if nuovi else dipendente)
    return tuple(risultato)
