"""Controllo privacy (scripts/check_privacy.py), provato solo con termini finti.

Le email e i percorsi da bloccare sono costruiti a pezzi ("C:" + ...): scritti per
intero farebbero bloccare il commit di questo stesso file.
"""

import zipfile
from pathlib import Path

import pytest
from check_privacy import REGOLE_FISSE, controlla_file, controlla_testo, main, regole_denylist

DENYLIST_FINTA = """\
# .privacy-denylist.txt (finta, per i test)

termine-finto
mare
Nome Inventato
esatto:SIGLAFINTA
re:(?i)rapporto\\s+n\\.\\s*\\d+
"""

UTENTI = "C:" + "\\Users\\"  # inizio di un percorso personale di Windows
DOMINIO_FINTO = "@" + "azienda-finta.it"  # dominio non ammesso


def trova(testo, denylist=DENYLIST_FINTA):
    return controlla_testo(testo, "f.txt", regole_denylist(denylist) + REGOLE_FISSE)


# --- Denylist: tipi di riga ---


def test_parola_intera_con_maiuscole_indifferenti():
    assert len(trova("C'è un TERMINE-FINTO qui")) == 1
    assert len(trova("vista sul Mare.")) == 1
    assert trova("sono amareggiato, maremma") == []  # termine dentro altre parole


def test_underscore_e_punteggiatura_separano_le_parole():
    assert len(trova("tema_mare")) == 1
    assert len(trova("(termine-finto)")) == 1


def test_termine_di_piu_parole_anche_diviso_da_un_a_capo():
    assert len(trova("firmato: Nome Inventato")) == 1
    [segnalazione] = trova("riga uno\nfirmato: Nome\nInventato")
    assert segnalazione.dove == "f.txt:2"


def test_esatto_rispetta_le_maiuscole_e_blocca_dentro_gli_identificatori():
    assert len(trova("TEMA_SIGLAFINTA")) == 1
    assert trova("siglafinta") == []
    assert trova("SIGLAFINTA3 e SIGLAFINTAscheduler") == []  # sigla seguita da cifre o lettere


def test_regex_usata_cosi_com_e():
    assert len(trova("vedi Rapporto n. 123")) == 1
    assert trova("server su 127.0.0.1, porta 123") == []  # numeri fuori contesto


def test_commenti_e_righe_vuote_ignorati():
    assert regole_denylist("# termine-finto\n\n   \n") == []


def test_regex_non_valida_segnalata_senza_mostrarla():
    with pytest.raises(ValueError, match="riga 2") as errore:
        regole_denylist("# commento\nre:segreto[")
    assert "segreto" not in str(errore.value)


def test_segnala_la_riga_della_denylist():
    [segnalazione] = trova("termine-finto")
    assert "riga 3 della denylist" in segnalazione.descrizione


# --- Regole fisse, valide anche senza denylist ---


def test_email_ammesse_solo_su_domini_di_esempio():
    assert len(trova("scrivi a persona" + DOMINIO_FINTO, denylist="")) == 1
    assert len(trova("altro" + "@anthropic.com", denylist="")) == 1
    ammesse = (
        "a@example.com b@uffici.example.org c@example.net d@posta.test "
        "e@host.invalid 123+utente@users.noreply.github.com noreply@anthropic.com"
    )
    assert trova(ammesse, denylist="") == []


def test_percorsi_personali_bloccati_salvo_segnaposto():
    for percorso in (UTENTI + "nome\\Desktop", "C:" + "/Users/nome", "C:" + "\\\\Users\\\\nome"):
        assert len(trova(percorso, denylist="")) == 1, percorso
    for segnaposto in ("<utente>\\Desktop", "%USERNAME%", "{utente}", "$env:USERNAME"):
        assert trova(UTENTI + segnaposto, denylist="") == [], segnaposto


