"""Codice fiscale: formato, carattere di controllo ed estrazione dal testo.

L'ultimo carattere del CF si calcola dagli altri 15. Se non torna, il CF è stato
scritto o letto male (per esempio dall'OCR) e viene scartato: meglio vuoto che
sbagliato. Sono ammessi i CF omocodici, con alcune cifre sostituite da lettere.
"""

import re
import string

# Lettere che sostituiscono le cifre nei CF omocodici: L=0, M=1, ..., V=9
_OMOCODIA = "LMNPQRSTUV"
_CIFRA = f"[0-9{_OMOCODIA}]"
_MESI = "ABCDEHLMPRST"
_FORMATO = re.compile(rf"[A-Z]{{6}}{_CIFRA}{{2}}[{_MESI}]{_CIFRA}{{2}}[A-Z]{_CIFRA}{{3}}[A-Z]")

_ALFABETO = string.digits + string.ascii_uppercase
# Valori dei caratteri in posizione dispari (1ª, 3ª, ...): tabella ufficiale.
# Le lettere da A a J valgono come le cifre da 0 a 9.
_DISPARI_0_9 = [1, 0, 5, 7, 9, 13, 15, 17, 19, 21]
_DISPARI_K_Z = [2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]
_VALORI_DISPARI = dict(zip(_ALFABETO, [*_DISPARI_0_9, *_DISPARI_0_9, *_DISPARI_K_Z], strict=True))
# Valori in posizione pari (2ª, 4ª, ...): cifre 0-9 e lettere A=0 ... Z=25
_VALORI_PARI = {c: int(c) if c.isdigit() else ord(c) - ord("A") for c in _ALFABETO}

# Candidati: 16 caratteri alfanumerici, con al massimo uno spazio tra uno e l'altro.
# Il lookahead trova anche i candidati sovrapposti; i confini si controllano dopo.
_CANDIDATO = re.compile(r"(?=([A-Za-z0-9](?:[ \N{NO-BREAK SPACE}]?[A-Za-z0-9]){15}))")
_SPAZI = re.compile(r"[ \N{NO-BREAK SPACE}]")


def carattere_di_controllo(primi_15: str) -> str:
    """Carattere di controllo calcolato dai primi 15 caratteri (maiuscoli)."""
    totale = sum(
        _VALORI_DISPARI[c] if posizione % 2 == 0 else _VALORI_PARI[c]
        for posizione, c in enumerate(primi_15)
    )
    return chr(ord("A") + totale % 26)


def cf_valido(cf: str) -> bool:
    cf = cf.upper()
    return bool(_FORMATO.fullmatch(cf)) and carattere_di_controllo(cf[:15]) == cf[15]


def trova_codici_fiscali(testo: str) -> list[str]:
    """Tutti i CF validi nel testo, in maiuscolo e senza spazi, in ordine e senza doppioni."""
    trovati: list[str] = []
    for candidato in _CANDIDATO.finditer(testo):
        inizio, fine = candidato.start(1), candidato.end(1)
        attaccato = (inizio > 0 and testo[inizio - 1].isalnum()) or (
            fine < len(testo) and testo[fine].isalnum()
        )
        cf = _SPAZI.sub("", candidato.group(1)).upper()
        if not attaccato and cf_valido(cf) and cf not in trovati:
            trovati.append(cf)
    return trovati


def estrai_cf(testo: str) -> str | None:
    """Il primo CF valido nel testo, oppure None."""
    trovati = trova_codici_fiscali(testo)
    return trovati[0] if trovati else None
