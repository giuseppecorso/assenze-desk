"""File delle impostazioni (issue #3): valori predefiniti, file parziali, errori chiari."""

import json
from pathlib import Path

import pytest

from assenze_desk.adapters.inps import URL_PORTALE_INPS
from assenze_desk.config import (
    CartelleOutlook,
    Ocr,
    PortaleAziendale,
    Risposte,
    carica_impostazioni,
    cartella_dati_predefinita,
    impostazioni_predefinite,
    indirizzo_apribile,
    regole_analisi,
    salva_impostazioni,
)
from assenze_desk.core.analisi import RegoleAnalisi
from assenze_desk.core.giustificativi import TIPI_PREDEFINITI, TipoGiustificativo
from assenze_desk.core.identificativi import JOBORDER, PROTOCOLLO, RegolaNumero
from assenze_desk.core.vocabolario import VOCABOLARIO


@pytest.fixture
def cartella(tmp_path):
    return tmp_path / "dati"


def scrivi(tmp_path, contenuto):
    file = tmp_path / "impostazioni.json"
    file.write_text(json.dumps(contenuto), encoding="utf-8")
    return file


def test_valori_predefiniti(cartella):
    imp = impostazioni_predefinite(cartella)
    assert imp.percorsi.archivio == cartella / "archivio.db"
    assert imp.percorsi.anagrafica == cartella / "anagrafica.xlsx"
    assert imp.percorsi.backup == cartella / "backup"
    assert imp.protocollo == PROTOCOLLO
    assert imp.joborder == JOBORDER
    assert imp.tipi == TIPI_PREDEFINITI
    assert imp.vocabolario == VOCABOLARIO
    assert imp.soglia_ufficio == 3
    assert imp.minuti_oltre_la_media == 10
    assert imp.domini_interni == ()
    assert "{PROTOCOLLO}" in imp.template.corpo_lavoratore


def test_file_mancante_valori_predefiniti(tmp_path, cartella):
    imp, avvisi = carica_impostazioni(tmp_path / "manca.json", cartella)
    assert imp == impostazioni_predefinite(cartella)
    assert avvisi == ["File delle impostazioni non trovato: uso i valori predefiniti."]


def test_salva_e_ricarica(tmp_path, cartella):
    file = tmp_path / "impostazioni.json"
    imp = impostazioni_predefinite(cartella)
    salva_impostazioni(imp, file)
    assert carica_impostazioni(file, cartella) == (imp, [])


def test_file_parziale_sovrascrive_solo_le_voci_presenti(tmp_path, cartella):
    file = scrivi(
        tmp_path,
        {
            "soglia_ufficio": 5,
            "domini_interni": ["azienda.example"],
            "ufficio": {"destinatari": ["ufficio@example.com"]},
            "protocollo": {"lunghezza": 10, "prefissi": ["5"]},
        },
    )
    imp, avvisi = carica_impostazioni(file, cartella)
    assert avvisi == []
    assert imp.soglia_ufficio == 5
    assert imp.domini_interni == ("azienda.example",)
    assert imp.ufficio.destinatari == ("ufficio@example.com",)
    assert imp.ufficio.copia == ()
    assert imp.protocollo == RegolaNumero(10, ("5",), PROTOCOLLO.parole_chiave)
    assert imp.tipi == TIPI_PREDEFINITI


def test_parole_aggiunte_al_vocabolario(tmp_path, cartella):
    file = scrivi(
        tmp_path, {"vocabolario_aggiunte": {"unita_ore": ["hr"], "invece": ["piuttosto che"]}}
    )
    imp, _ = carica_impostazioni(file, cartella)
    assert imp.vocabolario == VOCABOLARIO.estendi(unita_ore=["hr"], invece=["piuttosto che"])
    salva_impostazioni(imp, file)
    salvato = json.loads(file.read_text(encoding="utf-8"))
    assert salvato["vocabolario_aggiunte"] == {"unita_ore": ["hr"], "invece": ["piuttosto che"]}


def test_tipi_dal_file_al_posto_dei_predefiniti(tmp_path, cartella):
    file = scrivi(
        tmp_path,
        {"tipi": [{"nome": "Lavoro agile", "codice": "SW", "parole_chiave": ["smart working"]}]},
    )
    imp, _ = carica_impostazioni(file, cartella)
    assert imp.tipi == (TipoGiustificativo("Lavoro agile", "SW", ("smart working",)),)


