"""Adapter di Outlook Classic, provato con un Outlook finto (issue #4 e #10).

La prova con Outlook vero è nella checklist manuale della fase 3.
"""

from datetime import datetime

import pytest
from outlook_finto import Allegato, Mail, OutlookFinto

from assenze_desk.adapters.outlook import ErroreOutlook, MailImportata, Outlook


@pytest.fixture
def mail_a():
    return Mail("ID-A", "Certificato di malattia", "prot. 412345678", "lavoratore@example.com")


@pytest.fixture
def mail_b():
    return Mail("ID-B", "Altra mail", "altro", "altro@example.com")


# --- Import della mail selezionata ---


def test_importa_la_mail_selezionata(mail_a, mail_b):
    importata = Outlook(OutlookFinto(mail_a, mail_b)).mail_selezionata()
    assert importata == MailImportata(
        oggetto="Certificato di malattia",
        corpo="prot. 412345678",
        mittente="lavoratore@example.com",
        ricevuta=datetime(2026, 10, 7, 9, 15, 30),
        entry_id="ID-A",
        store_id="STORE-1",
    )


def test_testo_per_l_analisi(mail_a):
    importata = Outlook(OutlookFinto(mail_a)).mail_selezionata()
    assert importata.testo == (
        "OGG: Certificato di malattia\nDa: lavoratore@example.com\nData: 07/10/2026 09:15\n\n"
        "prot. 412345678"
    )


def test_mittente_interno_di_exchange(mail_a):
    mail_a.SenderEmailAddress = "/o=ORGANIZZAZIONE/ou=GRUPPO/cn=Recipients/cn=persona"
    assert Outlook(OutlookFinto(mail_a)).mail_selezionata().mittente == "persona@example.com"


def test_mittente_di_exchange_non_risolvibile(mail_a):
    mail_a.SenderEmailAddress = "/o=ORGANIZZAZIONE/cn=persona"
    mail_a.Sender = None  # Outlook non riesce a risalire all'indirizzo
    assert Outlook(OutlookFinto(mail_a)).mail_selezionata().mittente == ""


def test_nessuna_finestra_o_nessuna_mail_selezionata(mail_a):
    app = OutlookFinto(mail_a)
    app.explorer_attivo = False
    with pytest.raises(ErroreOutlook, match="Posta in arrivo"):
        Outlook(app).mail_selezionata()
    app = OutlookFinto()
    with pytest.raises(ErroreOutlook, match="seleziona"):
        Outlook(app).mail_selezionata()


# --- Risposta: sempre alla mail importata (problema noto 3) ---


def test_la_risposta_va_alla_mail_importata_anche_se_la_selezione_cambia(mail_a, mail_b):
    app = OutlookFinto(mail_a, mail_b)
    outlook = Outlook(app)
    importata = outlook.mail_selezionata()  # mail A
    app.seleziona(mail_b)  # nel frattempo in Outlook si seleziona un'altra mail

    outlook.bozza_risposta(importata, "<p>Gentile Luca,</p>", cc=["ufficio@example.com"])

    assert len(mail_a.risposte) == 1
    assert mail_b.risposte == []
    bozza = mail_a.risposte[0]
    assert bozza.HTMLBody == "<p>Gentile Luca,</p><p>messaggio originale</p>"
    assert bozza.CC == "ufficio@example.com"
    assert bozza.SentOnBehalfOfName == ""  # mittente: quello predefinito di Outlook
    assert bozza.mostrata  # aperta come bozza, mai inviata


def test_risposta_per_conto_di_un_altra_casella(mail_a):
    # Come nella v6.20: la risposta parte dalla casella del cliente (lista DL)
    app = OutlookFinto(mail_a)
    outlook = Outlook(app)
    outlook.bozza_risposta(outlook.mail_selezionata(), "<p>Ok</p>", mittente="alfa@example.com")
    assert mail_a.risposte[0].SentOnBehalfOfName == "alfa@example.com"


def test_mail_importata_non_piu_trovata_nessun_ripiego_sulla_selezione(mail_a, mail_b):
    app = OutlookFinto(mail_a, mail_b)
    outlook = Outlook(app)
    importata = outlook.mail_selezionata()
    app.mail.remove(mail_a)  # spostata o cancellata in Outlook
    with pytest.raises(ErroreOutlook, match="non è più"):
        outlook.bozza_risposta(importata, "<p>ciao</p>")
    assert mail_b.risposte == []


# --- Nuova bozza con allegati (mail all'ufficio) ---


def test_bozza_nuova_con_allegati(tmp_path, mail_a):
    app = OutlookFinto(mail_a)
    allegati = [tmp_path / "411111111.pdf", tmp_path / "422222222.pdf"]
    Outlook(app).bozza_nuova(
        a=["ufficio@example.com", "hr@example.com"],
        oggetto="Malattia",
        corpo_html="<p>In allegato</p>",
        cc=["copia@example.com"],
        allegati=allegati,
    )
    [bozza] = app.bozze_nuove
    assert (bozza.To, bozza.CC, bozza.Subject) == (
        "ufficio@example.com; hr@example.com",
        "copia@example.com",
        "Malattia",
    )
    assert bozza.HTMLBody == "<p>In allegato</p>"
    assert bozza.Attachments.percorsi == [str(p) for p in allegati]
    assert bozza.mostrata


# --- Allegati della mail importata ---


def test_salva_gli_allegati_della_mail_importata(tmp_path, mail_a, mail_b):
    mail_a.Attachments.elementi = [Allegato("certificato.pdf"), Allegato("certificato.pdf")]
    mail_b.Attachments.elementi = [Allegato("di_un_altra_mail.pdf")]
    app = OutlookFinto(mail_a, mail_b)
    outlook = Outlook(app)
    importata = outlook.mail_selezionata()
    app.seleziona(mail_b)

    salvati = outlook.salva_allegati(importata, tmp_path / "pdf")
    assert [p.name for p in salvati] == ["certificato.pdf", "certificato (2).pdf"]
    assert all(p.read_bytes() == b"%PDF-finto" for p in salvati)


# --- Spostamento in una cartella ---


@pytest.mark.parametrize(
    "percorso",
    ["Gestite/Malattie", "Gestite\\Malattie", "\\\\casella\\Posta in arrivo\\Gestite\\Malattie"],
)
def test_sposta_la_mail_importata(mail_a, percorso):
    outlook = Outlook(OutlookFinto(mail_a))
    importata = outlook.mail_selezionata()
    destinazione = outlook.sposta(importata, percorso)
    assert destinazione == "\\\\casella\\Posta in arrivo\\Gestite\\Malattie"
    assert mail_a.spostata_in.Name == "Malattie"


def test_cartella_inesistente(mail_a):
    outlook = Outlook(OutlookFinto(mail_a))
    importata = outlook.mail_selezionata()
    with pytest.raises(ErroreOutlook, match="Inesistente"):
        outlook.sposta(importata, "Gestite/Inesistente")
    assert mail_a.spostata_in is None
