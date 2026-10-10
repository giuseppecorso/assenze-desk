"""Righe dei giustificativi e capienza (issue #2).

Un periodo di più giorni diventa una riga per giorno, con le ore del turno del
cliente; avviso se si supera la capienza di ferie o ROL.
"""

from datetime import date

from assenze_desk.core.giustificativi import (
    TIPI_PREDEFINITI,
    RigaGiustificativo,
    eccedenza_capienza,
    righe_giustificativo,
)
from assenze_desk.core.turni import OrarioSettimanale

FERIE, ROL, VISITA = TIPI_PREDEFINITI
ORARIO = OrarioSettimanale((480, 480, 480, 480, 480, 240, 0))  # sabato mezza giornata
LUNEDI, MARTEDI, SABATO, DOMENICA = (date(2026, 10, d) for d in (12, 13, 17, 18))


def test_ferie_una_riga_per_giorno_con_le_ore_dell_orario():
    righe = righe_giustificativo(FERIE, (LUNEDI, MARTEDI, SABATO), None, ORARIO)
    assert righe == [
        RigaGiustificativo(LUNEDI, "Ferie", "FER", 480),
        RigaGiustificativo(MARTEDI, "Ferie", "FER", 480),
        RigaGiustificativo(SABATO, "Ferie", "FER", 240),
    ]


def test_giorno_non_lavorativo_o_orario_mancante_riga_da_compilare():
    assert righe_giustificativo(FERIE, (DOMENICA,), None, ORARIO)[0].minuti is None
    assert righe_giustificativo(FERIE, (LUNEDI,), None, None)[0].minuti is None


def test_ore_scritte_valgono_per_ogni_giorno():
    righe = righe_giustificativo(ROL, (LUNEDI, MARTEDI), 120, ORARIO)
    assert [r.minuti for r in righe] == [120, 120]
    # anche per le ferie: mezza giornata scritta o confermata
    assert righe_giustificativo(FERIE, (LUNEDI,), 240, ORARIO)[0].minuti == 240


def test_permesso_senza_ore_riga_da_compilare():
    assert righe_giustificativo(VISITA, (LUNEDI,), None, ORARIO)[0].minuti is None


def test_nessun_giorno_nessuna_riga():
    assert righe_giustificativo(FERIE, (), None, ORARIO) == []


def test_ore_della_riga():
    assert RigaGiustificativo(LUNEDI, "ROL", "ROL", 90).ore == 1.5
    assert RigaGiustificativo(LUNEDI, "ROL", "ROL", None).ore is None


# --- Capienza ---


def test_eccedenza_capienza():
    righe = righe_giustificativo(FERIE, (LUNEDI, MARTEDI), None, ORARIO)  # 960 minuti
    assert eccedenza_capienza(righe, capienza_minuti=1200) == 0
    assert eccedenza_capienza(righe, capienza_minuti=960) == 0
    assert eccedenza_capienza(righe, capienza_minuti=600) == 360


def test_capienza_sconosciuta():
    righe = righe_giustificativo(FERIE, (LUNEDI,), None, ORARIO)
    assert eccedenza_capienza(righe, capienza_minuti=None) is None


def test_righe_da_compilare_non_contano():
    righe = righe_giustificativo(FERIE, (LUNEDI, DOMENICA), None, ORARIO)  # 480 + da compilare
    assert eccedenza_capienza(righe, capienza_minuti=400) == 80