def test_percorsi_relativi_alla_cartella_dati(tmp_path, cartella):
    assoluto = tmp_path / "altrove" / "anagrafica.xlsx"
    file = scrivi(
        tmp_path, {"percorsi": {"archivio": "db/archivio.db", "anagrafica": str(assoluto)}}
    )
    imp, _ = carica_impostazioni(file, cartella)
    assert imp.percorsi.archivio == cartella / "db" / "archivio.db"
    assert imp.percorsi.anagrafica == assoluto


def test_posizione_delle_spunte_del_certificato(tmp_path, cartella):
    assert impostazioni_predefinite(cartella).spunte_prima_della_voce is None  # automatico
    imp, _ = carica_impostazioni(scrivi(tmp_path, {"spunte_prima_della_voce": True}), cartella)
    assert imp.spunte_prima_della_voce is True
    with pytest.raises(ValueError, match="spunte_prima_della_voce"):
        carica_impostazioni(scrivi(tmp_path, {"spunte_prima_della_voce": "si"}), cartella)


def test_voci_di_ocr_e_portale_inps(tmp_path, cartella):
    imp = impostazioni_predefinite(cartella)
    assert imp.percorsi.download == Path.home() / "Downloads"
    assert imp.portale_inps == URL_PORTALE_INPS
    assert imp.ocr == Ocr(tesseract="", parole_rumore=())  # "" = Tesseract cercato da solo

    file = scrivi(
        tmp_path,
        {
            "percorsi": {"download": str(tmp_path / "scaricati")},
            "portale_inps": "https://portale.example/attestati",
            "ocr": {"tesseract": str(tmp_path / "tesseract.exe"), "parole_rumore": ["intranet"]},
        },
    )
    imp, avvisi = carica_impostazioni(file, cartella)
    assert avvisi == []
    assert imp.percorsi.download == tmp_path / "scaricati"
    assert imp.portale_inps == "https://portale.example/attestati"
    assert imp.ocr == Ocr(str(tmp_path / "tesseract.exe"), ("intranet",))
    salva_impostazioni(imp, file)
    assert carica_impostazioni(file, cartella) == (imp, [])


def test_voci_dell_interfaccia(tmp_path, cartella):
    imp = impostazioni_predefinite(cartella)
    assert imp.tema == "sistema"
    assert imp.posta == "outlook"
    assert imp.cartelle_outlook == CartelleOutlook(malattie="", giustificativi="")

    file = scrivi(
        tmp_path,
        {"tema": "scuro", "posta": "mailto", "cartelle_outlook": {"malattie": "Gestite/Malattie"}},
    )
    imp, avvisi = carica_impostazioni(file, cartella)
    assert avvisi == []
    assert (imp.tema, imp.posta) == ("scuro", "mailto")
    assert imp.cartelle_outlook == CartelleOutlook("Gestite/Malattie", "")
    salva_impostazioni(imp, file)
    assert carica_impostazioni(file, cartella) == (imp, [])


def test_risposte_al_lavoratore_e_ai_colleghi(tmp_path, cartella):
    imp = impostazioni_predefinite(cartella)
    assert imp.risposte == Risposte(dalla_lista_cliente=False, mittente_collega="")
    assert "{" not in imp.template.corpo_collega  # testo breve, senza dati della pratica

    file = scrivi(
        tmp_path,
        {
            "risposte": {"dalla_lista_cliente": True, "mittente_collega": "io@example.com"},
            "template": {"corpo_collega": "Ciao, grazie!"},
        },
    )
    imp, avvisi = carica_impostazioni(file, cartella)
    assert avvisi == []
    assert imp.risposte == Risposte(True, "io@example.com")
    assert imp.template.corpo_collega == "Ciao, grazie!"
    salva_impostazioni(imp, file)
    assert carica_impostazioni(file, cartella) == (imp, [])


