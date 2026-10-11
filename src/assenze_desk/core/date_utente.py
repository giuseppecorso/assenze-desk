"""Date inserite dall'utente: avvisi sulle date poco plausibili e scelta dal calendario.

Una data scritta male (31/02, 45/13) non si legge e il campo lo dice da solo.
Qui si segnalano quelle che si leggono ma sembrano un errore di battitura: la
fine prima dell'inizio, una data a più di sei mesi da oggi (di solito l'anno
sbagliato). Sono avvisi, non blocchi: l'utente può confermare. I dati riaperti
dall'archivio sono già confermati e non si ricontrolla la distanza da oggi.

Dal mini calendario un clic aggiunge o toglie un giorno; un intervallo aggiunge
solo i giorni feriali, come la lettura dei permessi (D48): sabato e domenica
si scelgono con un clic a parte.
"""

from collections.abc import Iterable
from dataclasses import replace
from datetime import date, timedelta

from assenze_desk.core.campi import Campo, Origine

DISTANZA_MASSIMA = timedelta(days=183)  # circa sei mesi
AVVISO_LONTANA = "Data lontana da oggi (più di sei mesi): controlla l'anno."
AVVISO_FINE_PRIMA = "La fine viene prima dell'inizio: controlla le date."
AVVISO_GIORNI_LONTANI = "Alcuni giorni sono lontani da oggi (più di sei mesi): controlla l'anno."


def lontana(giorno: date, oggi: date) -> bool:
    return abs(giorno - oggi) > DISTANZA_MASSIMA


def controlla_periodo(inizio: Campo, fine: Campo, oggi: date) -> tuple[Campo, Campo]:
    """I due campi con gli avvisi di plausibilità aggiunti a quelli che hanno già."""
    controllati = []
    for campo in (inizio, fine):
        if isinstance(campo.valore, date) and _da_controllare(campo):
            campo = _con_avviso(campo, AVVISO_LONTANA if lontana(campo.valore, oggi) else "")
        controllati.append(campo)
    if (
        isinstance(inizio.valore, date)
        and isinstance(fine.valore, date)
        and fine.valore < inizio.valore
    ):
        controllati[1] = _con_avviso(controllati[1], AVVISO_FINE_PRIMA)
    return controllati[0], controllati[1]


def controlla_giorni(giorni: Campo, oggi: date) -> Campo:
    valore = giorni.valore if isinstance(giorni.valore, tuple) else ()
    if _da_controllare(giorni) and any(lontana(giorno, oggi) for giorno in valore):
        return _con_avviso(giorni, AVVISO_GIORNI_LONTANI)
    return giorni


def alterna_giorno(giorni: Iterable[date], giorno: date) -> tuple[date, ...]:
    """Il giorno si aggiunge se manca, si toglie se c'è già."""
    scelti = set(giorni) ^ {giorno}
    return tuple(sorted(scelti))


def aggiungi_feriali(giorni: Iterable[date], da: date, a: date) -> tuple[date, ...]:
    """Aggiunge i giorni da lunedì a venerdì tra `da` e `a`, in qualunque ordine."""
    primo, ultimo = min(da, a), max(da, a)
    feriali = {
        primo + timedelta(days=n)
        for n in range((ultimo - primo).days + 1)
        if (primo + timedelta(days=n)).weekday() < 5
    }
    return tuple(sorted(set(giorni) | feriali))


def _da_controllare(campo: Campo) -> bool:
    return campo.origine is not Origine.ARCHIVIO


def _con_avviso(campo: Campo, avviso: str) -> Campo:
    if not avviso or avviso in campo.avviso:
        return campo
    return replace(campo, avviso=f"{campo.avviso} {avviso}".strip())
