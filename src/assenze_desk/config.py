"""Impostazioni dell'app in un file JSON: percorsi, mail dell'ufficio, regole, tipi, template.

- Il file sta nella cartella dati dell'utente (%LOCALAPPDATA%\\AssenzeDesk), mai nel repo.
- Ogni voce mancante vale il suo valore predefinito: un file parziale funziona.
- Del vocabolario si salvano solo le parole aggiunte ("vocabolario_aggiunte"), così i
  valori predefiniti possono migliorare con le nuove versioni.
- Una voce sconosciuta dà un avviso; un valore non valido un errore che nomina la voce.
- I percorsi relativi si intendono dentro la cartella dati.
"""

import json
import os
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from assenze_desk.core.giustificativi import TIPI_PREDEFINITI, TipoGiustificativo
from assenze_desk.core.identificativi import JOBORDER, PROTOCOLLO, RegolaNumero
from assenze_desk.core.vocabolario import VOCABOLARIO, Vocabolario


@dataclass(frozen=True)
class Percorsi:
    archivio: Path
    anagrafica: Path
    certificati: Path
    export: Path
    log: Path


@dataclass(frozen=True)
class MailUfficio:
    destinatari: tuple[str, ...] = ()
    copia: tuple[str, ...] = ()


@dataclass(frozen=True)
class Template:
    oggetto_lavoratore: str = "Ricezione certificato di malattia - prot. {PROTOCOLLO}"
    corpo_lavoratore: str = (
        "Gentile {NOME},\n\n"
        "confermiamo la ricezione del certificato di malattia n. {PROTOCOLLO} "
        "dal {DAL} al {AL}.\n\n"
        "Cordiali saluti"
    )
    oggetto_ufficio: str = (
        "Malattia {CANDIDATO} - {CLIENTE} - dal {INIZIO_EPISODIO} al {FINE_EPISODIO}"
    )
    corpo_ufficio: str = (
        "Buongiorno,\n\n"
        "in allegato i certificati di malattia di {CANDIDATO} "
        "(codice fiscale {CF}, JobOrder {JOB}, cliente {CLIENTE}).\n"
        "Episodio dal {INIZIO_EPISODIO} al {FINE_EPISODIO}: {GIORNI_EPISODIO} giorni.\n"
        "Protocolli: {PROTOCOLLI}.\n\n"
        "Cordiali saluti"
    )
    oggetto_giustificativo: str = "Ricezione richiesta di {TIPO}"
    corpo_giustificativo: str = (
        "Gentile {NOME},\n\n"
        "abbiamo preso in carico la richiesta di {TIPO} per {GIORNI}.\n\n"
        "Cordiali saluti"
    )


@dataclass(frozen=True)
class Impostazioni:
    percorsi: Percorsi
    ufficio: MailUfficio
    protocollo: RegolaNumero
    joborder: RegolaNumero
    soglia_ufficio: int
    domini_interni: tuple[str, ...]
    tipi: tuple[TipoGiustificativo, ...]
    vocabolario: Vocabolario
    minuti_oltre_la_media: int
    giorni_avanti_permessi: int
    template: Template
    # Certificato PDF: la X delle spunte sta prima della voce? None = automatico
    spunte_prima_della_voce: bool | None = None


def cartella_dati_predefinita() -> Path:
    """%LOCALAPPDATA%\\AssenzeDesk su Windows, altrimenti ~/.assenze-desk."""
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "AssenzeDesk" if base else Path.home() / ".assenze-desk"


def impostazioni_predefinite(cartella_dati: Path) -> Impostazioni:
    return Impostazioni(
        percorsi=Percorsi(
            archivio=cartella_dati / "archivio.db",
            anagrafica=cartella_dati / "anagrafica.xlsx",
            certificati=cartella_dati / "certificati",
            export=cartella_dati / "export",
            log=cartella_dati / "log",
        ),
        ufficio=MailUfficio(),
        protocollo=PROTOCOLLO,
        joborder=JOBORDER,
        soglia_ufficio=3,
        domini_interni=(),
        tipi=TIPI_PREDEFINITI,
        vocabolario=VOCABOLARIO,
        minuti_oltre_la_media=10,
        giorni_avanti_permessi=0,
        template=Template(),
    )


