"""Log dell'app: file con rotazione e codice fiscale sempre mascherato.

Il mascheramento si applica al testo finale di ogni riga, traceback compresi:
un CF dentro il messaggio di un'eccezione non arriva mai in chiaro sul file.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from assenze_desk.core.privacy import maschera_cf

NOME_FILE = "assenze-desk.log"
FORMATO = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class FormatterRiservato(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return maschera_cf(super().format(record))


class GestoreFileApp(RotatingFileHandler):
    """Il gestore aggiunto da `configura_log`, riconoscibile per poterlo sostituire."""


def configura_log(
    cartella: Path,
    livello: int = logging.INFO,
    massimo_byte: int = 1_000_000,
    copie: int = 5,
) -> Path:
    """Scrive il log dell'app in `cartella`; richiamarla sostituisce la configurazione."""
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    file = cartella / NOME_FILE

    registro = logging.getLogger("assenze_desk")
    for gestore in list(registro.handlers):
        if isinstance(gestore, GestoreFileApp):
            registro.removeHandler(gestore)
            gestore.close()

    gestore = GestoreFileApp(file, maxBytes=massimo_byte, backupCount=copie, encoding="utf-8")
    gestore.setFormatter(FormatterRiservato(FORMATO))
    registro.addHandler(gestore)
    registro.setLevel(livello)
    return file
