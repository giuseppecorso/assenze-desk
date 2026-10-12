"""Import dei dati della v6.20: pratiche dal tracking delle malattie e righe dei
giustificativi, dai due file Excel che la vecchia versione aggiornava.

Solo dati finti, file creati nel test con le colonne della v6.20.
"""

from datetime import date, datetime

import pytest
from openpyxl import Workbook

from assenze_desk.core.stato import Stato
from assenze_desk.storage.archivio import Archivio, Pratica
from assenze_desk.storage.import_v620 import importa_in_archivio, leggi_file_v620

CF = "FNTPRV80A01Z999Y"
TRACKING = [
    "Timestamp", "JobOrder", "Candidato", "Cliente", "Protocollo",
    "DataInizio", "DataFine", "DataVisita", "DataPresentazione",
    "CF", "Giorni", "GiorniEpisodio",
    "TipoCertificato", "TipoVisita", "SpunteCertificato", "ProtocolloPrecedente",
    "MailLav", "MailUff", "StatoManuale", "Stato",
    "TimerStart", "TimerEnd", "TempoGestioneSec", "TempoGestioneMin", "TempoTrigger", "TempoSource",
]  # fmt: skip
GIUSTIFICATIVI = [
    "Timestamp", "JobOrder", "Cliente", "Candidato", "CodiceFiscale",
    "Dal", "Al", "Giorno", "NumeroGiorni", "TipoGiustificativo", "CodiceGiustificativo",
    "OreTurno", "QuantitaOre", "TestoOriginale", "Fonte", "Stato",
]  # fmt: skip


def salva(tmp_path, nome, intestazioni, righe):
    libro = Workbook()
    foglio = libro.active
    foglio.append(intestazioni)
    for valori in righe:
        foglio.append([valori.get(colonna) for colonna in intestazioni])
    percorso = tmp_path / nome
    libro.save(percorso)
    return percorso


@pytest.fixture
def archivio(tmp_path):
    archivio = Archivio(tmp_path / "archivio.db", adesso=lambda: datetime(2026, 10, 12, 9, 0))
    yield archivio
    archivio.chiudi()


# --- Tracking delle malattie ---


def test_pratiche_dal_tracking(tmp_path):
    percorso = salva(
        tmp_path,
        "Tracking_Malattie.xlsx",
        TRACKING,
        [
            {
                "Protocollo": 412345678,  # numero in Excel
                "CF": CF.lower(),
                "Candidato": "Fittizio Luca",
                "JobOrder": "201111111",
                "Cliente": "Alfa Srl",
                "DataInizio": "05/10/2026",
                "DataFine": datetime(2026, 10, 9),
                "DataPresentazione": "06/10/2026",
                "GiorniEpisodio": "5",
                "MailLav": "SI",
                "MailUff": "NO",
                "StatoManuale": "NO",
                "Stato": "Parziale",
                "TempoGestioneSec": "312,5",
            },
            {
                "Protocollo": "412345679",
                "CF": CF,
                "MailLav": "si",
                "StatoManuale": "SI",
                "Stato": "Chiusa",
            },
        ],
    )
    dati = leggi_file_v620(percorso)
    assert dati.tipo == "malattie"
    prima, seconda = dati.pratiche
    assert prima == Pratica(
        protocollo="412345678",
        cf=CF,
        dipendente="Fittizio Luca",
        joborder="201111111",
        cliente="Alfa Srl",
        inizio=date(2026, 10, 5),
        fine=date(2026, 10, 9),
        data_presentazione=date(2026, 10, 6),
        giorni_episodio=5,
        mail_lavoratore=True,
        mail_ufficio=False,
        stato_manuale=None,  # lo stato automatico si ricalcola con le regole nuove
        tempo_gestione_sec=312.5,
    )
    assert seconda.stato_manuale is Stato.CHIUSA  # lo stato messo a mano resta
    assert seconda.mail_lavoratore is True
    assert dati.avvisi == ()


