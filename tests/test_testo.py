"""Normalizzazione del testo per cercare parole chiave."""

import pytest

from assenze_desk.core.testo import normalizza, senza_accenti


def test_senza_accenti_tiene_la_punteggiatura():
    assert (
        senza_accenti("Entrerò PIÙ tardi: 2,5 ore, un’ora") == "entrero piu tardi: 2,5 ore, un'ora"
    )


@pytest.mark.parametrize(
    ("testo", "atteso"),
    [
        ("Entrerò PIÙ tardi", "entrero piu tardi"),
        ("ritardare l’entrata", "ritardare l entrata"),  # apostrofo tipografico
        ("ritardare l'entrata", "ritardare l entrata"),
        ("  ROL,  (rol)\n-ferie-  ", "rol rol ferie"),
        ("", ""),
    ],
)
def test_normalizza(testo, atteso):
    assert normalizza(testo) == atteso
