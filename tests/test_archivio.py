"""Archivio SQLite: pratiche, righe dei giustificativi, storico (issue #3 e #17)."""

import sqlite3
from contextlib import closing
from datetime import date, datetime

import pytest

from assenze_desk.core.stato import Stato
from assenze_desk.storage.archivio import Archivio, Pratica, RigaSalvata

CF_LUCA = "FNTPRV80A01Z999Y"
CF_ANNA = "TSTCSO92M45Z888V"


class Orologio:
    """Ora controllata dal test."""

    def __init__(self) -> None:
        self.ora = datetime(2026, 10, 7, 9, 0)

    def __call__(self) -> datetime:
        return self.ora


@pytest.fixture
def orologio():
    return Orologio()


@pytest.fixture
def archivio(orologio):
    with Archivio(":memory:", adesso=orologio) as archivio:
        yield archivio


def pratica(protocollo="411111111", cf=CF_LUCA, **altri):
    valori = {
        "protocollo": protocollo,
        "cf": cf,
        "dipendente": "Fittizio Luca",
        "joborder": "201111111",
        "cliente": "Alfa Srl",
        "inizio": date(2026, 10, 1),
        "fine": date(2026, 10, 3),
    }
    return Pratica(**{**valori, **altri})


# --- Pratiche ---


def test_salva_e_rilegge_una_pratica(archivio):
    archivio.salva_pratica(pratica(note="prima nota"))
    letta = archivio.pratica("411111111")
    assert letta.cf == CF_LUCA
    assert (letta.inizio, letta.fine) == (date(2026, 10, 1), date(2026, 10, 3))
    assert letta.note == "prima nota"
    assert letta.creata_il == letta.aggiornata_il == datetime(2026, 10, 7, 9, 0)


def test_pratica_inesistente(archivio):
    assert archivio.pratica("499999999") is None


def test_lo_stato_si_calcola_non_si_salva(archivio):
    archivio.salva_pratica(pratica())
    assert archivio.pratica("411111111").stato is Stato.DA_INVIARE
    archivio.aggiorna("411111111", mail_lavoratore=True)
    assert archivio.pratica("411111111").stato is Stato.CHIUSA


def test_stato_manuale_salvato(archivio):
    archivio.salva_pratica(pratica(cf=""))
    assert archivio.pratica("411111111").stato is Stato.INCOMPLETA
    archivio.aggiorna("411111111", stato_manuale=Stato.CHIUSA)
    assert archivio.pratica("411111111").stato is Stato.CHIUSA
    archivio.aggiorna("411111111", stato_manuale=None)  # torna automatico
    assert archivio.pratica("411111111").stato is Stato.INCOMPLETA


def test_una_modifica_aggiorna_solo_la_pratica_interessata(archivio, orologio):
    for protocollo in ("411111111", "422222222", "433333333"):
        archivio.salva_pratica(pratica(protocollo))
    modifiche_prima = archivio.modifiche_totali
    orologio.ora = datetime(2026, 10, 8, 10, 0)

    archivio.aggiorna("422222222", mail_lavoratore=True)

    assert archivio.modifiche_totali - modifiche_prima == 1  # una sola riga toccata
    assert archivio.pratica("422222222").aggiornata_il == datetime(2026, 10, 8, 10, 0)
    assert archivio.pratica("411111111").aggiornata_il == datetime(2026, 10, 7, 9, 0)
    assert archivio.pratica("422222222").creata_il == datetime(2026, 10, 7, 9, 0)


def test_salvare_di_nuovo_lo_stesso_protocollo_lo_aggiorna(archivio):
    archivio.salva_pratica(pratica(fine=date(2026, 10, 3)))
    archivio.salva_pratica(pratica(fine=date(2026, 10, 9)))
    assert len(archivio.pratiche()) == 1
    assert archivio.pratica("411111111").fine == date(2026, 10, 9)


def test_salvare_una_pratica_letta_non_cambia_la_data_di_creazione(archivio, orologio):
    archivio.salva_pratica(pratica())
    orologio.ora = datetime(2026, 10, 9, 15, 0)
    archivio.salva_pratica(archivio.pratica("411111111"))
    riletta = archivio.pratica("411111111")
    assert riletta.creata_il == datetime(2026, 10, 7, 9, 0)
    assert riletta.aggiornata_il == datetime(2026, 10, 9, 15, 0)


def test_aggiorna_campo_sconosciuto_o_pratica_inesistente(archivio):
    archivio.salva_pratica(pratica())
    with pytest.raises(ValueError):
        archivio.aggiorna("411111111", campo_inventato=1)
    with pytest.raises(KeyError):
        archivio.aggiorna("499999999", mail_lavoratore=True)


