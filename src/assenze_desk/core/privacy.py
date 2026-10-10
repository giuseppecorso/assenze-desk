"""Mascheramento dei dati personali nei testi che finiscono in log e storico.

Un codice fiscale diventa "FNT************Y": abbastanza per riconoscere la stessa
persona in due righe di log, non abbastanza per identificarla. Si maschera ogni
sequenza con il formato del CF, anche se il carattere di controllo è sbagliato.
"""

import re

_CIFRA = "[0-9LMNPQRSTUVlmnpqrstuv]"
_CF = re.compile(
    rf"(?<![A-Za-z0-9])([A-Za-z]{{3}})[A-Za-z]{{3}}{_CIFRA}{{2}}[A-Za-z]{_CIFRA}{{2}}"
    rf"[A-Za-z]{_CIFRA}{{3}}([A-Za-z])(?![A-Za-z0-9])"
)


def maschera_cf(testo: str) -> str:
    return _CF.sub(lambda cf: f"{cf[1]}{'*' * 12}{cf[2]}", testo)
