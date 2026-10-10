"""Divisione del testo di una mail in oggetto, corpo e intestazioni."""

from assenze_desk.core.mail import MailStrutturata, dividi_mail


def test_testo_completo():
    testo = (
        "OGG: Certificato di malattia\n"
        "Da: lavoratore@example.com\n"
        "Data: 05/01/2026 09:12\n"
        "\n"
        "Buongiorno,\n"
        "invio il certificato.\n"
    )
    assert dividi_mail(testo) == MailStrutturata(
        oggetto="Certificato di malattia",
        corpo="Buongiorno,\ninvio il certificato.",
        intestazioni="Da: lavoratore@example.com\nData: 05/01/2026 09:12",
    )


def test_oggetto_scritto_in_modi_diversi():
    for riga in ("Oggetto: Ferie", "oggetto:Ferie", "Subject: Ferie", "OGG: Ferie"):
        assert dividi_mail(riga + "\ntesto").oggetto == "Ferie", riga


def test_prima_riga_di_risposta_o_inoltro_vale_come_oggetto():
    for prefisso in ("R:", "RE:", "Re :", "I:", "FW:", "Fwd:"):
        mail = dividi_mail(f"{prefisso} Richiesta permesso\nGrazie")
        assert mail.oggetto == "Richiesta permesso", prefisso
        assert mail.corpo == "Grazie"


def test_intestazioni_anche_dentro_una_mail_inoltrata():
    testo = (
        "Vedi sotto\n"
        "Da: lavoratore@example.com\n"
        "Inviato: lunedì 5 gennaio 2026\n"
        "A: ufficio@example.com\n"
        "Cc: altro@example.com\n"
        "Oggetto: Malattia\n"
        "Ecco il protocollo"
    )
    mail = dividi_mail(testo)
    assert mail.oggetto == "Malattia"
    assert mail.corpo == "Vedi sotto\nEcco il protocollo"
    assert mail.intestazioni.splitlines() == [
        "Da: lavoratore@example.com",
        "Inviato: lunedì 5 gennaio 2026",
        "A: ufficio@example.com",
        "Cc: altro@example.com",
    ]


def test_solo_il_primo_oggetto_e_l_oggetto_gli_altri_sono_intestazioni():
    mail = dividi_mail("Oggetto: Primo\ntesto\nOggetto: Secondo")
    assert mail.oggetto == "Primo"
    assert mail.intestazioni == "Oggetto: Secondo"


def test_indirizzi_interni_di_exchange_tra_le_intestazioni():
    mail = dividi_mail("testo\n/o=ORGANIZZAZIONE/ou=GRUPPO/cn=Recipients/cn=utente")
    assert mail.corpo == "testo"
    assert mail.intestazioni.startswith("/o=")


def test_testo_semplice_tutto_nel_corpo():
    assert dividi_mail("  solo testo\r\nsu due righe  ") == MailStrutturata(
        oggetto="", corpo="solo testo\nsu due righe", intestazioni=""
    )


def test_testo_vuoto():
    assert dividi_mail("") == MailStrutturata(oggetto="", corpo="", intestazioni="")
    assert dividi_mail("   \n  ") == MailStrutturata(oggetto="", corpo="", intestazioni="")
