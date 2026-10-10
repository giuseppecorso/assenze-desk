"""Template delle mail: segnaposti {NOME_IN_MAIUSCOLO} sostituiti con i dati.

- In un solo passaggio: un dato che contiene il testo di un segnaposto ("vedi {CF}")
  resta com'è, non viene sostituito di nuovo.
- In HTML i dati sono sempre testo: escape di <, >, &, virgolette; gli a capo
  diventano <br>. Il template, scritto dall'utente, resta com'è. In testo semplice
  (oggetto, bozze mailto) nessun escape.
- Un segnaposto senza valore resta visibile nella bozza ed è elencato tra i
  mancanti: meglio un "{NOME}" che salta all'occhio di un "Gentile ," inviato
  senza accorgersene.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from html import escape, unescape

_SEGNAPOSTO = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


@dataclass(frozen=True)
class TemplateCompilato:
    testo: str
    mancanti: tuple[str, ...]  # segnaposti senza valore, in ordine di comparsa


def segnaposti(template: str) -> list[str]:
    """Nomi dei segnaposti del template, in ordine e senza doppioni."""
    return list(dict.fromkeys(_SEGNAPOSTO.findall(template)))


def compila(
    template: str, valori: Mapping[str, str | None], html: bool = False
) -> TemplateCompilato:
    mancanti: list[str] = []

    def sostituisci(segnaposto: re.Match[str]) -> str:
        nome = segnaposto[1]
        valore = valori.get(nome)
        if not valore:
            if nome not in mancanti:
                mancanti.append(nome)
            return segnaposto[0]
        return _in_html(valore) if html else valore

    testo = _SEGNAPOSTO.sub(sostituisci, template)
    return TemplateCompilato(testo, tuple(mancanti))


_TAG = re.compile(r"<[a-zA-Z/!][^>]*>")


def compila_per_outlook(template: str, valori: Mapping[str, str | None]) -> TemplateCompilato:
    """Corpo HTML per Outlook. Un template in testo semplice viene protetto e i suoi
    a capo diventano <br>; un template già in HTML resta com'è."""
    if not _TAG.search(template):
        righe = template.replace("\r\n", "\n").split("\n")
        template = "<br>\n".join(escape(riga, quote=False) for riga in righe)
    return compila(template, valori, html=True)


def html_in_testo(html: str) -> str:
    """Testo semplice da un corpo HTML (per le bozze mailto, che non accettano HTML)."""
    testo = re.sub(r"(?is)<(style|script)\b.*?</\1\s*>", "", html)
    testo = re.sub(r"(?i)<br\s*/?>", "\n", testo)
    testo = re.sub(r"(?i)</p\s*>", "\n\n", testo)
    testo = unescape(_TAG.sub("", testo))
    testo = "\n".join(riga.strip() for riga in testo.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", testo).strip()


def _in_html(valore: str) -> str:
    righe = valore.replace("\r\n", "\n").split("\n")
    return "<br>".join(escape(riga, quote=True) for riga in righe)
