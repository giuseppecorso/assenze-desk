"""Testo selezionato in un'altra applicazione, letto tramite gli appunti.

Windows non permette di leggere direttamente il testo selezionato in un'altra
finestra: l'interfaccia si riduce a icona, qui si invia Ctrl+C all'applicazione
attiva e poi si leggono gli appunti. Vale solo il testo nuovo: se gli appunti
non cambiano, la copia non è riuscita.
"""

import ctypes
import time

_CTRL, _TASTO_C, _RILASCIA = 0x11, 0x43, 0x0002


def testo_nuovo(prima: str, dopo: str) -> str | None:
    """Il testo copiato, se negli appunti c'è qualcosa di nuovo e non vuoto."""
    copiato = dopo.strip()
    return copiato if copiato and copiato != prima.strip() else None


def premi_ctrl_c() -> None:  # pragma: no cover - tastiera vera, solo Windows
    tastiera = ctypes.windll.user32.keybd_event  # type: ignore[attr-defined]
    tastiera(_CTRL, 0, 0, 0)
    tastiera(_TASTO_C, 0, 0, 0)
    tastiera(_TASTO_C, 0, _RILASCIA, 0)
    tastiera(_CTRL, 0, _RILASCIA, 0)
    time.sleep(0.25)  # lascia all'applicazione il tempo di copiare
