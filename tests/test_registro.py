"""Log con rotazione e codice fiscale sempre mascherato (issue #3)."""

import logging

import pytest

from assenze_desk.registro import configura_log

CF = "FNTPRV80A01Z999Y"


@pytest.fixture
def log(tmp_path):
    file = configura_log(tmp_path / "log", massimo_byte=2000, copie=2)
    yield file
    registro = logging.getLogger("assenze_desk")
    for gestore in list(registro.handlers):
        registro.removeHandler(gestore)
        gestore.close()  # chiude il file di log


def contenuto(file):
    for gestore in logging.getLogger("assenze_desk").handlers:
        gestore.flush()
    return file.read_text(encoding="utf-8")


def test_cf_mascherato_nei_messaggi(log):
    logging.getLogger("assenze_desk.prova").info("Pratica di %s salvata", CF)
    testo = contenuto(log)
    assert "Pratica di FNT************Y salvata" in testo
    assert CF not in testo


def test_cf_mascherato_anche_negli_errori(log):
    try:
        raise ValueError(f"CF {CF} non trovato in anagrafica")
    except ValueError:
        logging.getLogger("assenze_desk.prova").exception("Errore durante l'import")
    testo = contenuto(log)
    assert "Traceback" in testo
    assert "FNT************Y" in testo
    assert CF not in testo


def test_rotazione(log):
    registro = logging.getLogger("assenze_desk.prova")
    for numero in range(200):
        registro.info("riga di prova numero %d con un po' di testo", numero)
    file_di_log = sorted(p.name for p in log.parent.iterdir())
    assert file_di_log == ["assenze-desk.log", "assenze-desk.log.1", "assenze-desk.log.2"]


def test_configurare_due_volte_non_duplica_le_righe(tmp_path, log):
    configura_log(tmp_path / "log", massimo_byte=2000, copie=2)
    logging.getLogger("assenze_desk.prova").warning("una volta sola")
    assert contenuto(log).count("una volta sola") == 1


def test_livello_e_formato(log):
    registro = logging.getLogger("assenze_desk.prova")
    registro.debug("non scritto")
    registro.warning("scritto")
    testo = contenuto(log)
    assert "non scritto" not in testo
    assert "WARNING assenze_desk.prova: scritto" in testo
