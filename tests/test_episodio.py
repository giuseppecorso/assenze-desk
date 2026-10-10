"""Episodio di malattia (issue #2).

I certificati dello stesso CF contigui (uno finisce il giorno prima dell'inizio
dell'altro) o sovrapposti formano un episodio. Una continuazione si aggancia al
certificato che finisce il giorno prima del suo inizio. La mail all'ufficio serve
oltre 3 giorni di episodio e allega i PDF di tutti i certificati dell'episodio.
"""

from datetime import date

import pytest

from assenze_desk.core.episodio import Certificato, calcola_episodio, certificato_precedente
from assenze_desk.core.stato import serve_mail_ufficio

CF = "FNTPRV80A01Z999Y"
ALTRO_CF = "TSTCSO92M45Z888V"


def cert(protocollo, inizio, fine, cf=CF):
    return Certificato(protocollo, cf, date(2026, 10, inizio), date(2026, 10, fine))


A = cert("411111111", 1, 3)
B = cert("422222222", 4, 6)  # contiguo ad A
C = cert("433333333", 7, 8)  # contiguo a B


def test_certificato_da_solo():
    episodio = calcola_episodio(A, [])
    assert (episodio.inizio, episodio.fine, episodio.giorni) == (
        date(2026, 10, 1),
        date(2026, 10, 3),
        3,
    )
    assert episodio.protocolli == ("411111111",)


def test_certificati_contigui():
    episodio = calcola_episodio(B, [A])
    assert (episodio.inizio, episodio.fine, episodio.giorni) == (
        date(2026, 10, 1),
        date(2026, 10, 6),
        6,
    )
    assert episodio.protocolli == ("411111111", "422222222")


def test_certificati_sovrapposti():
    episodio = calcola_episodio(cert("422222222", 4, 8), [cert("411111111", 1, 5)])
    assert (episodio.inizio, episodio.fine) == (date(2026, 10, 1), date(2026, 10, 8))


def test_catena_di_certificati_in_qualsiasi_ordine():
    episodio = calcola_episodio(C, [B, A])
    assert episodio.protocolli == ("411111111", "422222222", "433333333")
    assert episodio.giorni == 8


def test_anche_i_certificati_successivi_entrano_nell_episodio():
    assert calcola_episodio(A, [C, B]).giorni == 8


def test_un_giorno_di_pausa_separa_gli_episodi():
    episodio = calcola_episodio(cert("422222222", 5, 6), [A])  # A finisce il 3, questo inizia il 5
    assert episodio.protocolli == ("422222222",)


def test_altro_codice_fiscale_non_conta():
    assert calcola_episodio(B, [cert("411111111", 1, 3, cf=ALTRO_CF)]).protocolli == ("422222222",)


def test_codice_fiscale_in_minuscolo_o_con_spazi():
    assert calcola_episodio(B, [cert("411111111", 1, 3, cf=f" {CF.lower()} ")]).giorni == 6


def test_il_certificato_gia_in_archivio_non_si_conta_due_volte():
    assert calcola_episodio(B, [A, B]).protocolli == ("411111111", "422222222")


def test_mail_all_ufficio_oltre_3_giorni():
    assert not serve_mail_ufficio(calcola_episodio(A, []).giorni)
    assert serve_mail_ufficio(calcola_episodio(B, [A]).giorni)


# --- Continuazione ---


def test_certificato_precedente():
    assert certificato_precedente(B, [A, C]) == A


def test_nessun_precedente_con_un_giorno_di_pausa_o_altro_cf():
    assert certificato_precedente(cert("422222222", 5, 6), [A]) is None
    assert certificato_precedente(B, [cert("411111111", 1, 3, cf=ALTRO_CF)]) is None


def test_tra_piu_precedenti_il_piu_recente():
    recente = cert("405555555", 2, 3)  # finisce come A ma inizia dopo
    assert certificato_precedente(B, [A, recente]) == recente
    assert certificato_precedente(B, [recente, A]) == recente


def test_certificato_non_valido():
    with pytest.raises(ValueError):
        cert("411111111", 5, 3)
