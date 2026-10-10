"""Codice fiscale: formato, carattere di controllo ed estrazione dal testo.

Tutti i CF sono inventati. Il carattere di controllo atteso è stato calcolato con
l'algoritmo ufficiale, verificato prima su un esempio pubblico di manuale.
Un CF con il carattere di controllo sbagliato viene scartato (decisione D22).
"""

import pytest

from assenze_desk.core.codice_fiscale import (
    carattere_di_controllo,
    cf_valido,
    estrai_cf,
    trova_codici_fiscali,
)

CF_UOMO = "FNTPRV80A01Z999Y"
CF_DONNA = "TSTCSO92M45Z888V"  # giorno + 40 per le donne
CF_OMOCODICO = "FNTPRVULALMZ999J"  # cifre sostituite da lettere (L=0, M=1, U=8)
CF_OMOCODICO_2 = "FNTPRV80A01Z9QQQ"  # Q=4


@pytest.mark.parametrize("cf", [CF_UOMO, CF_DONNA, CF_OMOCODICO, CF_OMOCODICO_2])
def test_carattere_di_controllo(cf):
    assert carattere_di_controllo(cf[:15]) == cf[15]


@pytest.mark.parametrize("cf", [CF_UOMO, CF_DONNA, CF_OMOCODICO, CF_OMOCODICO_2])
def test_cf_validi(cf):
    assert cf_valido(cf)
    assert cf_valido(cf.lower())


@pytest.mark.parametrize(
    "cf",
    [
        "FNTPRV80A01Z999A",  # carattere di controllo sbagliato
        "FNTPRV8OA01Z999Y",  # OCR: lettera O al posto dello zero
        "FNTPRV80A01Z999",  # 15 caratteri
        "FNTPRV80A01Z999YY",  # 17 caratteri
        "FNTPRV80F01Z999Y",  # F non è una lettera di mese
        "FNTPRV80A01Z99AY",  # A non sostituisce una cifra
        "1NTPRV80A01Z999Y",  # cifra al posto di una lettera del cognome
        "",
    ],
)
def test_cf_non_validi(cf):
    assert not cf_valido(cf)


# --- Estrazione dal testo ---


def test_estrae_il_cf_dal_testo():
    assert estrai_cf(f"Il mio codice fiscale è {CF_UOMO}, grazie") == CF_UOMO


def test_minuscole_e_spazi_in_mezzo():
    assert estrai_cf(f"cf: {CF_DONNA.lower()}") == CF_DONNA
    assert estrai_cf("CF FNT PRV 80A01 Z999Y.") == CF_UOMO


def test_cf_con_controllo_sbagliato_scartato():
    assert estrai_cf("CF FNTPRV80A01Z999A") is None


def test_salta_quelli_non_validi_e_prende_il_primo_valido():
    testo = f"letto male FNTPRV80A01Z999A, corretto {CF_DONNA}, collega {CF_UOMO}"
    assert estrai_cf(testo) == CF_DONNA
    assert trova_codici_fiscali(testo) == [CF_DONNA, CF_UOMO]


def test_nessun_doppione():
    assert trova_codici_fiscali(f"{CF_UOMO} e ancora {CF_UOMO.lower()}") == [CF_UOMO]


@pytest.mark.parametrize(
    "testo",
    [
        f"X{CF_UOMO}",  # attaccato ad altre lettere
        f"{CF_UOMO}9",  # attaccato ad altre cifre
        "CF FNTPRV80A01\nZ999Y",  # un a capo separa sempre
        "nessun codice fiscale qui",
        "",
    ],
)
def test_nessun_cf(testo):
    assert estrai_cf(testo) is None


def test_parole_vicine_non_si_uniscono_al_cf():
    assert estrai_cf(f"da {CF_UOMO}") == CF_UOMO
    assert estrai_cf(f"cf {CF_UOMO} ok") == CF_UOMO
