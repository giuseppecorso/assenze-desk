"""Analisi di una mail: proposte per i campi, con l'origine di ogni dato (issue #5)."""

from datetime import date, datetime

from assenze_desk.core.analisi import (
    RegoleAnalisi,
    completa_con_dipendente,
    intestazioni_mail,
    proposta_dipendente,
    proposte_certificato,
    proposte_malattia,
    proposte_permesso,
    unisci,
)
from assenze_desk.core.campi import Origine, Proposta
from assenze_desk.core.certificato import DatiCertificato
from assenze_desk.core.dipendenti import Dipendente, EsitoMatch
from assenze_desk.core.permessi import leggi_permesso

CF = "FNTPRV80A01Z999Y"
MAIL = (
    "OGG: Certificato di malattia\n"
    "Da: Anna Esempio <Anna.Esempio@example.com>\n"
    "Data: 07/10/2026 09:12\n\n"
    "Buongiorno,\n"
    "invio il certificato protocollo 412 345 678 dal 5 al 9 ottobre.\n"
    f"Codice fiscale {CF}, JobOrder 201234567.\n\n"
    "Cordiali saluti\nAnna Esempio"
)
OGGI = date(2026, 10, 7)
ANNA = Dipendente(CF, "Esempio", "Anna", joborder="201234567", cliente="Alfa Srl")


def certificato(**altri):
    valori = {
        "protocollo": "412345678",
        "cf": CF,
        "cognome": "Esempio",
        "nome": "Anna",
        "inizio": date(2026, 10, 5),
        "fine": date(2026, 10, 10),
        "data_visita": date(2026, 10, 5),
        "tipo": "Inizio",
        "visita": "Ambulatoriale",
        "segnalazioni": (),
    }
    return DatiCertificato(**{**valori, **altri})


# --- Intestazioni di una mail incollata ---


def test_mittente_e_data_dalle_intestazioni():
    assert intestazioni_mail(MAIL) == ("anna.esempio@example.com", datetime(2026, 10, 7, 9, 12))


def test_intestazioni_di_outlook_copiate_con_il_mese_in_lettere():
    testo = "From: a@example.com\nInviato: martedì 7 ottobre 2026 09:12\n\nciao"
    assert intestazioni_mail(testo) == ("a@example.com", datetime(2026, 10, 7, 9, 12))


def test_senza_intestazioni():
    assert intestazioni_mail("chiedo ferie domani") == ("", None)
    assert intestazioni_mail("Data: 07/10/2026\n\nciao") == ("", datetime(2026, 10, 7))


# --- Malattia ---


def test_proposte_dal_testo_della_mail_di_malattia():
    proposte = proposte_malattia(MAIL, OGGI, RegoleAnalisi())
    assert proposte == {
        "protocollo": Proposta("412345678", Origine.TESTO),
        "cf": Proposta(CF, Origine.TESTO),
        "joborder": Proposta("201234567", Origine.TESTO),
        "inizio": Proposta(date(2026, 10, 5), Origine.TESTO),
        "fine": Proposta(date(2026, 10, 9), Origine.TESTO),
    }


def test_testo_senza_dati_nessuna_proposta():
    assert proposte_malattia("Buongiorno, a domani", OGGI, RegoleAnalisi()) == {}


def test_piu_periodi_nel_testo_date_vuote_e_segnalate():
    testo = "malattia dal 5 al 9 ottobre, poi ancora dal 12 al 14 ottobre"
    proposte = proposte_malattia(testo, OGGI, RegoleAnalisi())
    for campo in ("inizio", "fine"):
        assert proposte[campo].valore is None
        assert "più periodi" in proposte[campo].avviso


def test_proposte_dal_certificato_pdf():
    proposte = proposte_certificato(certificato())
    assert proposte["protocollo"] == Proposta("412345678", Origine.PDF)
    assert proposte["fine"] == Proposta(date(2026, 10, 10), Origine.PDF)
    assert proposte["tipo_certificato"] == Proposta("Inizio", Origine.PDF)


def test_le_segnalazioni_del_certificato_vanno_sul_campo_giusto():
    dati = certificato(
        cf=None,
        fine=None,
        tipo=None,
        segnalazioni=(
            "Nel certificato manca il codice fiscale.",
            "Nel certificato manca la data di fine.",
            "Le spunte della sezione 'Trattasi di' non sono leggibili: scegli a mano.",
        ),
    )
    proposte = proposte_certificato(dati)
    assert proposte["cf"].avviso == "Nel certificato manca il codice fiscale."
    assert proposte["fine"].avviso == "Nel certificato manca la data di fine."
    assert "Trattasi di" in proposte["tipo_certificato"].avviso
    assert proposte["inizio"].avviso == ""


