"""Import dell'anagrafica da Excel (issue #3). Solo dati finti, file creati nel test."""

from datetime import date, datetime

import pytest
from openpyxl import Workbook

from assenze_desk.core.dipendenti import Dipendente
from assenze_desk.core.turni import OrarioSettimanale
from assenze_desk.demo.generatore import genera_dati
from assenze_desk.storage.anagrafica import importa_anagrafica, scrivi_anagrafica

CF_LUCA = "FNTPRV80A01Z999Y"


def salva(tmp_path, fogli, nome="anagrafica.xlsx"):
    """Crea un file Excel con i fogli indicati: {nome: [intestazione, riga, ...]}."""
    libro = Workbook()
    libro.remove(libro.active)
    for titolo, righe in fogli.items():
        foglio = libro.create_sheet(titolo)
        for riga in righe:
            foglio.append(riga)
    percorso = tmp_path / nome
    libro.save(percorso)
    return percorso


def test_andata_e_ritorno_con_i_dati_demo(tmp_path):
    dati = genera_dati(date(2026, 10, 7), seme=3, dipendenti=12)
    capienze = {dati.anagrafica[0].joborder: {"Ferie": 2400, "ROL": 960}}
    percorso = tmp_path / "anagrafica.xlsx"
    scrivi_anagrafica(percorso, dati.anagrafica, dati.orari, capienze)

    esito = importa_anagrafica(percorso)
    assert esito.dipendenti == dati.anagrafica
    assert esito.orari == dati.orari
    assert esito.capienze == capienze
    assert esito.avvisi == ()


def test_nomi_di_colonna_flessibili_e_valori_da_ripulire(tmp_path):
    percorso = salva(
        tmp_path,
        {
            "Dipendenti": [
                [
                    "Codice Fiscale",
                    "COGNOME",
                    "Nome",
                    "E-mail",
                    "Job Order",
                    "Clienti",
                    "Data inizio",
                    "Data fine",
                ],
                [
                    f" {CF_LUCA.lower()} ",
                    " Fittizio ",
                    "Luca",
                    "Luca.Fittizio@Example.com",
                    201111111,  # numero, non testo
                    "Alfa Srl",
                    datetime(2026, 1, 1),  # data vera di Excel
                    "30/06/2026",  # data scritta come testo
                ],
            ]
        },
    )
    [dipendente] = importa_anagrafica(percorso).dipendenti
    assert dipendente == Dipendente(
        cf=CF_LUCA,
        cognome="Fittizio",
        nome="Luca",
        email="luca.fittizio@example.com",
        joborder="201111111",
        cliente="Alfa Srl",
        inizio_joborder=date(2026, 1, 1),
        fine_joborder=date(2026, 6, 30),
    )


def test_periodi_dei_joborder_in_un_altro_foglio_come_nella_v620(tmp_path):
    # Il file di configurazione della v6.20 (.xlsm) tiene i periodi in un foglio
    # a parte, con JobOrder e date d'inizio e fine: il nome del foglio non conta
    percorso = salva(
        tmp_path,
        {
            "Dipendenti": [
                ["CF", "Cognome", "Nome", "JobOrder", "CDC", "DL"],
                [CF_LUCA, "Fittizio", "Luca", "201111111", "X", "Y"],
                [CF_LUCA, "Fittizio", "Luca", "202222222", "X", "Y"],
                [CF_LUCA, "Fittizio", "Luca", "203333333", "X", "Y"],
            ],
            "Template": [["Chiave", "Testo"], ["Oggetto", "Certificato"]],
            "Elenco periodi": [
                ["NumJob", "Dt.Inizio", "Dt.Fine"],
                [201111111, datetime(2026, 1, 1), datetime(2026, 3, 31)],
                ["202222222", "01/04/2026", None],
            ],
        },
        nome="config.xlsm",
    )
    dipendenti = importa_anagrafica(percorso).dipendenti
    periodi = [(d.inizio_joborder, d.fine_joborder) for d in dipendenti]
    assert periodi == [
        (date(2026, 1, 1), date(2026, 3, 31)),
        (date(2026, 4, 1), None),
        (None, None),  # JobOrder senza periodo
    ]


def test_lista_del_cliente_in_copia_come_nella_v620(tmp_path):
    # La colonna DL dei dipendenti; il foglio "Clienti" (Clienti + DL) vince
    percorso = salva(
        tmp_path,
        {
            "Dipendenti": [
                ["CF", "Cognome", "JobOrder", "Cliente", "DL"],
                [CF_LUCA, "Fittizio", "201111111", "Alfa Srl", "alfa.vecchia@example.com"],
                [CF_LUCA, "Fittizio", "202222222", "Beta Spa", "beta@example.com"],
                [CF_LUCA, "Fittizio", "203333333", "Gamma Srl", None],
            ],
            "Clienti": [["clienti", "DL"], ["ALFA SRL ", "alfa@example.com; capo@example.com"]],
        },
    )
    copie = [d.copia_cliente for d in importa_anagrafica(percorso).dipendenti]
    assert copie == ["alfa@example.com; capo@example.com", "beta@example.com", ""]


