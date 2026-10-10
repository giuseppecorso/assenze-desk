"""Vocabolario dei permessi: parole predefinite, estendibili dalle impostazioni."""

import pytest

from assenze_desk.core.vocabolario import VOCABOLARIO, Vocabolario


def test_parole_predefinite():
    assert VOCABOLARIO.unita_ore == ("ore", "ora", "h")
    assert "anziché" in VOCABOLARIO.invece


def test_estendi_aggiunge_senza_doppioni_e_senza_toccare_l_originale():
    esteso = VOCABOLARIO.estendi(unita_ore=["hr", "h"], invece=["piuttosto che"])
    assert esteso.unita_ore == ("ore", "ora", "h", "hr")
    assert esteso.invece[-1] == "piuttosto che"
    assert VOCABOLARIO.unita_ore == ("ore", "ora", "h")


def test_estendi_campo_sconosciuto():
    with pytest.raises(TypeError):
        VOCABOLARIO.estendi(parole_inventate=["x"])


@pytest.mark.parametrize("parole", [("ore", ""), ("ore", "  "), ()])
def test_parole_non_valide(parole):
    with pytest.raises(ValueError):
        Vocabolario(unita_ore=parole)
