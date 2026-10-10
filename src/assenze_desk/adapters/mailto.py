"""Bozze con il programma di posta predefinito (link mailto), senza allegati.

Per chi non usa Outlook Classic. Il corpo è testo semplice: gli a capo diventano
CRLF come vuole lo standard dei link mailto. La mail resta sempre una bozza.
"""

import os
import webbrowser
from collections.abc import Callable, Sequence
from urllib.parse import quote


def url_mailto(a: Sequence[str], oggetto: str, corpo: str, cc: Sequence[str] = ()) -> str:
    parametri = []
    if cc:
        parametri.append(("cc", ";".join(cc)))
    if oggetto:
        parametri.append(("subject", oggetto))
    if corpo:
        parametri.append(("body", corpo.replace("\r\n", "\n").replace("\n", "\r\n")))
    query = "&".join(f"{nome}={quote(valore, safe='@;')}" for nome, valore in parametri)
    return f"mailto:{quote(';'.join(a), safe='@;')}" + (f"?{query}" if query else "")


def apri_bozza_mailto(url: str, apri: Callable[[str], object] | None = None) -> None:
    """Apre la bozza nel programma di posta predefinito di Windows."""
    if apri is None:
        apri = getattr(os, "startfile", None) or webbrowser.open  # pragma: no cover
    apri(url)