def carica_impostazioni(file: Path, cartella_dati: Path) -> tuple[Impostazioni, list[str]]:
    """Le impostazioni del file (con i predefiniti per le voci mancanti) e gli avvisi."""
    predefinite = impostazioni_predefinite(cartella_dati)
    if not Path(file).is_file():
        return predefinite, ["File delle impostazioni non trovato: uso i valori predefiniti."]
    try:
        contenuto = json.loads(Path(file).read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as errore:
        raise ValueError(f"file delle impostazioni non leggibile (riga {errore.lineno})") from None
    if not isinstance(contenuto, dict):
        raise ValueError("file delle impostazioni non valido: serve un oggetto JSON")

    avvisi: list[str] = []
    valori: dict[str, Any] = {}
    for voce, valore in contenuto.items():
        conversione = _CONVERSIONI.get(voce)
        if conversione is None:
            avvisi.append(f"Voce sconosciuta ignorata: {voce}")
            continue
        try:
            campo, convertito = conversione(valore, predefinite, cartella_dati)
        except (TypeError, ValueError, KeyError, AttributeError) as errore:
            raise ValueError(f"impostazioni non valide alla voce '{voce}': {errore}") from None
        valori[campo] = convertito
    return replace(predefinite, **valori), avvisi


def salva_impostazioni(impostazioni: Impostazioni, file: Path) -> None:
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(
        json.dumps(_in_dizionario(impostazioni), ensure_ascii=False, indent=2), encoding="utf-8"
    )


# --- Conversioni dal file ---


def _testi(valore: Any) -> tuple[str, ...]:
    if not isinstance(valore, list) or not all(isinstance(v, str) for v in valore):
        raise TypeError("serve un elenco di testi")
    return tuple(valore)


def _intero(valore: Any) -> int:
    if isinstance(valore, bool) or not isinstance(valore, int):
        raise TypeError("serve un numero intero")
    return valore


def _percorsi(valore: Any, predefinite: Impostazioni, cartella: Path):
    attuali = {f.name: getattr(predefinite.percorsi, f.name) for f in fields(Percorsi)}
    for nome, testo in valore.items():
        if nome not in attuali or not isinstance(testo, str):
            raise ValueError(f"percorso non valido: {nome}")
        percorso = Path(testo)
        attuali[nome] = percorso if percorso.is_absolute() else cartella / percorso
    return "percorsi", Percorsi(**attuali)


def _ufficio(valore: Any, predefinite: Impostazioni, _cartella: Path):
    attuali = {"destinatari": predefinite.ufficio.destinatari, "copia": predefinite.ufficio.copia}
    attuali.update({nome: _testi(elenco) for nome, elenco in valore.items() if nome in attuali})
    return "ufficio", MailUfficio(**attuali)


def _regola(nome: str):
    def converti(valore: Any, predefinite: Impostazioni, _cartella: Path):
        attuale: RegolaNumero = getattr(predefinite, nome)
        return nome, RegolaNumero(
            lunghezza=_intero(valore.get("lunghezza", attuale.lunghezza)),
            prefissi=_testi(valore.get("prefissi", list(attuale.prefissi))),
            parole_chiave=_testi(valore.get("parole_chiave", list(attuale.parole_chiave))),
        )

    return converti


def _numero(nome: str):
    def converti(valore: Any, _predefinite: Impostazioni, _cartella: Path):
        return nome, _intero(valore)

    return converti


def _domini(valore: Any, _predefinite: Impostazioni, _cartella: Path):
    return "domini_interni", _testi(valore)


def _tipi(valore: Any, _predefinite: Impostazioni, _cartella: Path):
    return "tipi", tuple(
        TipoGiustificativo(
            nome=tipo["nome"],
            codice=tipo["codice"],
            parole_chiave=_testi(tipo.get("parole_chiave", [])),
            a_giornata=bool(tipo.get("a_giornata", False)),
        )
        for tipo in valore
    )


def _vocabolario(valore: Any, _predefinite: Impostazioni, _cartella: Path):
    return "vocabolario", VOCABOLARIO.estendi(**{c: _testi(p) for c, p in valore.items()})


def _spunte(valore: Any, _predefinite: Impostazioni, _cartella: Path):
    if valore is not None and not isinstance(valore, bool):
        raise TypeError("serve true, false oppure null (automatico)")
    return "spunte_prima_della_voce", valore


def _template(valore: Any, predefinite: Impostazioni, _cartella: Path):
    nomi = {f.name for f in fields(Template)}
    testi = {
        nome: testo for nome, testo in valore.items() if nome in nomi and isinstance(testo, str)
    }
    return "template", replace(predefinite.template, **testi)


_CONVERSIONI = {
    "percorsi": _percorsi,
    "ufficio": _ufficio,
    "protocollo": _regola("protocollo"),
    "joborder": _regola("joborder"),
    "soglia_ufficio": _numero("soglia_ufficio"),
    "domini_interni": _domini,
    "tipi": _tipi,
    "vocabolario_aggiunte": _vocabolario,
    "minuti_oltre_la_media": _numero("minuti_oltre_la_media"),
    "giorni_avanti_permessi": _numero("giorni_avanti_permessi"),
    "template": _template,
    "spunte_prima_della_voce": _spunte,
}


# --- Conversione verso il file ---


def _in_dizionario(imp: Impostazioni) -> dict[str, Any]:
    aggiunte = {
        campo.name: [
            parola
            for parola in getattr(imp.vocabolario, campo.name)
            if parola not in getattr(VOCABOLARIO, campo.name)
        ]
        for campo in fields(Vocabolario)
    }
    return {
        "percorsi": {f.name: str(getattr(imp.percorsi, f.name)) for f in fields(Percorsi)},
        "ufficio": {"destinatari": list(imp.ufficio.destinatari), "copia": list(imp.ufficio.copia)},
        "protocollo": _regola_in_dizionario(imp.protocollo),
        "joborder": _regola_in_dizionario(imp.joborder),
        "soglia_ufficio": imp.soglia_ufficio,
        "domini_interni": list(imp.domini_interni),
        "tipi": [
            {
                "nome": tipo.nome,
                "codice": tipo.codice,
                "parole_chiave": list(tipo.parole_chiave),
                "a_giornata": tipo.a_giornata,
            }
            for tipo in imp.tipi
        ],
        "vocabolario_aggiunte": {campo: parole for campo, parole in aggiunte.items() if parole},
        "minuti_oltre_la_media": imp.minuti_oltre_la_media,
        "giorni_avanti_permessi": imp.giorni_avanti_permessi,
        "template": {f.name: getattr(imp.template, f.name) for f in fields(Template)},
        "spunte_prima_della_voce": imp.spunte_prima_della_voce,
    }


def _regola_in_dizionario(regola: RegolaNumero) -> dict[str, Any]:
    return {
        "lunghezza": regola.lunghezza,
        "prefissi": list(regola.prefissi),
        "parole_chiave": list(regola.parole_chiave),
    }
