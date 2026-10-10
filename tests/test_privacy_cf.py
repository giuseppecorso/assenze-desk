"""Mascheramento del codice fiscale in log, storico e messaggi."""

import pytest

from assenze_desk.core.privacy import maschera_cf


@pytest.mark.parametrize(
    ("testo", "atteso"),
    [
        ("CF FNTPRV80A01Z999Y ok", "CF FNT************Y ok"),
        ("cf fntprv80a01z999y", "cf fnt************y"),
        ("due: FNTPRV80A01Z999Y e TSTCSO92M45Z888V", "due: FNT************Y e TST************V"),
        (
            "anche con carattere sbagliato FNTPRV80A01Z999A",
            "anche con carattere sbagliato FNT************A",
        ),
        ("protocollo 412345678", "protocollo 412345678"),
        ("XFNTPRV80A01Z999Y", "XFNTPRV80A01Z999Y"),  # non è un CF a sé
        ("", ""),
    ],
)
def test_maschera_cf(testo, atteso):
    assert maschera_cf(testo) == atteso
