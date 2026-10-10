"""Normalizzazione del testo per cercare parole chiave."""

import pytest

from assenze_desk.core.testo import normalizza


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
