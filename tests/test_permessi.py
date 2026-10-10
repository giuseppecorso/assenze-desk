"""Lettura completa di una richiesta di permesso (issue #15, passo 3c).

Regole (D32): tipo, giorni e ore si cercano in oggetto e corpo, non nelle
intestazioni; le ore scritte (durate, fasce, orari spostati) vincono su
mattina/pomeriggio, che sono solo proposte dal turno; per i tipi "a giornata"
(Ferie) senza ore scritte valgono le ore del turno; ogni dubbio diventa una
segnalazione sul campo interessato e il campo resta vuoto.
"""

from datetime import date, time

from assenze_desk.core.orari import Intervallo
from assenze_desk.core.permessi import leggi_permesso
from assenze_desk.core.turni import Turno

MAIL = date(2026, 10, 7)  # mercoledì
TURNO = Turno(Intervallo(time(9), time(13)), Intervallo(time(14), time(18)))


def leggi(testo, turno=TURNO):
    return leggi_permesso(testo, MAIL, turno)


def campi_segnalati(permesso):
    return [segnalazione.campo for segnalazione in permesso.segnalazioni]


def test_richiesta_completa_senza_dubbi():
    permesso = leggi(
        "Oggetto: Richiesta permesso ROL\n"
        "Buongiorno, chiedo un permesso ROL per lunedì dalle 9 alle 11.\nGrazie"
    )
    assert permesso.tipo.nome == "ROL"
    assert permesso.giorni == (date(2026, 10, 12),)
    assert permesso.minuti == 120
    assert permesso.intervallo == Intervallo(time(9), time(11))
    assert permesso.segnalazioni == ()


def test_mattina_proposta_dal_turno_da_confermare():
    permesso = leggi("Buongiorno, domani mattina ho una visita medica, chiedo il permesso.")
    assert permesso.tipo.nome == "Permesso visita medica"
    assert permesso.giorni == (date(2026, 10, 8),)
    assert permesso.minuti == 240
    assert campi_segnalati(permesso) == ["ore"]
    assert "da confermare" in permesso.segnalazioni[0].messaggio


def test_mattina_senza_turno():
    permesso = leggi("domani mattina ho una visita medica", turno=None)
    assert permesso.minuti is None
    assert campi_segnalati(permesso) == ["ore"]


def test_pomeriggio_con_turno_solo_di_mattina():
    part_time = Turno(mattina=Intervallo(time(8), time(12)))
    permesso = leggi("domani pomeriggio ho una visita medica", turno=part_time)
    assert permesso.minuti is None
    assert permesso.segnalazioni[0].messaggio.startswith("Ore del pomeriggio non disponibili")


def test_ore_scritte_vincono_sulla_mattina():
    permesso = leggi("lunedì mattina dalle 9 alle 11 per visita medica")
    assert permesso.minuti == 120
    assert permesso.segnalazioni == ()


def test_ferie_a_giornata_con_le_ore_del_turno_e_weekend_da_decidere():
    permesso = leggi("Vorrei chiedere le ferie dal 12/10 al 18/10")
    assert permesso.tipo.nome == "Ferie"
    assert permesso.giorni == tuple(date(2026, 10, d) for d in range(12, 17))
    assert permesso.giorni_weekend == (date(2026, 10, 17), date(2026, 10, 18))
    assert permesso.minuti == 480  # giornata intera del turno, senza conferma
    assert campi_segnalati(permesso) == ["giorni"]
    assert "sabato o domenica" in permesso.segnalazioni[0].messaggio


def test_ferie_senza_turno():
    permesso = leggi("ferie domani", turno=None)
    assert permesso.minuti is None
    assert campi_segnalati(permesso) == ["ore"]


def test_mezza_giornata_di_ferie():
    permesso = leggi("ferie domani pomeriggio")
    assert permesso.minuti == 240
    assert campi_segnalati(permesso) == ["ore"]  # proposta da confermare


def test_ore_in_contrasto_restano_vuote():
    permesso = leggi("chiedo un permesso orario di 2 ore lunedì dalle 9 alle 12")
    assert permesso.minuti is None
    assert permesso.intervallo == Intervallo(time(9), time(12))
    assert campi_segnalati(permesso) == ["ore"]
    assert "contrasto" in permesso.segnalazioni[0].messaggio


def test_piu_tipi_possibili():
    permesso = leggi("chiedo un permesso ROL per visita medica giovedì, 2 ore")
    assert permesso.tipo is None
    assert [t.nome for t in permesso.tipi] == ["ROL", "Permesso visita medica"]
    assert campi_segnalati(permesso) == ["tipo"]


def test_tipo_e_giorno_non_trovati():
    permesso = leggi("esco alle 16 anziché alle 18")
    assert permesso.tipo is None
    assert permesso.minuti == 120
    assert campi_segnalati(permesso) == ["tipo", "giorni"]


def test_date_delle_intestazioni_ignorate():
    permesso = leggi("Da: lavoratore@example.com\nData: 05/10/2026 09:12\n\nchiedo ferie domani")
    assert permesso.giorni == (date(2026, 10, 8),)


def test_orari_con_h_non_diventano_durate():
    permesso = leggi("permesso orario domani dalle 9h alle 11h")
    assert permesso.minuti == 120
    assert permesso.segnalazioni == ()


def test_periodo_con_giorni_della_settimana():
    permesso = leggi("ferie da lunedì a venerdì")
    assert permesso.giorni == tuple(date(2026, 10, d) for d in range(12, 17))
    assert permesso.giorni_weekend == ()


def test_giorno_ripetuto_dentro_il_periodo_non_si_duplica():
    permesso = leggi("ferie dal 12/10 al 14/10, cioè da lunedì 12")
    assert permesso.giorni == (date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14))


def test_sabato_chiesto_esplicitamente():
    permesso = leggi("ferie sabato")
    assert permesso.giorni == (date(2026, 10, 10),)
    assert permesso.giorni_weekend == ()


def test_piu_giorni_con_la_stessa_fascia():
    permesso = leggi("permesso orario lunedì e martedì dalle 9 alle 11")
    assert permesso.giorni == (date(2026, 10, 12), date(2026, 10, 13))
    assert permesso.minuti == 120
    assert permesso.segnalazioni == ()


def test_parti_della_giornata_diverse():
    permesso = leggi("visita medica lunedì mattina e martedì pomeriggio")
    assert permesso.minuti is None
    assert campi_segnalati(permesso) == ["ore"]


def test_nessuna_ora_per_un_permesso_non_a_giornata():
    permesso = leggi("permesso per visita medica giovedì")
    assert permesso.minuti is None
    assert campi_segnalati(permesso) == ["ore"]
