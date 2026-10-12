"""Copie di sicurezza dell'archivio: una al giorno, le ultime 14, controllo di integrità."""

from datetime import date, timedelta

from assenze_desk.storage.archivio import Archivio, Pratica
from assenze_desk.storage.backup import COPIE_DA_TENERE, copia_di_sicurezza, integro

OGGI = date(2026, 10, 12)


def archivio_con_una_pratica(tmp_path):
    archivio = Archivio(tmp_path / "archivio.db")
    archivio.salva_pratica(Pratica(protocollo="412345678", cf="FNTPRV80A01Z999Y"))
    return archivio


def test_una_copia_al_giorno_leggibile(tmp_path):
    with archivio_con_una_pratica(tmp_path) as archivio:
        cartella = tmp_path / "backup"
        copia = copia_di_sicurezza(archivio, cartella, OGGI)
        assert copia == cartella / "archivio-2026-10-12.db"
        assert copia_di_sicurezza(archivio, cartella, OGGI) is None  # oggi c'è già
    with Archivio(copia) as ripristinato:  # la copia è un archivio completo
        assert ripristinato.pratica("412345678") is not None


def test_si_tengono_solo_le_ultime_copie(tmp_path):
    cartella = tmp_path / "backup"
    cartella.mkdir()
    altro = cartella / "appunti.txt"
    altro.write_text("non è una copia", encoding="utf-8")
    with archivio_con_una_pratica(tmp_path) as archivio:
        for giorni in range(COPIE_DA_TENERE + 3):
            copia_di_sicurezza(archivio, cartella, OGGI + timedelta(days=giorni))
    copie = sorted(cartella.glob("archivio-*.db"))
    assert len(copie) == COPIE_DA_TENERE
    assert copie[0].name == f"archivio-{OGGI + timedelta(days=3):%Y-%m-%d}.db"
    assert altro.exists()  # gli altri file della cartella non si toccano


def test_integrita(tmp_path):
    with archivio_con_una_pratica(tmp_path) as archivio:
        assert archivio.integro()
    assert integro(tmp_path / "archivio.db")
    assert integro(tmp_path / "non-esiste-ancora.db")  # verrà creato
    rovinato = tmp_path / "rovinato.db"
    rovinato.write_bytes(b"SQLite format 3" + bytes([0]) + bytes([0xFF]) * 4096)
    assert not integro(rovinato)
