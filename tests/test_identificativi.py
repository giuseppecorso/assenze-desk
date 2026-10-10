"""Protocollo e JobOrder (issue #8 e #19).

Regola di scelta tra più numeri candidati (graduatoria a livelli):
prima i numeri sulla riga di una parola chiave (o sulla riga subito dopo), poi gli altri;
a parità, conta l'ordine delle sezioni (protocollo: corpo, oggetto; JobOrder: oggetto,
corpo); le intestazioni vengono per ultime; a parità ancora, vince il primo nel testo.
"""

import pytest

from assenze_desk.core.identificativi import (
    JOBORDER,
    PROTOCOLLO,
    RegolaNumero,
    estrai_joborder,
    estrai_protocollo,
)

# --- Protocollo: lettura del numero ---


def test_protocollo_semplice():
    assert estrai_protocollo("Il protocollo è 412345678, grazie") == "412345678"


NBSP = "\N{NO-BREAK SPACE}"  # spazio non separabile, frequente nei testi copiati da Outlook


@pytest.mark.parametrize(
    "scritto", ["412 345 678", "412-345-678", "4123-45678", f"412{NBSP}345{NBSP}678"]
)
def test_protocollo_con_spazi_o_trattini(scritto):
    assert estrai_protocollo(f"Protocollo {scritto}") == "412345678"


@pytest.mark.parametrize(
    "testo",
    [
        "Protocollo 4123456789",  # 10 cifre: non si tronca
        "Protocollo 312345678",  # prefisso sbagliato
        "Protocollo 412.345.678",  # punti: si confondono con le date
        "Protocollo 412/345/678",  # barre: idem
        "Protocollo 412 345\n678",  # un a capo separa sempre i numeri
        "Protocollo 412 345 678 901",  # fa parte di un numero più lungo
        "Malattia dal 4-12-2025 10 giorni",  # data seguita da un numero
        "Nessun numero qui",
        "",
    ],
)
def test_protocollo_non_trovato(testo):
    assert estrai_protocollo(testo) is None


def test_numero_attaccato_a_un_suffisso_o_a_una_data():
    assert estrai_protocollo("Protocollo 412345678-1") == "412345678"
    assert estrai_protocollo("certificato del 05-01-2026 412345678") == "412345678"


# --- Protocollo: scelta tra più candidati ---


def test_vince_il_numero_sulla_riga_della_parola_chiave():
    testo = "Pratica interna 498765432\nProt. 412345678 del 05/01/2026"
    assert estrai_protocollo(testo) == "412345678"


def test_parola_chiave_sulla_riga_prima():
    testo = "Riferimento 498765432\nNumero di protocollo:\n412345678"
    assert estrai_protocollo(testo) == "412345678"


def test_parola_chiave_solo_a_parola_intera():
    # "protocollato" non è "protocollo" né "prot"
    testo = "Documento protocollato 498765432\naltro 412345678"
    assert estrai_protocollo(testo) == "498765432"


def test_corpo_prima_dell_oggetto():
    testo = "Oggetto: richiesta 498765432\nil numero è 412345678"
    assert estrai_protocollo(testo) == "412345678"


def test_oggetto_con_parola_chiave_prima_del_corpo_senza():
    testo = "Oggetto: certificato 412345678\nriferimento 498765432"
    assert estrai_protocollo(testo) == "412345678"


def test_intestazioni_per_ultime():
    testo = "Data: 05/01/2026 498765432\n\nil numero è 412345678"
    assert estrai_protocollo(testo) == "412345678"
    assert estrai_protocollo("Data: 05/01/2026 498765432\n\nnessun numero") == "498765432"


def test_a_parita_vince_il_primo():
    assert estrai_protocollo("numeri 412345678 e 498765432") == "412345678"


def test_mai_uguale_al_joborder():
    # Con un JobOrder configurato con lo stesso prefisso del protocollo
    joborder_con_4 = RegolaNumero(lunghezza=9, prefissi=("4",), parole_chiave=("job",))
    testo = "Job 412 345 678\ncertificato in allegato"
    assert estrai_protocollo(testo, regola_joborder=joborder_con_4) is None
    testo += "\nprotocollo 498765432"
    assert estrai_protocollo(testo, regola_joborder=joborder_con_4) == "498765432"


def test_protocollo_con_lunghezza_e_prefissi_configurati():
    regola = RegolaNumero(lunghezza=10, prefissi=("5", "7"))  # anche senza parole chiave
    assert estrai_protocollo("prot 712 345 6789", regola=regola) == "7123456789"
    assert estrai_protocollo("prot 412345678", regola=regola) is None


# --- JobOrder ---


def test_joborder_semplice_e_con_separatori():
    assert estrai_joborder("JobOrder 201234567") == "201234567"
    assert estrai_joborder("job order: 201-234-567") == "201234567"


def test_joborder_prefisso_sbagliato():
    assert estrai_joborder("JobOrder 211234567") is None


def test_joborder_oggetto_prima_del_corpo():
    testo = "Oggetto: ferie 201111111\nriferimento 209999999"
    assert estrai_joborder(testo) == "201111111"


def test_joborder_parola_chiave_nel_corpo_prima_dell_oggetto_senza():
    testo = "Oggetto: ferie 201111111\nJob 209999999"
    assert estrai_joborder(testo) == "209999999"


# --- Impostazioni ---


def test_valori_predefiniti():
    assert (PROTOCOLLO.lunghezza, PROTOCOLLO.prefissi) == (9, ("4",))
    assert (JOBORDER.lunghezza, JOBORDER.prefissi) == (9, ("20",))


@pytest.mark.parametrize(
    "parametri",
    [
        {"lunghezza": 0, "prefissi": ("4",)},
        {"lunghezza": 9, "prefissi": ()},
        {"lunghezza": 9, "prefissi": ("4a",)},
        {"lunghezza": 3, "prefissi": ("4567",)},  # prefisso più lungo del numero
    ],
)
def test_impostazioni_non_valide(parametri):
    with pytest.raises(ValueError):
        RegolaNumero(**parametri)