def test_righe_senza_protocollo_o_con_valori_illeggibili(tmp_path):
    percorso = salva(
        tmp_path,
        "tracking.xlsx",
        TRACKING,
        [
            {"CF": CF, "DataInizio": "05/10/2026"},
            {"Protocollo": "412345678", "CF": CF, "DataInizio": "abc", "StatoManuale": "SI"},
        ],
    )
    dati = leggi_file_v620(percorso)
    [pratica] = dati.pratiche
    assert pratica.inizio is None  # meglio vuoto che sbagliato
    assert pratica.stato_manuale is None  # "SI" senza uno stato valido
    assert dati.avvisi == ("riga 2: manca il protocollo, non importata",)


# --- Giustificativi ---


def test_righe_dei_giustificativi(tmp_path):
    percorso = salva(
        tmp_path,
        "db_giustificativi.xlsx",
        GIUSTIFICATIVI,
        [
            {
                "CodiceFiscale": CF,
                "Candidato": "Fittizio Luca",
                "JobOrder": "201111111",
                "Cliente": "Alfa Srl",
                "Dal": "12/10/2026",
                "Al": "12/10/2026",
                "Giorno": "12/10/2026",
                "TipoGiustificativo": "Ferie",
                "CodiceGiustificativo": "FER",
                "QuantitaOre": 7.5,
                "Stato": "Da esportare",
            },
            {
                "CodiceFiscale": CF,
                "Giorno": datetime(2026, 10, 13),
                "TipoGiustificativo": "ROL",
                "QuantitaOre": "2,5",
            },
            {  # vecchio salvataggio di un periodo in una riga sola: non si inventa la divisione
                "CodiceFiscale": CF,
                "Dal": "14/10/2026",
                "Al": "16/10/2026",
                "Giorno": "dal 14/10/2026 al 16/10/2026",
                "TipoGiustificativo": "Ferie",
                "QuantitaOre": 24,
            },
        ],
    )
    dati = leggi_file_v620(percorso)
    assert dati.tipo == "giustificativi"
    prima, seconda = dati.righe
    assert (prima.giorno, prima.tipo, prima.codice, prima.minuti) == (
        date(2026, 10, 12),
        "Ferie",
        "FER",
        450,
    )
    assert prima.cf == CF and prima.dipendente == "Fittizio Luca"
    assert prima.esportata  # la v6.20 non segnava l'export: sono già state gestite
    assert (seconda.giorno, seconda.minuti) == (date(2026, 10, 13), 150)
    assert dati.avvisi == ("riga 4: più giorni in una riga, non importata (inseriscila a mano)",)


# --- File non riconosciuto ---


def test_file_non_riconosciuto(tmp_path):
    percorso = salva(tmp_path, "altro.xlsx", ["A", "B"], [{"A": 1}])
    with pytest.raises(ValueError, match="non sembra un file della versione precedente"):
        leggi_file_v620(percorso)


# --- Nell'archivio ---


def test_import_nell_archivio_senza_doppioni_e_senza_sovrascrivere(tmp_path, archivio):
    archivio.salva_pratica(Pratica("412345678", CF, note="già lavorata nella versione nuova"))
    tracking = salva(
        tmp_path,
        "tracking.xlsx",
        TRACKING,
        [{"Protocollo": "412345678", "CF": CF}, {"Protocollo": "412345679", "CF": CF}],
    )
    esito = importa_in_archivio(archivio, leggi_file_v620(tracking))
    assert (esito.nuove, esito.gia_presenti) == (1, 1)
    assert archivio.pratica("412345678").note == "già lavorata nella versione nuova"
    assert archivio.pratica("412345679") is not None

    giust = salva(
        tmp_path,
        "giust.xlsx",
        GIUSTIFICATIVI,
        [{"CodiceFiscale": CF, "Giorno": "12/10/2026", "TipoGiustificativo": "Ferie"}],
    )
    assert importa_in_archivio(archivio, leggi_file_v620(giust)).nuove == 1
    di_nuovo = importa_in_archivio(archivio, leggi_file_v620(giust))
    assert (di_nuovo.nuove, di_nuovo.gia_presenti) == (0, 1)  # importare due volte non duplica
    assert len(archivio.righe()) == 1
    assert "Importate" in archivio.storico()[0].azione
