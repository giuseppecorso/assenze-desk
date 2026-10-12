"""Risposta alla mail di malattia: a chi, con chi in copia, da quale casella.

Come nella v6.20: la lista del cliente (DL) in copia, la risposta dalla casella
del cliente se l'utente lo ha scelto, e per le mail girate da un collega una
risposta breve a lui. In più: la modalità collega si propone da sola quando il
mittente è interno e non è il lavoratore.
"""

from assenze_desk.core.dipendenti import Dipendente
from assenze_desk.core.risposte import Risposta, da_collega, indirizzi, scegli_risposta

CF = "FNTPRV80A01Z999Y"
LUCA = Dipendente(
    CF,
    "Fittizio",
    "Luca",
    email="luca@example.com",
    copia_cliente="alfa@example.com; capo.alfa@example.com",
)
INTERNI = ("azienda.example",)


def test_indirizzi_separati_da_punto_e_virgola_o_virgola():
    assert indirizzi(" a@example.com; b@example.com,a@example.com ;") == (
        "a@example.com",
        "b@example.com",
    )
    assert indirizzi("") == ()


def test_risposta_al_lavoratore_con_il_cliente_in_copia():
    risposta = scegli_risposta(dipendente=LUCA, mittente_mail="luca@example.com")
    assert risposta == Risposta(
        a=("luca@example.com",),
        cc=("alfa@example.com", "capo.alfa@example.com"),
        mittente="",
        collega=False,
    )


def test_risposta_dalla_casella_del_cliente():
    risposta = scegli_risposta(dipendente=LUCA, mittente_mail="", dalla_lista_cliente=True)
    assert risposta.mittente == "alfa@example.com"
    assert risposta.a == ("luca@example.com",)  # senza mail importata: l'indirizzo in anagrafica


def test_senza_dipendente_si_risponde_al_mittente():
    risposta = scegli_risposta(dipendente=None, mittente_mail="luca@example.com")
    assert risposta == Risposta(a=("luca@example.com",), cc=(), mittente="", collega=False)


def test_risposta_al_collega():
    risposta = scegli_risposta(
        dipendente=LUCA,
        mittente_mail="collega@azienda.example",
        collega=True,
        dalla_lista_cliente=True,
        mittente_collega="io@azienda.example",
    )
    # Risposta breve al collega: niente cliente in copia, dalla casella scelta per i colleghi
    assert risposta == Risposta(
        a=("collega@azienda.example",), cc=(), mittente="io@azienda.example", collega=True
    )


def test_la_mail_di_un_collega_si_riconosce_dal_dominio_interno():
    assert da_collega("collega@azienda.example", LUCA, INTERNI)
    assert da_collega("Collega@Sede.Azienda.Example", LUCA, INTERNI)
    assert not da_collega("luca@example.com", LUCA, INTERNI)
    # il lavoratore stesso con un indirizzo interno non è un collega
    interno = Dipendente(CF, "Fittizio", "Luca", email="luca@azienda.example")
    assert not da_collega("luca@azienda.example", interno, INTERNI)
    assert not da_collega("", LUCA, INTERNI)
    assert not da_collega("collega@azienda.example", LUCA, ())
