"""Statistiche (issue #2): tempo medio di gestione senza valori anomali e riepilogo."""

from datetime import date

from assenze_desk.core.statistiche import PraticaStatistica, riepilogo, tempo_medio
from assenze_desk.core.stato import Stato

# --- Tempo medio: esclusi i valori oltre media + 10 minuti, ricalcolato più volte ---


def test_tempo_medio_scarta_un_valore_anomalo():
    risultato = tempo_medio([600, 660, 720, 3600])
    assert risultato.media_sec == 660
    assert risultato.scartati == (3600,)


def test_tempo_medio_ricalcolato_piu_volte():
    # 1° giro: media 1550, soglia 2150 → via 4000; 2° giro: media 733, soglia 1333 → via 1500
    risultato = tempo_medio([300, 400, 1500, 4000])
    assert risultato.media_sec == 350
    assert risultato.validi == (300, 400)
    assert risultato.scartati == (4000, 1500)


def test_tempo_medio_senza_anomalie():
    assert tempo_medio([600, 700]).scartati == ()
    assert tempo_medio([600, 700]).media_sec == 650


def test_tempo_medio_con_soglia_e_giri_configurati():
    assert tempo_medio([600, 900], minuti_oltre_la_media=1).media_sec == 600
    assert tempo_medio([300, 400, 1500, 4000], giri=1).media_sec == 2200 / 3


def test_tempo_medio_senza_dati():
    risultato = tempo_medio([0, -5])
    assert risultato.media_sec is None
    assert risultato.validi == ()


def test_media_in_minuti():
    assert tempo_medio([600, 660, 720]).media_min == 11
    assert tempo_medio([]).media_min is None


# --- Riepilogo ---


def pratica(
    protocollo, cf, nome, cliente, inizio, fine, stato=Stato.CHIUSA, episodio=None, tempo=None
):
    return PraticaStatistica(
        protocollo=protocollo,
        cf=cf,
        dipendente=nome,
        cliente=cliente,
        inizio=inizio,
        fine=fine,
        giorni_episodio=episodio,
        stato=stato,
        tempo_gestione_sec=tempo,
    )


PRATICHE = [
    pratica(
        "411111111",
        "CF1",
        "Fittizio Luca",
        "Alfa Srl",
        date(2026, 9, 1),
        date(2026, 9, 3),
        tempo=600,
    ),
    pratica(
        "422222222",
        "CF1",
        "Fittizio Luca",
        "Alfa Srl",
        date(2026, 10, 1),
        date(2026, 10, 5),
        episodio=5,
        tempo=720,
    ),
    pratica(
        "433333333",
        "CF2",
        "Esempio Anna",
        "Beta Spa",
        date(2026, 10, 2),
        date(2026, 10, 2),
        Stato.DA_INVIARE,
    ),
    pratica("", "", "", "", None, None, Stato.INCOMPLETA, tempo=6000),
]


def test_riepilogo_numeri_principali():
    r = riepilogo(PRATICHE)
    assert (r.pratiche, r.dipendenti, r.clienti) == (4, 2, 2)
    assert r.giorni == 9  # 3 + 5 + 1, la pratica senza date non conta
    assert r.media_giorni_per_pratica == 3  # 9 giorni / 3 pratiche con date
    assert r.episodi_lunghi == 1
    assert r.percentuale_episodi_lunghi == 25.0


def test_riepilogo_per_stato_in_ordine():
    assert riepilogo(PRATICHE).per_stato == {
        Stato.INCOMPLETA: 1,
        Stato.DA_INVIARE: 1,
        Stato.PARZIALE: 0,
        Stato.CHIUSA: 2,
    }


def test_riepilogo_giorni_per_mese():
    assert riepilogo(PRATICHE).giorni_per_mese == {"2026-09": 3, "2026-10": 6}


def test_classifiche_per_giorni_senza_cf_nelle_etichette():
    r = riepilogo(PRATICHE)
    assert r.per_cliente == [("Alfa Srl", 8, 2), ("Beta Spa", 1, 1)]
    assert r.per_dipendente == [("Fittizio Luca", 8, 2), ("Esempio Anna", 1, 1)]


def test_tempo_medio_nel_riepilogo():
    assert riepilogo(PRATICHE).tempo.media_sec == 660  # 6000 scartato


def test_riepilogo_con_soglie_delle_impostazioni():
    r = riepilogo(PRATICHE, soglia_ufficio=5, minuti_oltre_la_media=100)
    assert r.episodi_lunghi == 0  # 5 giorni non superano la soglia di 5
    assert r.tempo.media_sec == 2440  # con 100 minuti di margine nessun valore è anomalo


def test_riepilogo_vuoto():
    r = riepilogo([])
    assert (r.pratiche, r.giorni, r.media_giorni_per_pratica, r.percentuale_episodi_lunghi) == (
        0,
        0,
        0,
        0,
    )
    assert r.tempo.media_sec is None