def test_cartelle_onedrive_aziendali_bloccate_salvo_segnaposto():
    assert len(trova("OneDrive" + " - Azienda Finta\\Documenti", denylist="")) == 1
    assert trova("OneDrive - <organizzazione> e OneDrive personale", denylist="") == []


# --- File: nome, testo, Office, binari ---
# Come in pre-commit, i file si passano con il percorso relativo alla cartella di lavoro.


@pytest.fixture(autouse=True)
def cartella_di_lavoro(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _regole():
    return regole_denylist(DENYLIST_FINTA) + REGOLE_FISSE


def _scrivi(nome, testo="niente di strano"):
    Path(nome).write_text(testo, encoding="utf-8")
    return nome


@pytest.mark.parametrize("nome", ["mail.msg", "copia.EML", "lavoro.xlsm", "archivio.pst", "a.ost"])
def test_estensioni_vietate(nome):
    [segnalazione] = controlla_file(_scrivi(nome), _regole())
    assert "estensione" in segnalazione.descrizione


@pytest.mark.parametrize("nome", [".privacy-denylist.txt", ".privacy-denylist.bak"])
def test_la_denylist_non_entra_mai_nel_repo(nome):
    [segnalazione] = controlla_file(_scrivi(nome, "# vuota\n"), _regole())
    assert "denylist" in segnalazione.descrizione


def test_termine_nel_nome_del_file_segnalato_e_mascherato():
    [segnalazione] = controlla_file(_scrivi("note_termine-finto.txt"), _regole())
    assert "nome del file" in segnalazione.dove
    assert "termine-finto" not in str(segnalazione)


def test_file_di_testo_con_bom_e_fine_riga_windows():
    Path("note.txt").write_bytes("riga pulita\r\nc'è termine-finto\r\n".encode("utf-8-sig"))
    [segnalazione] = controlla_file("note.txt", _regole())
    assert segnalazione.dove == "note.txt:2"


def test_file_office_controllati_dentro():
    with zipfile.ZipFile("documento.docx", "w", zipfile.ZIP_DEFLATED) as archivio:
        archivio.writestr("word/styles.xml", "<w:styles/>")
        archivio.writestr("word/document.xml", "<w:t>vista sul mare</w:t>")
    [segnalazione] = controlla_file("documento.docx", _regole())
    assert segnalazione.dove == "documento.docx/word/document.xml:1"


def test_file_binari_letti_come_latin1():
    Path("immagine.bin").write_bytes(b"\x89\xff\x00 SIGLAFINTA \xfe")
    assert len(controlla_file("immagine.bin", _regole())) == 1


# --- Uso da riga di comando ---


@pytest.fixture
def denylist():
    return _scrivi("denylist.txt", DENYLIST_FINTA)


def test_file_puliti_passano(denylist):
    assert main(["--denylist", denylist, _scrivi("pulito.py", "x = 1\n")]) == 0


def test_output_mascherato(denylist, capsys):
    sporco = _scrivi("sporco.txt", "riga 1\nil termine-finto\n")
    assert main(["--denylist", denylist, sporco]) == 1
    uscita = capsys.readouterr().out
    assert "sporco.txt:2: termine vietato alla riga 3 della denylist (te***)" in uscita
    assert "termine-finto" not in uscita


def test_messaggio_di_commit(denylist):
    messaggio = _scrivi("COMMIT_EDITMSG", "fix: corretto il caso Nome Inventato\n")
    assert main(["--denylist", denylist, "--commit-msg", messaggio]) == 1
    _scrivi(messaggio, "fix: corretto il caso\n\nCo-Authored-By: X <noreply@anthropic.com>\n")
    assert main(["--denylist", denylist, "--commit-msg", messaggio]) == 0


def test_denylist_mancante_blocca_e_spiega(capsys):
    assert main(["--denylist", "manca.txt", _scrivi("pulito.py", "x = 1\n")]) == 1
    assert "un termine vietato per riga" in capsys.readouterr().err
