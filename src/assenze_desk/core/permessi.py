"""Lettura completa di una richiesta di permesso o di ferie.

Mette insieme i moduli del core: tipo (giustificativi), giorni (periodi, date,
giorni relativi), ore (durate, fasce, orari spostati, parti della giornata).

Regole:
- si legge solo oggetto e corpo: le date delle intestazioni sono quelle della mail;
- le ore scritte vincono su mattina/pomeriggio, che sono proposte dal turno da
  confermare; se le ore scritte non concordano tra loro, il campo resta vuoto;
- per i tipi "a giornata" (Ferie) senza ore scritte le ore restano vuote senza
  segnalazione: le righe le prendono dall'orario del cliente, giorno per giorno;
- ogni dubbio diventa una segnalazione sul campo (tipo, giorni, ore), che
  l'interfaccia evidenzia: meglio vuoto che sbagliato. Il weekend nei periodi ha
  una segnalazione a parte: lo decide l'utente con un interruttore (D48).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from assenze_desk.core.date import trova_date
from assenze_desk.core.giorni import trova_giorni
from assenze_desk.core.giustificativi import (
    TIPI_PREDEFINITI,
    TipoGiustificativo,
    classifica_giustificativo,
)
from assenze_desk.core.mail import dividi_mail
from assenze_desk.core.orari import Intervallo, togli_intervalli, trova_intervalli
from assenze_desk.core.ore import trova_durate
from assenze_desk.core.periodi import togli_periodi, trova_periodi
from assenze_desk.core.turni import Turno, minuti_parte, trova_parti_giornata
from assenze_desk.core.vocabolario import VOCABOLARIO, Vocabolario


@dataclass(frozen=True)
class Segnalazione:
    campo: Literal["tipo", "giorni", "weekend", "ore"]
    messaggio: str


@dataclass(frozen=True)
class Permesso:
    tipi: tuple[TipoGiustificativo, ...]
    giorni: tuple[date, ...]
    giorni_weekend: tuple[date, ...]  # nei periodi: se includerli lo decide l'utente
    minuti: int | None  # per ogni giorno
    intervallo: Intervallo | None
    segnalazioni: tuple[Segnalazione, ...]

    @property
    def tipo(self) -> TipoGiustificativo | None:
        """Il tipo, se ne è stato riconosciuto uno solo."""
        return self.tipi[0] if len(self.tipi) == 1 else None


def leggi_permesso(
    testo: str,
    data_mail: date,
    turno: Turno | None = None,
    tipi: Sequence[TipoGiustificativo] = TIPI_PREDEFINITI,
    vocabolario: Vocabolario = VOCABOLARIO,
    giorni_avanti: int = 0,
) -> Permesso:
    mail = dividi_mail(testo)
    contenuto = f"{mail.oggetto}\n{mail.corpo}"
    segnalazioni: list[Segnalazione] = []

    trovati = tuple(classifica_giustificativo(contenuto, tipi))
    if not trovati:
        segnalazioni.append(Segnalazione("tipo", "Tipo non riconosciuto: sceglilo."))
    elif len(trovati) > 1:
        nomi = ", ".join(tipo.nome for tipo in trovati)
        segnalazioni.append(
            Segnalazione("tipo", f"Più tipi possibili ({nomi}): scegli quello giusto.")
        )

    giorni, weekend = _giorni(contenuto, data_mail, vocabolario, giorni_avanti)
    if not giorni and not weekend:
        segnalazioni.append(Segnalazione("giorni", "Giorno non trovato: inseriscilo."))
    if weekend:
        segnalazioni.append(
            Segnalazione(
                "weekend",
                f"Il periodo comprende {len(weekend)} giorni di sabato o domenica: "
                "decidi se includerli.",
            )
        )

    intervalli = trova_intervalli(contenuto, vocabolario)
    tipo = trovati[0] if len(trovati) == 1 else None
    minuti, avviso = _minuti(contenuto, intervalli, tipo, turno, vocabolario)
    if avviso:
        segnalazioni.append(Segnalazione("ore", avviso))

    return Permesso(
        tipi=trovati,
        giorni=giorni,
        giorni_weekend=weekend,
        minuti=minuti,
        intervallo=intervalli[0] if len(intervalli) == 1 else None,
        segnalazioni=tuple(segnalazioni),
    )


def _giorni(
    testo: str, data_mail: date, vocabolario: Vocabolario, giorni_avanti: int
) -> tuple[tuple[date, ...], tuple[date, ...]]:
    """Giorni chiesti e, a parte, i giorni di weekend che cadono dentro i periodi."""
    periodi = trova_periodi(testo, data_mail, vocabolario, giorni_avanti)
    chiesti = {giorno for periodo in periodi for giorno in periodo.lavorativi}
    weekend = {giorno for periodo in periodi for giorno in periodo.weekend}
    # I giorni singoli si cercano fuori dai periodi, già letti
    fuori = togli_periodi(testo, vocabolario)
    chiesti |= set(trova_date(fuori, data_mail, giorni_avanti))
    chiesti |= set(trova_giorni(fuori, data_mail, vocabolario))
    return tuple(sorted(chiesti)), tuple(sorted(weekend - chiesti))


def _minuti(
    testo: str,
    intervalli: list[Intervallo],
    tipo: TipoGiustificativo | None,
    turno: Turno | None,
    vocabolario: Vocabolario,
) -> tuple[int | None, str | None]:
    """Minuti per giorno e, se serve, il motivo della segnalazione."""
    # Le durate si cercano fuori dalle fasce: "dalle 9h alle 11h" non è "9h"
    scritti = set(trova_durate(togli_intervalli(testo, vocabolario), vocabolario))
    scritti |= {intervallo.minuti for intervallo in intervalli}
    if len(scritti) == 1:
        return scritti.pop(), None
    if len(scritti) > 1:
        valori = ", ".join(f"{m // 60}:{m % 60:02d}" for m in sorted(scritti))
        return None, f"Ore in contrasto nel testo ({valori}): inseriscile."

    parti = trova_parti_giornata(testo, vocabolario)
    if len(parti) > 1:
        return None, "Parti della giornata diverse: inserisci le ore."
    if parti:
        minuti = minuti_parte(parti[0], turno)
        if minuti is None:
            nome = {"mattina": "della mattina", "pomeriggio": "del pomeriggio"}.get(
                parti[0], "della giornata"
            )
            return None, f"Ore {nome} non disponibili nel turno: inseriscile."
        return minuti, f"Ore proposte dal turno ({parti[0]}): da confermare."

    if tipo and tipo.a_giornata:
        return None, None  # giornate intere: le ore di ogni giorno vengono dall'orario (righe)
    return None, "Ore non trovate: inseriscile."
