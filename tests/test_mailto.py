"""Bozze mailto, per chi non usa Outlook Classic (issue #4)."""

from assenze_desk.adapters.mailto import apri_bozza_mailto, url_mailto


def test_url_mailto():
    url = url_mailto(
        a=["lavoratore@example.com", "altro@example.com"],
        oggetto="Ricezione certificato - prot. 412345678",
        corpo="Gentile Luca,\nricevuto & grazie.",
        cc=["ufficio@example.com"],
    )
    assert url == (
        "mailto:lavoratore@example.com;altro@example.com"
        "?cc=ufficio@example.com"
        "&subject=Ricezione%20certificato%20-%20prot.%20412345678"
        "&body=Gentile%20Luca%2C%0D%0Aricevuto%20%26%20grazie."
    )


def test_url_mailto_minimo():
    assert url_mailto(a=["a@example.com"], oggetto="", corpo="") == "mailto:a@example.com"


def test_apri_bozza_mailto():
    aperti = []
    apri_bozza_mailto("mailto:a@example.com", apri=aperti.append)
    assert aperti == ["mailto:a@example.com"]
