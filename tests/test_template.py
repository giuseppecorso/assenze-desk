"""Template delle mail con escape dei dati (issue #18).

Segnaposti: {NOME_IN_MAIUSCOLO}. Il template è scritto dall'utente e resta com'è;
i dati inseriti, in HTML, sono sempre trattati come testo.
"""

import pytest

from assenze_desk.core.template import compila, segnaposti


def test_sostituisce_i_segnaposti():
    risultato = compila(
        "Prot. {PROTOCOLLO} per {CANDIDATO}",
        {"PROTOCOLLO": "412345678", "CANDIDATO": "Mario Finto"},
    )
    assert risultato.testo == "Prot. 412345678 per Mario Finto"
    assert risultato.mancanti == ()


@pytest.mark.parametrize(
    ("valore", "atteso"),
    [
        ("<b>grassetto</b>", "&lt;b&gt;grassetto&lt;/b&gt;"),
        ("Finto & Figli", "Finto &amp; Figli"),
        ('nota "urgente"', "nota &quot;urgente&quot;"),
        ("riga 1\nriga 2", "riga 1<br>riga 2"),
    ],
)
def test_in_html_i_dati_sono_testo(valore, atteso):
    assert compila("<p>{NOTE}</p>", {"NOTE": valore}, html=True).testo == f"<p>{atteso}</p>"


def test_in_testo_semplice_nessun_escape():
    # oggetto della mail e bozze mailto
    assert compila("Ditta: {CLIENTE}", {"CLIENTE": "Finto & Figli <srl>"}).testo == (
        "Ditta: Finto & Figli <srl>"
    )


def test_il_template_html_resta_com_e():
    template = "<style>p { color: red }</style><p>Gentile {NOME},</p>"
    assert compila(template, {"NOME": "Anna"}, html=True).testo == (
        "<style>p { color: red }</style><p>Gentile Anna,</p>"
    )


def test_un_dato_che_contiene_un_segnaposto_non_viene_sostituito_di_nuovo():
    valori = {"NOTE": "vedi {CF}", "CF": "FNTPRV80A01Z999Y"}
    assert compila("{NOTE} - {CF}", valori).testo == "vedi {CF} - FNTPRV80A01Z999Y"
    assert compila("{NOTE}", valori, html=True).testo == "vedi {CF}"


def test_segnaposti_senza_valore_restano_visibili_e_sono_elencati():
    risultato = compila(
        "Gentile {NOME} {COGNOME}, prot. {PROTOCOLLO}", {"NOME": "", "COGNOME": None}
    )
    assert risultato.testo == "Gentile {NOME} {COGNOME}, prot. {PROTOCOLLO}"
    assert risultato.mancanti == ("NOME", "COGNOME", "PROTOCOLLO")


def test_segnaposto_ripetuto():
    risultato = compila("{GIORNI} giorni ({GIORNI})", {"GIORNI": "3"})
    assert risultato.testo == "3 giorni (3)"


def test_solo_maiuscole_sono_segnaposti():
    risultato = compila("{nome} e {Nome} e { NOME }", {})
    assert risultato.testo == "{nome} e {Nome} e { NOME }"
    assert risultato.mancanti == ()


def test_elenco_dei_segnaposti():
    assert segnaposti("{NOME} {CF} {NOME} {GIORNI_EPISODIO}") == ["NOME", "CF", "GIORNI_EPISODIO"]