def test_elenco_pratiche_con_filtri(archivio):
    archivio.salva_pratica(pratica("411111111"))
    archivio.salva_pratica(pratica("422222222", cf=CF_ANNA, mail_lavoratore=True))
    assert [p.protocollo for p in archivio.pratiche()] == ["411111111", "422222222"]
    assert [p.protocollo for p in archivio.pratiche(cf=CF_ANNA.lower())] == ["422222222"]
    assert [p.protocollo for p in archivio.pratiche(stato=Stato.DA_INVIARE)] == ["411111111"]


def test_certificati_per_l_episodio(archivio):
    archivio.salva_pratica(pratica("411111111", inizio=date(2026, 10, 1), fine=date(2026, 10, 3)))
    archivio.salva_pratica(pratica("422222222", inizio=date(2026, 10, 4), fine=date(2026, 10, 6)))
    archivio.salva_pratica(pratica("433333333", cf=CF_ANNA))
    archivio.salva_pratica(pratica("444444444", inizio=None))  # senza date: non è un certificato
    certificati = archivio.certificati(CF_LUCA)
    assert [c.protocollo for c in certificati] == ["411111111", "422222222"]


# --- Righe dei giustificativi ---


def riga(giorno=12, minuti=480, codice="FER"):
    return RigaSalvata(
        cf=CF_LUCA,
        dipendente="Fittizio Luca",
        joborder="201111111",
        cliente="Alfa Srl",
        giorno=date(2026, 10, giorno),
        tipo="Ferie",
        codice=codice,
        minuti=minuti,
    )


def test_righe_aggiunte_ed_esportate(archivio):
    ids = archivio.aggiungi_righe([riga(12), riga(13, minuti=None)])
    assert len(ids) == 2
    assert [r.giorno.day for r in archivio.righe(solo_da_esportare=True)] == [12, 13]
    archivio.segna_esportate(ids[:1])
    assert [r.giorno.day for r in archivio.righe(solo_da_esportare=True)] == [13]
    assert [r.esportata for r in archivio.righe()] == [True, False]
    assert archivio.righe()[1].minuti is None


def test_modifica_ed_elimina_righe(archivio):
    [primo, secondo] = archivio.aggiungi_righe([riga(12), riga(13)])
    archivio.modifica_riga(primo, minuti=240)
    assert archivio.righe()[0].minuti == 240
    archivio.elimina_righe([secondo])
    assert [r.id for r in archivio.righe()] == [primo]


# --- Storico delle azioni ---


def test_storico_delle_azioni(archivio, orologio):
    archivio.registra("Bozza al lavoratore", protocollo="411111111")
    orologio.ora = datetime(2026, 10, 7, 9, 5)
    archivio.registra("Mail all'ufficio", protocollo="411111111", dettaglio="2 allegati")
    azioni = archivio.storico()
    assert [a.azione for a in azioni] == [
        "Mail all'ufficio",
        "Bozza al lavoratore",
    ]  # recenti prima
    assert azioni[0].dettaglio == "2 allegati"


def test_lo_storico_non_salva_codici_fiscali(archivio):
    archivio.registra("Nota", dettaglio=f"verificato {CF_LUCA}")
    assert CF_LUCA not in archivio.storico()[0].dettaglio


# --- File su disco ---


def test_i_dati_restano_dopo_la_chiusura(tmp_path, orologio):
    percorso = tmp_path / "archivio.db"
    with Archivio(percorso, adesso=orologio) as archivio:
        archivio.salva_pratica(pratica())
    with Archivio(percorso, adesso=orologio) as archivio:
        assert archivio.pratica("411111111").cf == CF_LUCA


def test_versione_dello_schema(tmp_path, orologio):
    percorso = tmp_path / "archivio.db"
    with Archivio(percorso, adesso=orologio):
        pass
    with closing(sqlite3.connect(percorso)) as connessione:  # "with connect" non chiude
        assert connessione.execute("PRAGMA user_version").fetchone()[0] == 1


def test_errori_di_uso(archivio):
    with pytest.raises(ValueError):
        archivio.salva_pratica(pratica(protocollo="  "))
    [id_riga] = archivio.aggiungi_righe([riga()])
    with pytest.raises(ValueError):
        archivio.modifica_riga(id_riga, cf="altro")


def test_date_e_ore_salvate_come_testo(archivio):
    archivio.salva_pratica(pratica())
    archivio.aggiorna("411111111", data_presentazione=date(2026, 10, 2), tempo_gestione_sec=95.5)
    letta = archivio.pratica("411111111")
    assert (letta.data_presentazione, letta.tempo_gestione_sec) == (date(2026, 10, 2), 95.5)
