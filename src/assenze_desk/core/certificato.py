"""Dati dal testo di un certificato di malattia INPS (testo già estratto dal PDF).

Etichette cercate (come nella v6.20): "Protocollo univoco del certificato (PUC)",
"Cognome ... Nome ... C.F.", "ammalato dal ... a tutto il ...", "Data visita",
e le spunte "X" nelle sezioni "Trattasi di:" e "Visita:".

Spunte: nel testo estratto una X sta tra due voci. Con `x_prima_della_voce`
None (automatico) la si attribuisce solo se la sezione comincia con una X (le X
precedono le voci) o finisce con una X (le seguono); altrimenti la spunta resta
vuota e segnalata. Quando si conosce il formato dei certificati veri si imposta
True o False. Ogni dato mancante o dubbio diventa una segnalazione, senza CF in chiaro.
"""

import re
from dataclasses import dataclass
from datetime import date

from assenze_desk.core.codice_fiscale import cf_valido
from assenze_desk.core.date import leggi_data
from assenze_desk.core.identificativi import estrai_protocollo
from assenze_desk.core.privacy import maschera_cf

TIPI = ("Inizio", "Continuazione", "Ricaduta", "Ricovero")
VISITE = ("Ambulatoriale", "Domiciliare", "Pronto Soccorso", "Ricovero")

_DATA = r"([0-3]?\d/[01]?\d/\d{4})"
_PROTOCOLLO = re.compile(
    r"(?:PUC|protocollo(?:\s+univoco)?(?:\s+del\s+certificato)?)\D{0,30}?((?:\d[ \-/]?){6,}\d)",
    re.IGNORECASE,
)
_CF = re.compile(r"\bC\.?\s?F\.?\s*:?\s*([A-Z0-9]{16})\b", re.IGNORECASE)
_NOMINATIVO = re.compile(
    r"\bCognome\s+([A-ZÀ-Ü' ]+?)\s+Nome\s+([A-ZÀ-Ü' ]+?)\s+C\.?\s?F", re.IGNORECASE
)
_INIZIO = re.compile(rf"ammalat[oa]\s+dal\s+{_DATA}", re.IGNORECASE)
_FINE = re.compile(rf"a\s+tutto\s+il\s+{_DATA}", re.IGNORECASE)
_DATA_VISITA = re.compile(rf"Data\s+(?:della\s+)?visita\s*:?\s*{_DATA}", re.IGNORECASE)
_SEZIONE_TRATTASI = re.compile(r"Trattasi\s+di\s*:(.*?)(?=Visita\s*:|$)", re.IGNORECASE | re.DOTALL)
_SEZIONE_VISITA = re.compile(
    r"Visita\s*:(.*?)(?=Data\s+(?:della\s+)?visita|La\s+malattia|DATI\s+DEL|ammalat|$)",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class DatiCertificato:
    protocollo: str | None
    cf: str | None
    cognome: str
    nome: str
    inizio: date | None
    fine: date | None
    data_visita: date | None
    tipo: str | None  # Inizio, Continuazione, Ricaduta, Ricovero
    visita: str | None  # Ambulatoriale, Domiciliare, Pronto Soccorso, Ricovero
    segnalazioni: tuple[str, ...]

    @property
    def continuazione(self) -> bool:
        return self.tipo == "Continuazione"


def leggi_certificato(testo: str, x_prima_della_voce: bool | None = None) -> DatiCertificato:
    segnalazioni: list[str] = []

    protocollo = None
    if trovato := _PROTOCOLLO.search(testo):
        protocollo = re.sub(r"\D", "", trovato[1])
    protocollo = protocollo or estrai_protocollo(testo)
    if not protocollo:
        segnalazioni.append("Nel certificato manca il protocollo.")

    cf = None
    if trovato := _CF.search(testo):
        cf = trovato[1].upper()
        if not cf_valido(cf):
            segnalazioni.append(
                f"Il codice fiscale {maschera_cf(cf)} del certificato non è valido."
            )
            cf = None
    else:
        segnalazioni.append("Nel certificato manca il codice fiscale.")

    cognome = nome = ""
    if trovato := _NOMINATIVO.search(testo):
        cognome = " ".join(trovato[1].split()).title()
        nome = " ".join(trovato[2].split()).title()

    inizio = _data(_INIZIO, testo, "inizio", segnalazioni)
    fine = _data(_FINE, testo, "fine", segnalazioni)
    trovato = _DATA_VISITA.search(testo)
    data_visita = leggi_data(trovato[1]) if trovato else None

    tipo = _spunta(_SEZIONE_TRATTASI, testo, TIPI, x_prima_della_voce, "Trattasi di", segnalazioni)
    visita = _spunta(_SEZIONE_VISITA, testo, VISITE, x_prima_della_voce, "Visita", segnalazioni)

    return DatiCertificato(
        protocollo, cf, cognome, nome, inizio, fine, data_visita, tipo, visita, tuple(segnalazioni)
    )


def _data(regex: re.Pattern[str], testo: str, nome: str, segnalazioni: list[str]) -> date | None:
    trovato = regex.search(testo)
    data = leggi_data(trovato[1]) if trovato else None
    if data is None:
        segnalazioni.append(f"Nel certificato manca la data di {nome}.")
    return data


def _spunta(
    sezione_regex: re.Pattern[str],
    testo: str,
    voci: tuple[str, ...],
    x_prima: bool | None,
    nome_sezione: str,
    segnalazioni: list[str],
) -> str | None:
    sezione = sezione_regex.search(testo)
    if not sezione:
        return None
    alternative = "|".join(re.escape(v).replace(r"\ ", r"\s+") for v in voci)
    elementi = [
        "X" if parte.upper() == "X" else _voce(parte, voci)
        for parte in re.findall(rf"\bX\b|{alternative}", sezione[1], re.IGNORECASE)
    ]
    if "X" not in elementi:
        return None
    if x_prima is None:
        x_prima = True if elementi[0] == "X" else False if elementi[-1] == "X" else None
    if x_prima is None:
        segnalazioni.append(
            f"Le spunte della sezione '{nome_sezione}' non sono leggibili: scegli a mano."
        )
        return None

    posizione = elementi.index("X")
    vicina = posizione + 1 if x_prima else posizione - 1
    if 0 <= vicina < len(elementi) and elementi[vicina] != "X":
        return elementi[vicina]
    segnalazioni.append(
        f"Le spunte della sezione '{nome_sezione}' non sono leggibili: scegli a mano."
    )
    return None


def _voce(scritta: str, voci: tuple[str, ...]) -> str:
    """La voce nella forma canonica ("pronto  soccorso" → "Pronto Soccorso")."""
    pulita = " ".join(scritta.split()).lower()
    return next(v for v in voci if v.lower() == pulita)
