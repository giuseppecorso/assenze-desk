"""Campi della pratica: origine del dato e campi manuali protetti (issue #5).

Regole del brief: un campo modificato a mano non viene più sovrascritto
dall'analisi; si vede da dove viene ogni dato; "ripristina valore automatico";
i campi incerti sono evidenziati.
"""

from datetime import date

import pytest

from assenze_desk.core.campi import Modulo, Origine, Proposta

FINE_PDF = Proposta(date(2026, 10, 9), Origine.PDF)


@pytest.fixture
def modulo():
    return Modulo(["protocollo", "cf", "fine", "tipo"])


def test_l_analisi_compila_i_campi_con_l_origine(modulo):
    modulo.proponi(
        {"protocollo": Proposta("412345678", Origine.TESTO), "cf": Proposta("X", Origine.PDF)}
    )
    assert modulo["protocollo"].valore == "412345678"
    assert modulo["protocollo"].origine is Origine.TESTO
    assert modulo["cf"].origine is Origine.PDF
    assert modulo["fine"].valore is None
    assert modulo["fine"].origine is None


def test_un_campo_modificato_a_mano_non_viene_piu_sovrascritto(modulo):
    modulo.proponi({"fine": FINE_PDF})
    assert modulo.scrivi("fine", date(2026, 10, 10)) is True
    nuova = Proposta(date(2026, 10, 11), Origine.TESTO)
    modulo.proponi({"fine": nuova})

    campo = modulo["fine"]
    assert campo.valore == date(2026, 10, 10)
    assert campo.origine is Origine.MANUALE
    assert campo.manuale
    assert campo.proposta == nuova  # mostrato come "Automatico: 11/10/2026"
    assert campo.automatico_diverso


def test_ripristina_il_valore_automatico(modulo):
    modulo.proponi({"fine": FINE_PDF})
    modulo.scrivi("fine", date(2026, 10, 10))
    modulo.ripristina("fine")
    assert modulo["fine"].valore == date(2026, 10, 9)
    assert modulo["fine"].origine is Origine.PDF
    assert not modulo["fine"].manuale
    assert not modulo["fine"].automatico_diverso


def test_svuotare_un_campo_a_mano_e_una_scelta_protetta(modulo):
    modulo.proponi({"protocollo": Proposta("412345678", Origine.TESTO)})
    modulo.scrivi("protocollo", "  ")
    assert modulo["protocollo"].valore is None
    assert modulo["protocollo"].manuale
    modulo.proponi({"protocollo": Proposta("412345678", Origine.TESTO)})
    assert modulo["protocollo"].valore is None


def test_riscrivere_lo_stesso_valore_non_lo_rende_manuale(modulo):
    # Le caselle dell'interfaccia riscrivono il valore anche quando non cambia
    modulo.proponi({"protocollo": Proposta("412345678", Origine.TESTO)})
    assert modulo.scrivi("protocollo", "412345678") is False
    assert not modulo["protocollo"].manuale


def test_campo_incerto_con_avviso_e_scelte(modulo):
    modulo.proponi(
        {"tipo": Proposta(None, avviso="Trovati più tipi: scegli tu.", scelte=("Ferie", "ROL"))}
    )
    assert modulo["tipo"].incerto
    assert modulo["tipo"].scelte == ("Ferie", "ROL")
    modulo.scrivi("tipo", "ROL")
    assert not modulo["tipo"].incerto
    assert modulo["tipo"].origine is Origine.MANUALE


def test_un_campo_incerto_puo_avere_un_valore_da_confermare(modulo):
    modulo.proponi({"fine": Proposta(date(2026, 10, 9), Origine.PDF, avviso="Controlla.")})
    assert modulo["fine"].valore == date(2026, 10, 9)
    assert modulo["fine"].incerto


def test_un_dato_non_piu_trovato_svuota_il_campo_automatico(modulo):
    modulo.proponi({"protocollo": Proposta("412345678", Origine.TESTO)})
    modulo.proponi({})
    assert modulo["protocollo"].valore is None


def test_proposte_per_campi_che_il_modulo_non_ha_si_ignorano(modulo):
    modulo.proponi({"joborder": Proposta("201234567", Origine.TESTO)})
    assert "joborder" not in modulo.nomi


def test_valori_e_svuota(modulo):
    modulo.proponi({"protocollo": Proposta("412345678", Origine.TESTO)})
    modulo.scrivi("cf", "FNTPRV80A01Z999Y")
    assert modulo.valori() == {
        "protocollo": "412345678",
        "cf": "FNTPRV80A01Z999Y",
        "fine": None,
        "tipo": None,
    }
    modulo.svuota()
    assert set(modulo.valori().values()) == {None}
    assert not modulo["cf"].manuale


def test_campo_sconosciuto(modulo):
    with pytest.raises(KeyError):
        modulo.scrivi("inventato", 1)
    with pytest.raises(KeyError):
        modulo.ripristina("inventato")
