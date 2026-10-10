"""Errori mostrati e registrati, mai ignorati in silenzio (problema noto 9).

Gli errori previsti (Outlook chiuso, PDF illeggibile, dati mancanti...) hanno
già un messaggio per l'utente: finiscono nella barra dei messaggi e nel log.
Quelli imprevisti passano dal gestore globale della finestra principale.
"""

import logging
from collections.abc import Callable

from assenze_desk.adapters.inps import ErroreInps
from assenze_desk.adapters.ocr import ErroreOcr
from assenze_desk.adapters.outlook import ErroreOutlook
from assenze_desk.adapters.pdf import ErrorePdf
from assenze_desk.gui.componenti import BarraMessaggi
from assenze_desk.servizi import ErroreServizi

log = logging.getLogger(__name__)

ERRORI_PREVISTI = (
    ErroreServizi,
    ErroreOutlook,
    ErrorePdf,
    ErroreInps,
    ErroreOcr,
    OSError,
    ValueError,
)


def esegui[T](messaggi: BarraMessaggi, azione: Callable[[], T]) -> T | None:
    """Esegue l'azione; un errore previsto diventa un messaggio e il risultato è None."""
    try:
        return azione()
    except ERRORI_PREVISTI as errore:
        log.warning("%s", errore)
        messaggi.mostra(str(errore), "errore")
        return None
