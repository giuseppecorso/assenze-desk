"""Lettura del certificato da PDF, provata su PDF finti generati (issue #4)."""

import re
from datetime import date

import pytest
from fpdf import FPDF

from assenze_desk.adapters.pdf import ErrorePdf, leggi_certificato_pdf, testo_pdf
from assenze_desk.demo.certificati import CertificatoFinto, scrivi_certificato_finto

FINTO = CertificatoFinto(
    protocollo="412345678",
    cf="FNTPRV80A01Z999Y",
    cognome="Fittizio",
    nome="Luca",
    inizio=date(2026, 10, 1),
    fine=date(2026, 10, 3),
    tipo="Continuazione",
    visita="Domiciliare",
)


def test_il_pdf_finto_si_legge_come_un_certificato(tmp_path):
    percorso = scrivi_certificato_finto(FINTO, tmp_path / "certificato.pdf")
    dati = leggi_certificato_pdf(percorso, x_prima_della_voce=True)
    assert dati.protocollo == FINTO.protocollo
    assert dati.cf == FINTO.cf
    assert (dati.cognome, dati.nome) == ("Fittizio", "Luca")
    assert (dati.inizio, dati.fine, dati.data_visita) == (FINTO.inizio, FINTO.fine, FINTO.inizio)
    assert (dati.tipo, dati.visita) == ("Continuazione", "Domiciliare")
    assert dati.segnalazioni == ()


def test_il_pdf_finto_dichiara_di_essere_finto(tmp_path):
    testo = testo_pdf(scrivi_certificato_finto(FINTO, tmp_path / "c.pdf"))
    assert "FAC-SIMILE" in testo


def test_file_che_non_e_un_pdf(tmp_path):
    percorso = tmp_path / "non_pdf.pdf"
    percorso.write_text("non sono un PDF", encoding="utf-8")
    with pytest.raises(ErrorePdf, match=re.escape("non_pdf.pdf")):
        testo_pdf(percorso)


def test_file_mancante(tmp_path):
    with pytest.raises(ErrorePdf, match=re.escape("manca.pdf")):
        testo_pdf(tmp_path / "manca.pdf")


def test_pdf_senza_testo_come_una_scansione(tmp_path):
    pdf = FPDF()
    pdf.add_page()  # pagina vuota: come una scansione, nessun testo da leggere
    percorso = tmp_path / "scansione.pdf"
    pdf.output(str(percorso))
    with pytest.raises(ErrorePdf, match="scansione"):
        leggi_certificato_pdf(percorso)
