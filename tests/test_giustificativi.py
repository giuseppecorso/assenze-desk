"""Tipi di giustificativo e parole chiave (issue #11).

Decisioni: con più tipi trovati non se ne sceglie nessuno, li sceglie l'utente (D25);
"permesso" da solo non è una parola chiave del ROL: mai ROL per ripiego.
"""

import pytest

from assenze_desk.core.giustificativi import (
    TIPI_PREDEFINITI,
    TipoGiustificativo,
    classifica_giustificativo,
)

FERIE, ROL, VISITA = TIPI_PREDEFINITI


def nomi(testo, tipi=TIPI_PREDEFINITI):
    return [tipo.nome for tipo in classifica_giustificativo(testo, tipi)]


def test_tipi_predefiniti_con_codici_di_esempio():
    assert [(t.nome, t.codice, t.a_giornata) for t in TIPI_PREDEFINITI] == [
        ("Ferie", "FER", True),  # si conta a giornate, con le ore del turno
        ("ROL", "ROL", False),
        ("Permesso visita medica", "PVM", False),
    ]


# --- Parole chiave a parola intera (problema noto 4) ---


@pytest.mark.parametrize("testo", ["controllo del protocollo", "Rolando", "enrollment"])
def test_rol_non_si_trova_dentro_altre_parole(testo):
    assert nomi(testo) == []


@pytest.mark.parametrize("testo", ["ROL", "chiedo 2 ore di rol, grazie", "permesso (rol)", "Rol."])
def test_rol_a_parola_intera(testo):
    assert nomi(testo) == ["ROL"]


@pytest.mark.parametrize(
    ("tipo", "parola"),
    [(tipo, parola) for tipo in TIPI_PREDEFINITI for parola in tipo.parole_chiave],
)
def test_ogni_parola_chiave_predefinita_solo_a_parola_intera(tipo, parola):
    assert tipo in classifica_giustificativo(f"Buongiorno, {parola}.")
    # attaccata ad altre lettere su entrambi i lati non vale più
    assert tipo not in classifica_giustificativo(f"Buongiorno, xyz{parola}xyz.")


def test_accenti_maiuscole_e_apostrofi_non_contano():
    assert nomi("Domani ENTRERÒ PIÙ TARDI") == ["ROL"]
    assert nomi("devo ritardare l’entrata di un'ora") == ["ROL"]


# --- Un tipo, nessuno o più di uno ---


def test_un_solo_tipo():
    assert nomi("Oggetto: Richiesta ferie\nvorrei 3 giorni di ferie") == ["Ferie"]
    assert nomi("ho una visita specialistica venerdì") == ["Permesso visita medica"]


def test_piu_tipi_in_ordine_di_comparsa():
    assert nomi("chiedo un permesso ROL per visita medica") == ["ROL", "Permesso visita medica"]
    assert nomi("visita medica, poi uscita anticipata") == ["Permesso visita medica", "ROL"]


@pytest.mark.parametrize(
    "testo",
    [
        "permesso 104 per il giorno 12",  # nella v6.20 diventava ROL
        "chiedo un permesso dalle 9 alle 11",  # "permesso" da solo non decide il tipo
        "buongiorno, a domani",
        "",
    ],
)
def test_nessun_tipo(testo):
    assert nomi(testo) == []


def test_parola_dentro_una_frase_chiave_piu_lunga_non_conta_da_sola():
    permesso_104 = TipoGiustificativo("Permesso 104", "P104", ("permesso 104",))
    generico = TipoGiustificativo("Permesso generico", "PG", ("permesso",))
    tipi = (generico, permesso_104)
    assert nomi("chiedo un permesso 104", tipi) == ["Permesso 104"]
    assert nomi("chiedo un permesso", tipi) == ["Permesso generico"]
    assert nomi("permesso 104 e un altro permesso", tipi) == ["Permesso 104", "Permesso generico"]


def test_tipi_configurati_al_posto_dei_predefiniti():
    smart = TipoGiustificativo("Lavoro agile", "SW", ("smart working", "lavoro agile"))
    assert nomi("domani in smart working", (smart,)) == ["Lavoro agile"]
    assert nomi("domani ferie", (smart,)) == []


def test_tipo_senza_parole_chiave_si_sceglie_solo_a_mano():
    a_mano = TipoGiustificativo("Altro", "ALT")
    assert nomi("qualsiasi testo", (a_mano,)) == []


@pytest.mark.parametrize(
    "parametri",
    [
        {"nome": "", "codice": "X"},
        {"nome": "Ferie", "codice": " "},
        {"nome": "Ferie", "codice": "FER", "parole_chiave": ("ferie", "  ")},
        {"nome": "Ferie", "codice": "FER", "parole_chiave": ("!!",)},  # vuota dopo la pulizia
    ],
)
def test_tipo_non_valido(parametri):
    with pytest.raises(ValueError):
        TipoGiustificativo(**parametri)
