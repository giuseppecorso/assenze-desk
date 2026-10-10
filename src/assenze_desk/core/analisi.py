"""Analisi di una mail: le proposte per i campi della pratica, con l'origine.

Mette insieme le regole del core e le traduce in `Proposta` per il modulo dei
campi (core/campi.py):
- malattia: protocollo, CF, JobOrder e periodo dal testo; dal certificato PDF
  protocollo, CF, date e tipo. Il PDF vince sul testo, ma se la mail diceva
  altro il campo resta incerto con il valore della mail nell'avviso;
- permesso: tipo, giorni, ore e weekend da `leggi_permesso`, con le sue
  segnalazioni sul campo giusto;
- dipendente: scelto in automatico solo se il match è sicuro, altrimenti i
  candidati diventano scelte per l'utente.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime, time

from assenze_desk.core.campi import Origine, Proposta
from assenze_desk.core.certificato import DatiCertificato
from assenze_desk.core.codice_fiscale import estrai_cf
from assenze_desk.core.date import trova_date
from assenze_desk.core.dipendenti import Dipendente, EsitoMatch
from assenze_desk.core.giustificativi import TIPI_PREDEFINITI, TipoGiustificativo
from assenze_desk.core.identificativi import (
    JOBORDER,
    PROTOCOLLO,
    RegolaNumero,
    estrai_joborder,
    estrai_protocollo,
)
from assenze_desk.core.mail import dividi_mail
from assenze_desk.core.periodi import trova_periodi
from assenze_desk.core.permessi import Permesso
from assenze_desk.core.vocabolario import VOCABOLARIO, Vocabolario

_DA = re.compile(r"^(?:da|from)\s*:", re.IGNORECASE)
_DATA = re.compile(r"^(?:data|date|inviato|sent)\s*:", re.IGNORECASE)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_ORA = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")

# Parole delle segnalazioni del certificato → campo a cui si riferiscono
_CAMPI_SEGNALAZIONI = (
    ("protocollo", "protocollo"),
    ("codice fiscale", "cf"),
    ("data di inizio", "inizio"),
    ("data di fine", "fine"),
    ("'Trattasi di'", "tipo_certificato"),
)
_CAMPI_PERMESSO = {"tipo": "tipo", "giorni": "giorni", "weekend": "weekend", "ore": "minuti"}


@dataclass(frozen=True)
class RegoleAnalisi:
    protocollo: RegolaNumero = PROTOCOLLO
    joborder: RegolaNumero = JOBORDER
    tipi: tuple[TipoGiustificativo, ...] = TIPI_PREDEFINITI
    vocabolario: Vocabolario = VOCABOLARIO
    giorni_avanti: int = 0


def intestazioni_mail(testo: str) -> tuple[str, datetime | None]:
    """Mittente e data di una mail incollata, dalle righe "Da:" e "Data:"/"Inviato:"."""
    mittente, ricevuta = "", None
    for riga in dividi_mail(testo).intestazioni.splitlines():
        if not mittente and _DA.match(riga) and (email := _EMAIL.search(riga)):
            mittente = email[0].lower()
        if ricevuta is None and _DATA.match(riga) and (date_trovate := trova_date(riga)):
            ora = _ORA.search(riga)
            orario = time(int(ora[1]), int(ora[2])) if ora else time()
            ricevuta = datetime.combine(date_trovate[0], orario)
    return mittente, ricevuta


# --- Malattia ---


def proposte_malattia(testo: str, data_mail: date, regole: RegoleAnalisi) -> dict[str, Proposta]:
    proposte: dict[str, Proposta] = {}
    trovati = {
        "protocollo": estrai_protocollo(testo, regole.protocollo, regole.joborder),
        "cf": estrai_cf(testo),
        "joborder": estrai_joborder(testo, regole.joborder),
    }
    proposte.update({c: Proposta(v, Origine.TESTO) for c, v in trovati.items() if v})

    mail = dividi_mail(testo)
    periodi = set(
        trova_periodi(
            f"{mail.oggetto}\n{mail.corpo}", data_mail, regole.vocabolario, regole.giorni_avanti
        )
    )
    if len(periodi) == 1:
        periodo = periodi.pop()
        proposte["inizio"] = Proposta(periodo.inizio, Origine.TESTO)
        proposte["fine"] = Proposta(periodo.fine, Origine.TESTO)
    elif periodi:
        avviso = "Nel testo ci sono più periodi: controlla le date."
        proposte["inizio"] = proposte["fine"] = Proposta(avviso=avviso)
    return proposte


def proposte_certificato(dati: DatiCertificato) -> dict[str, Proposta]:
    valori = {
        "protocollo": dati.protocollo,
        "cf": dati.cf,
        "inizio": dati.inizio,
        "fine": dati.fine,
        "tipo_certificato": dati.tipo,
    }
    avvisi: dict[str, list[str]] = {campo: [] for campo in valori}
    for segnalazione in dati.segnalazioni:
        for parola, campo in _CAMPI_SEGNALAZIONI:
            if parola in segnalazione:
                avvisi[campo].append(segnalazione)
                break
    return {
        campo: Proposta(valore, Origine.PDF if valore else None, " ".join(avvisi[campo]))
        for campo, valore in valori.items()
    }


def unisci(
    dal_testo: Mapping[str, Proposta], dal_pdf: Mapping[str, Proposta]
) -> dict[str, Proposta]:
    """Il PDF vince; un valore diverso nella mail resta scritto nell'avviso."""
    unite = dict(dal_testo)
    for campo, pdf in dal_pdf.items():
        testo = dal_testo.get(campo)
        if pdf.valore is None:
            if testo is None or testo.valore is None:
                unite[campo] = pdf
            continue
        if testo is not None and testo.valore is not None and testo.valore != pdf.valore:
            avviso = f"Nella mail: {_mostra(testo.valore)}. Controlla."
            pdf = replace(pdf, avviso=f"{pdf.avviso} {avviso}".strip())
        unite[campo] = pdf
    return unite


