"""Assistente per il portale INPS e testo selezionato (issue #4)."""

import os
from datetime import datetime

import pytest

from assenze_desk.adapters.inps import (
    URL_PORTALE_INPS,
    ErroreInps,
    apri_portale,
    archivia_certificato,
    pdf_scaricati_dopo,
)
from assenze_desk.adapters.testo_selezionato import testo_nuovo

INIZIO = datetime(2026, 10, 7, 9, 0)


def scarica(cartella, nome, quando, contenuto=b"%PDF-finto"):
    file = cartella / nome
    file.write_bytes(contenuto)
    os.utime(file, (quando.timestamp(), quando.timestamp()))
    return file


def test_portale(monkeypatch):
    aperti = []
    apri_portale(URL_PORTALE_INPS, apri=aperti.append)
    assert aperti == [URL_PORTALE_INPS]
    assert URL_PORTALE_INPS.startswith("https://") and "inps.it" in URL_PORTALE_INPS


def test_pdf_scaricati_dopo_l_apertura_del_portale(tmp_path):
    scarica(tmp_path, "vecchio.pdf", datetime(2026, 10, 6, 18, 0))
    primo = scarica(tmp_path, "primo.pdf", datetime(2026, 10, 7, 9, 2))
    secondo = scarica(tmp_path, "secondo.pdf", datetime(2026, 10, 7, 9, 5))
    scarica(tmp_path, "nota.txt", datetime(2026, 10, 7, 9, 6))
    assert pdf_scaricati_dopo(tmp_path, INIZIO) == [secondo, primo]  # il più recente prima


def test_cartella_dei_download_mancante(tmp_path):
    assert pdf_scaricati_dopo(tmp_path / "manca", INIZIO) == []


def test_archivia_con_il_nome_del_protocollo(tmp_path):
    scaricato = scarica(tmp_path, "AttestatoMalattia.pdf", INIZIO)
    archiviato = archivia_certificato(scaricato, tmp_path / "certificati", "412345678")
    assert archiviato == tmp_path / "certificati" / "412345678.pdf"
    assert archiviato.read_bytes() == b"%PDF-finto"
    assert not scaricato.exists()


def test_archivia_lo_stesso_file_due_volte(tmp_path):
    archivia_certificato(scarica(tmp_path, "a.pdf", INIZIO), tmp_path / "c", "412345678")
    di_nuovo = archivia_certificato(scarica(tmp_path, "b.pdf", INIZIO), tmp_path / "c", "412345678")
    assert di_nuovo == tmp_path / "c" / "412345678.pdf"  # identico: nessun doppione
    assert sorted(p.name for p in (tmp_path / "c").iterdir()) == ["412345678.pdf"]


def test_non_sovrascrive_un_file_diverso(tmp_path):
    archivia_certificato(scarica(tmp_path, "a.pdf", INIZIO), tmp_path / "c", "412345678")
    altro = archivia_certificato(
        scarica(tmp_path, "b.pdf", INIZIO, b"%PDF-altro"), tmp_path / "c", "412345678"
    )
    assert altro.name == "412345678 (2).pdf"


@pytest.mark.parametrize(("nome", "protocollo"), [("a.pdf", " "), ("a.txt", "412345678")])
def test_archivia_errori(tmp_path, nome, protocollo):
    with pytest.raises(ErroreInps):
        archivia_certificato(scarica(tmp_path, nome, INIZIO), tmp_path / "c", protocollo)


# --- Testo selezionato: solo il testo nuovo negli appunti ---


@pytest.mark.parametrize(
    ("prima", "dopo", "atteso"),
    [
        ("vecchio", "  testo copiato  ", "testo copiato"),
        ("uguale", "uguale", None),  # Ctrl+C non ha copiato niente di nuovo
        ("vecchio", "   ", None),
        ("", "testo", "testo"),
    ],
)
def test_testo_nuovo_negli_appunti(prima, dopo, atteso):
    assert testo_nuovo(prima, dopo) == atteso