def test_le_date_nel_foglio_dipendenti_vincono(tmp_path):
    percorso = salva(
        tmp_path,
        {
            "Dipendenti": [
                ["CF", "JobOrder", "Data inizio"],
                [CF_LUCA, "201111111", datetime(2026, 2, 1)],
            ],
            "Periodi": [["JobOrder", "Data inizio"], ["201111111", datetime(2025, 1, 1)]],
        },
    )
    [dipendente] = importa_anagrafica(percorso).dipendenti
    assert dipendente.inizio_joborder == date(2026, 2, 1)


def test_nome_completo_in_una_sola_colonna(tmp_path):
    percorso = salva(tmp_path, {"Dipendenti": [["CF", "Candidato"], [CF_LUCA, "Fittizio Luca"]]})
    [dipendente] = importa_anagrafica(percorso).dipendenti
    assert (dipendente.cognome, dipendente.nome) == ("Fittizio Luca", "")


def test_righe_scartate_o_dubbie_con_avviso_senza_cf_in_chiaro(tmp_path):
    percorso = salva(
        tmp_path,
        {
            "Dipendenti": [
                ["CF", "Cognome", "Nome"],
                ["", "Senza", "Codice"],
                ["FNTPRV80A01Z999A", "Errato", "Controllo"],  # carattere di controllo sbagliato
                [None, None, None],  # riga vuota: ignorata senza avviso
            ]
        },
    )
    esito = importa_anagrafica(percorso)
    assert [d.cognome for d in esito.dipendenti] == ["Errato"]
    assert len(esito.avvisi) == 2
    assert "riga 2" in esito.avvisi[0] and "manca il codice fiscale" in esito.avvisi[0]
    assert "riga 3" in esito.avvisi[1] and "FNT************A" in esito.avvisi[1]


def test_orari_in_ore_con_virgola(tmp_path):
    percorso = salva(
        tmp_path,
        {
            "Dipendenti": [["CF"], [CF_LUCA]],
            "Orari": [
                [
                    "Cliente",
                    "Lunedì",
                    "Martedi",
                    "Mercoledì",
                    "Giovedì",
                    "Venerdì",
                    "Sabato",
                    "Domenica",
                ],
                ["Beta Spa", 8, "8", "7,5", 8, 8, 4, None],
            ],
        },
    )
    assert importa_anagrafica(percorso).orari == {
        "Beta Spa": OrarioSettimanale((480, 480, 450, 480, 480, 240, 0))
    }


def test_fogli_facoltativi_incompleti_o_valori_non_numerici(tmp_path):
    percorso = salva(
        tmp_path,
        {
            "Dipendenti": [["CF"], [CF_LUCA]],
            "Orari": [["Nome cliente", "Lunedì"], ["Alfa Srl", 8]],  # manca "Cliente"
            "Capienze": [["Codice", "Ferie"], ["201111111", 10]],  # manca "JobOrder"
        },
    )
    esito = importa_anagrafica(percorso)
    assert (esito.orari, esito.capienze) == ({}, {})

    percorso = salva(
        tmp_path,
        {
            "Dipendenti": [["CF"], [CF_LUCA]],
            "Orari": [["Cliente", "Lunedì", "Martedì"], ["Alfa Srl", "n/d", ""]],
            "Capienze": [["JobOrder", "Ferie", "ROL"], ["201111111", "n/d", None], ["202", 8, 4]],
        },
    )
    esito = importa_anagrafica(percorso)
    assert esito.orari == {"Alfa Srl": OrarioSettimanale((0, 0, 0, 0, 0, 0, 0))}
    assert esito.capienze == {"202": {"Ferie": 480, "ROL": 240}}  # riga senza valori: ignorata


def test_numeri_interi_letti_come_decimali():
    from assenze_desk.storage.anagrafica import _testo

    assert _testo(201111111.0) == "201111111"  # non "201111111.0"
    assert _testo(7.5) == "7.5"


def test_errori_chiari(tmp_path):
    with pytest.raises(FileNotFoundError):
        importa_anagrafica(tmp_path / "manca.xlsx")
    with pytest.raises(ValueError, match="Dipendenti"):
        importa_anagrafica(salva(tmp_path, {"Altro": [["CF"]]}))
    with pytest.raises(ValueError, match="codice fiscale"):
        importa_anagrafica(salva(tmp_path, {"Dipendenti": [["Cognome", "Nome"]]}))


def test_scelto_il_file_delle_pratiche_al_posto_dell_anagrafica(tmp_path):
    # Errore capitato davvero: il tracking delle malattie scelto come anagrafica
    tracking = salva(tmp_path, {"Foglio1": [["Protocollo", "CF", "DataInizio"]]})
    with pytest.raises(ValueError, match="si importa da Archivio"):
        importa_anagrafica(tracking)


def test_modello_vuoto(tmp_path):
    percorso = tmp_path / "modello.xlsx"
    scrivi_anagrafica(percorso, (), {}, {})
    esito = importa_anagrafica(percorso)
    assert (esito.dipendenti, esito.orari, esito.capienze, esito.avvisi) == ((), {}, {}, ())