# --- Dipendente ---


def proposta_dipendente(esito: EsitoMatch) -> Proposta:
    if esito.dipendente is not None:
        return Proposta(esito.dipendente, Origine.ANAGRAFICA)
    if esito.candidati:
        return Proposta(avviso="Più dipendenti possibili: scegli tu.", scelte=esito.candidati)
    return Proposta(avviso="Dipendente non trovato: cercalo o inseriscilo a mano.")


def completa_con_dipendente(
    proposte: Mapping[str, Proposta], dipendente: Dipendente | None
) -> dict[str, Proposta]:
    """CF e JobOrder dall'anagrafica, se il testo e il PDF non li hanno dati."""
    completate = dict(proposte)
    if dipendente is None:
        return completate
    for campo, valore in (("cf", dipendente.cf), ("joborder", dipendente.joborder)):
        attuale = completate.get(campo)
        if valore and (attuale is None or attuale.valore is None):
            completate[campo] = Proposta(valore, Origine.ANAGRAFICA)
    return completate


# --- Permessi ---


def proposte_permesso(permesso: Permesso) -> dict[str, Proposta]:
    avvisi: dict[str, list[str]] = {campo: [] for campo in _CAMPI_PERMESSO.values()}
    for segnalazione in permesso.segnalazioni:
        avvisi[_CAMPI_PERMESSO[segnalazione.campo]].append(segnalazione.messaggio)

    tipo = permesso.tipo
    scelte = tuple(t.nome for t in permesso.tipi) if len(permesso.tipi) > 1 else ()
    valori: dict[str, object] = {
        "tipo": tipo.nome if tipo else None,
        "giorni": permesso.giorni or None,
        "weekend": permesso.giorni_weekend or None,
        "minuti": permesso.minuti,
    }
    return {
        campo: Proposta(
            valore,
            Origine.TESTO if valore is not None else None,
            " ".join(avvisi[campo]),
            scelte if campo == "tipo" else (),
        )
        for campo, valore in valori.items()
    }


def _mostra(valore: object) -> str:
    return f"{valore:%d/%m/%Y}" if isinstance(valore, date) else str(valore)