def test_portale_aziendale_facoltativo(tmp_path, cartella):
    imp = impostazioni_predefinite(cartella)
    assert imp.portale_aziendale == PortaleAziendale(nome="Portale aziendale", indirizzo="")
    assert not imp.portale_aziendale.attivo

    file = scrivi(
        tmp_path,
        {"portale_aziendale": {"nome": "Intranet", "indirizzo": "https://intranet.example/app"}},
    )
    imp, avvisi = carica_impostazioni(file, cartella)
    assert avvisi == []
    assert imp.portale_aziendale == PortaleAziendale("Intranet", "https://intranet.example/app")
    assert imp.portale_aziendale.attivo
    salva_impostazioni(imp, file)
    assert carica_impostazioni(file, cartella) == (imp, [])


@pytest.mark.parametrize(
    "indirizzo",
    [
        "",
        "https://intranet.example",
        "http://10.0.0.1/app",
        r"C:\Programmi\App\app.exe",
        r"\\server\app",
    ],
)
def test_portale_aziendale_indirizzi_ammessi(indirizzo):
    assert indirizzo_apribile(indirizzo)


@pytest.mark.parametrize("indirizzo", ["intranet.example", "ftp://x", "javascript:alert(1)"])
def test_portale_aziendale_indirizzi_rifiutati(indirizzo):
    assert not indirizzo_apribile(indirizzo)


def test_regole_per_l_analisi(tmp_path, cartella):
    file = scrivi(tmp_path, {"giorni_avanti_permessi": 30, "protocollo": {"lunghezza": 10}})
    imp, _ = carica_impostazioni(file, cartella)
    assert regole_analisi(imp) == RegoleAnalisi(
        protocollo=imp.protocollo,
        joborder=imp.joborder,
        tipi=imp.tipi,
        vocabolario=imp.vocabolario,
        giorni_avanti=30,
    )


def test_voce_sconosciuta_avviso(tmp_path, cartella):
    _imp, avvisi = carica_impostazioni(scrivi(tmp_path, {"voce_inventata": 1}), cartella)
    assert avvisi == ["Voce sconosciuta ignorata: voce_inventata"]


@pytest.mark.parametrize(
    ("contenuto", "voce"),
    [
        ({"soglia_ufficio": "tre"}, "soglia_ufficio"),
        ({"protocollo": {"lunghezza": 0}}, "protocollo"),
        ({"tipi": [{"nome": "Ferie"}]}, "tipi"),
        ({"vocabolario_aggiunte": {"parole_inventate": ["x"]}}, "vocabolario_aggiunte"),
        ({"domini_interni": "azienda.example"}, "domini_interni"),
        ({"percorsi": {"cartella_inventata": "x"}}, "percorsi"),
        ({"portale_inps": "portale.example"}, "portale_inps"),
        ({"ocr": {"parole_rumore": "intranet"}}, "ocr"),
        ({"ocr": {"tesseract": 5}}, "ocr"),
        ({"tema": "blu"}, "tema"),
        ({"posta": "piccione"}, "posta"),
        ({"cartelle_outlook": {"malattie": 3}}, "cartelle_outlook"),
        ({"risposte": {"dalla_lista_cliente": "forse"}}, "risposte"),
        ({"risposte": {"inventata": 1}}, "risposte"),
        ({"portale_aziendale": {"indirizzo": "intranet.example"}}, "portale_aziendale"),
        ({"portale_aziendale": {"nome": ""}}, "portale_aziendale"),
        ({"portale_aziendale": {"inventata": "x"}}, "portale_aziendale"),
    ],
)
def test_valore_non_valido_errore_con_la_voce(tmp_path, cartella, contenuto, voce):
    with pytest.raises(ValueError, match=voce):
        carica_impostazioni(scrivi(tmp_path, contenuto), cartella)


def test_json_rovinato(tmp_path, cartella):
    file = tmp_path / "impostazioni.json"
    file.write_text("{ non è json", encoding="utf-8")
    with pytest.raises(ValueError, match="impostazioni"):
        carica_impostazioni(file, cartella)
    file.write_text("[1, 2]", encoding="utf-8")  # JSON valido ma non un oggetto
    with pytest.raises(ValueError, match="impostazioni"):
        carica_impostazioni(file, cartella)


def test_cartella_dati_predefinita(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert cartella_dati_predefinita() == tmp_path / "AssenzeDesk"
    monkeypatch.delenv("LOCALAPPDATA")
    assert cartella_dati_predefinita() == Path.home() / ".assenze-desk"
