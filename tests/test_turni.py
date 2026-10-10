"""Turno del cliente e mezza giornata (issue #15, passo 3a).

"Mattina" o "pomeriggio" propongono le ore della parte di turno corrispondente;
la proposta va confermata dall'utente. Senza turno non si propone niente.
"""

from datetime import time

import pytest

from assenze_desk.core.orari import Intervallo
from assenze_desk.core.turni import Turno, minuti_parte, trova_parti_giornata
from assenze_desk.core.vocabolario import VOCABOLARIO

TURNO = Turno(mattina=Intervallo(time(9), time(13)), pomeriggio=Intervallo(time(14), time(18)))


# --- Parti della giornata nel testo ---


@pytest.mark.parametrize(
    ("testo", "parti"),
    [
        ("chiedo un permesso per lunedì mattina", ["mattina"]),
        ("esco stamattina", ["mattina"]),
        ("domattina ho una visita", ["mattina"]),
        ("in mattinata", ["mattina"]),
        ("al mattino", ["mattina"]),
        ("domani pomeriggio", ["pomeriggio"]),
        ("ferie tutto il giorno", ["giornata"]),
        ("permesso per l'intera giornata", ["giornata"]),
        ("lunedì mattina e martedì pomeriggio", ["mattina", "pomeriggio"]),
        ("mattina... sì, di mattina", ["mattina"]),
        ("buongiorno", []),
        ("il mattinale", []),
        ("", []),
    ],
)
def test_parti_della_giornata(testo, parti):
    assert trova_parti_giornata(testo) == parti


def test_parole_aggiunte_dalle_impostazioni():
    esteso = VOCABOLARIO.estendi(pomeriggio=["dopo pranzo"])
    assert trova_parti_giornata("esco dopo pranzo") == []
    assert trova_parti_giornata("esco dopo pranzo", esteso) == ["pomeriggio"]


# --- Minuti proposti dal turno ---


def test_minuti_dal_turno():
    assert minuti_parte("mattina", TURNO) == 240
    assert minuti_parte("pomeriggio", TURNO) == 240
    assert minuti_parte("giornata", TURNO) == 480


def test_turno_con_mezze_ore():
    turno = Turno(Intervallo(time(8, 30), time(12, 30)), Intervallo(time(13, 30), time(17)))
    assert (minuti_parte("mattina", turno), minuti_parte("pomeriggio", turno)) == (240, 210)
    assert minuti_parte("giornata", turno) == 450


def test_turno_solo_di_mattina():
    part_time = Turno(mattina=Intervallo(time(8), time(12)))
    assert minuti_parte("mattina", part_time) == 240
    assert minuti_parte("pomeriggio", part_time) is None
    assert minuti_parte("giornata", part_time) == 240


def test_senza_turno_nessuna_proposta():
    assert minuti_parte("mattina", None) is None


@pytest.mark.parametrize(
    "parametri",
    [
        {},  # nessuna parte
        {"mattina": Intervallo(time(13), time(9))},  # finisce prima di iniziare
        {"mattina": Intervallo(time(9), time(14)), "pomeriggio": Intervallo(time(13), time(18))},
    ],
)
def test_turno_non_valido(parametri):
    with pytest.raises(ValueError):
        Turno(**parametri)
