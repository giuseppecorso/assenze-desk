"""OCR: pulizia del testo (core) e lettura delle immagini (adapter). Issue #4.

Il programma Tesseract non serve ai test: la lettura vera è finta (`ocr=`).
"""

from pathlib import Path

import pytest
from PIL import Image

from assenze_desk.adapters.ocr import (
    ErroreOcr,
    leggi_testo_immagine,
    prepara_immagine,
    trova_tesseract,
)
from assenze_desk.core.ocr import pulisci_testo_ocr, qualita_testo

# --- Pulizia del testo letto (core) ---


def test_toglie_le_righe_di_disturbo():
    letto = (
        "| File | Home | Visualizza |\n"
        "a b c d e f\n"
        "====>>>___\n"
        "Buongiorno,\n"
        "invio il certificato protocollo 412345678\n"
        "@@ ##\n"
    )
    assert pulisci_testo_ocr(letto) == "Buongiorno,\ninvio il certificato protocollo 412345678"


def test_le_righe_restano_separate_e_gli_spazi_si_ripuliscono():
    # Il core legge anche su più righe: unire le righe attaccherebbe dati diversi
    letto = "  chiedo un permesso per  \ndomani dalle 9 alle 11.\n\n\nGrazie • "
    assert pulisci_testo_ocr(letto) == "chiedo un permesso per\ndomani dalle 9 alle 11.\n\nGrazie"


def test_conserva_le_righe_con_dati_utili_anche_se_corte():
    letto = "CF\nFNTPRV80A01Z999Y\n05/10/2026\na@example.com"
    assert pulisci_testo_ocr(letto) == "FNTPRV80A01Z999Y\n05/10/2026\na@example.com"


def test_parole_di_disturbo_configurabili():
    letto = "Portale Interno Demo\nchiedo ferie domani"
    assert pulisci_testo_ocr(letto) == "Portale Interno Demo\nchiedo ferie domani"
    assert pulisci_testo_ocr(letto, ("portale interno",)) == "chiedo ferie domani"


def test_caratteri_invisibili_e_apostrofi():
    assert pulisci_testo_ocr("l’ufficio\u200b ha  ricevuto") == "l'ufficio ha ricevuto"


def test_qualita_del_testo():
    buono = "Buongiorno,\ninvio il certificato di malattia\nCordiali saluti"
    rumoroso = "|| ## @@ ~~\n<< >>"
    assert qualita_testo(buono) > qualita_testo(rumoroso)
    assert qualita_testo("") < qualita_testo(rumoroso)


# --- Programma Tesseract (adapter) ---


def test_trova_tesseract_nell_impostazione_poi_nei_percorsi_standard(monkeypatch, tmp_path):
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr("shutil.which", lambda _nome: None)
    impostato = tmp_path / "tesseract.exe"
    impostato.write_bytes(b"")
    assert trova_tesseract(str(impostato)) == impostato

    standard = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    assert trova_tesseract("", esiste=lambda p: p == standard) == standard
    assert trova_tesseract("", esiste=lambda _p: False) is None


def test_trova_tesseract_dalla_variabile_d_ambiente(monkeypatch, tmp_path):
    da_variabile = tmp_path / "da_variabile.exe"
    da_variabile.write_bytes(b"")
    monkeypatch.setenv("TESSERACT_CMD", str(da_variabile))
    assert trova_tesseract("") == da_variabile


# --- Lettura delle immagini (adapter) ---


def test_prepara_immagine_bianco_e_nero_e_ingrandita():
    immagine = Image.new("RGB", (100, 50), "white")
    pronta = prepara_immagine(immagine)
    assert pronta.mode == "L"
    assert pronta.size == (300, 150)  # le immagini piccole si ingrandiscono
    assert {colore for _quanti, colore in pronta.getcolors()} <= {0, 255}


def test_legge_il_ritaglio_migliore():
    letture = iter(["|| @@ ~~", "Buongiorno,\ninvio il certificato di malattia", "##"])
    immagine = Image.new("RGB", (400, 300), "white")
    testo = leggi_testo_immagine(immagine, Path("tesseract"), ocr=lambda *_a, **_k: next(letture))
    assert testo == "Buongiorno,\ninvio il certificato di malattia"


def test_si_ferma_al_primo_ritaglio_ben_leggibile():
    letto = (
        "Buongiorno,\ninvio il certificato di malattia\nprotocollo 412345678\n"
        "dal 05/10/2026 al 09/10/2026\nCordiali saluti"
    )
    chiamate = []

    def ocr(*_a, **_k):
        chiamate.append(1)
        return letto

    immagine = Image.new("RGB", (400, 300), "white")
    assert leggi_testo_immagine(immagine, Path("tesseract"), ocr=ocr) == letto
    assert len(chiamate) == 1  # gli altri ritagli non servono: l'OCR è lento


def test_nessun_testo_utile():
    immagine = Image.new("RGB", (400, 300), "white")
    with pytest.raises(ErroreOcr, match="testo"):
        leggi_testo_immagine(immagine, Path("tesseract"), ocr=lambda *_a, **_k: "  ")


def test_tesseract_non_installato():
    with pytest.raises(ErroreOcr, match="Tesseract"):
        leggi_testo_immagine(Image.new("RGB", (40, 40)), None)
