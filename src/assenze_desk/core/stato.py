"""Stato della pratica di malattia.

Incompleta (manca protocollo, CF o date, oppure la fine viene prima dell'inizio)
→ Da inviare (risposta al lavoratore non fatta)
→ Parziale (episodio oltre la soglia, di default 3 giorni, senza mail all'ufficio)
→ Chiusa.
Uno stato impostato a mano non viene ricalcolato.
"""

from datetime import date
from enum import StrEnum

SOGLIA_UFFICIO = 3  # giorni di episodio oltre i quali serve la mail all'ufficio


class Stato(StrEnum):
    INCOMPLETA = "Incompleta"
    DA_INVIARE = "Da inviare"
    PARZIALE = "Parziale"
    CHIUSA = "Chiusa"


def serve_mail_ufficio(giorni_episodio: int, soglia: int = SOGLIA_UFFICIO) -> bool:
    return giorni_episodio > soglia


def calcola_stato(
    *,
    protocollo: str | None,
    cf: str | None,
    inizio: date | None,
    fine: date | None,
    mail_lavoratore: bool,
    mail_ufficio: bool,
    giorni_episodio: int | None = None,
    stato_manuale: Stato | None = None,
    soglia_ufficio: int = SOGLIA_UFFICIO,
) -> Stato:
    if stato_manuale is not None:
        return stato_manuale
    mancano_dati = not (protocollo or "").strip() or not (cf or "").strip()
    if mancano_dati or inizio is None or fine is None or fine < inizio:
        return Stato.INCOMPLETA
    if not mail_lavoratore:
        return Stato.DA_INVIARE
    # Episodio non ancora calcolato: valgono i giorni del certificato
    giorni = giorni_episodio if giorni_episodio is not None else (fine - inizio).days + 1
    if serve_mail_ufficio(giorni, soglia_ufficio) and not mail_ufficio:
        return Stato.PARZIALE
    return Stato.CHIUSA