def test_il_pdf_vince_sul_testo():
    unite = unisci(
        proposte_malattia(MAIL, OGGI, RegoleAnalisi()), proposte_certificato(certificato())
    )
    assert unite["fine"].valore == date(2026, 10, 10)
    assert unite["fine"].origine is Origine.PDF
    assert "09/10/2026" in unite["fine"].avviso  # la mail diceva un'altra data
    assert unite["protocollo"] == Proposta("412345678", Origine.PDF)  # uguali: nessun avviso
    assert unite["joborder"] == Proposta("201234567", Origine.TESTO)  # solo nella mail


def test_dato_mancante_nel_pdf_preso_dalla_mail():
    dati = certificato(cf=None, segnalazioni=("Nel certificato manca il codice fiscale.",))
    unite = unisci(proposte_malattia(MAIL, OGGI, RegoleAnalisi()), proposte_certificato(dati))
    assert unite["cf"] == Proposta(CF, Origine.TESTO)


def test_dato_mancante_ovunque_resta_l_avviso_del_pdf():
    dati = certificato(fine=None, segnalazioni=("Nel certificato manca la data di fine.",))
    unite = unisci(
        proposte_malattia("protocollo 412345678", OGGI, RegoleAnalisi()), proposte_certificato(dati)
    )
    assert unite["fine"] == Proposta(avviso="Nel certificato manca la data di fine.")


# --- Dipendente ---


def test_dipendente_trovato_in_automatico():
    proposta = proposta_dipendente(EsitoMatch(ANNA, (ANNA,), "JobOrder"))
    assert proposta == Proposta(ANNA, Origine.ANAGRAFICA)


def test_piu_dipendenti_possibili_sceglie_l_utente():
    altra = Dipendente("TSTCSO92M45Z888V", "Esempio", "Anna", cliente="Beta Spa")
    proposta = proposta_dipendente(EsitoMatch(None, (ANNA, altra), "nome nel testo"))
    assert proposta.valore is None
    assert proposta.scelte == (ANNA, altra)
    assert "scegli" in proposta.avviso


def test_dipendente_non_trovato():
    proposta = proposta_dipendente(EsitoMatch(None, (), ""))
    assert proposta.valore is None
    assert "cercalo" in proposta.avviso


def test_cf_e_joborder_presi_dall_anagrafica_se_mancano():
    proposte = completa_con_dipendente({"protocollo": Proposta("412345678", Origine.TESTO)}, ANNA)
    assert proposte["cf"] == Proposta(CF, Origine.ANAGRAFICA)
    assert proposte["joborder"] == Proposta("201234567", Origine.ANAGRAFICA)
    # quelli trovati nel testo restano
    proposte = completa_con_dipendente({"cf": Proposta(CF, Origine.PDF)}, ANNA)
    assert proposte["cf"] == Proposta(CF, Origine.PDF)
    assert completa_con_dipendente({}, None) == {}


# --- Permessi ---


def test_proposte_del_permesso():
    permesso = leggi_permesso("chiedo un permesso ROL per domani dalle 9 alle 11", OGGI)
    proposte = proposte_permesso(permesso)
    assert proposte["tipo"] == Proposta("ROL", Origine.TESTO)
    assert proposte["giorni"] == Proposta((date(2026, 10, 8),), Origine.TESTO)
    assert proposte["minuti"] == Proposta(120, Origine.TESTO)
    assert proposte["weekend"] == Proposta(None)


def test_permesso_con_piu_tipi_e_weekend():
    permesso = leggi_permesso("ferie e visita medica dal 9 al 13 ottobre", OGGI)
    proposte = proposte_permesso(permesso)
    assert proposte["tipo"].valore is None
    assert proposte["tipo"].scelte == ("Ferie", "Permesso visita medica")
    assert "Più tipi" in proposte["tipo"].avviso
    assert proposte["giorni"].valore == (date(2026, 10, 9), date(2026, 10, 12), date(2026, 10, 13))
    assert proposte["giorni"].avviso == ""
    assert proposte["weekend"].valore == (date(2026, 10, 10), date(2026, 10, 11))


def test_permesso_senza_dati():
    proposte = proposte_permesso(leggi_permesso("buongiorno", OGGI))
    assert proposte["tipo"].avviso and proposte["giorni"].avviso
    assert proposte["minuti"].valore is None
