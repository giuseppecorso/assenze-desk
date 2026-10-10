"""Stampa un esempio di dati finti (anagrafica e mail), per guardarli a occhio.

Uso: python demo/genera_demo.py [seme]
"""

import sys
from datetime import date

from assenze_desk.demo.generatore import genera_dati


def main() -> None:
    seme = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    dati = genera_dati(date(2026, 10, 7), seme=seme, dipendenti=5, mail_malattia=2, mail_permesso=5)
    for dipendente in dati.anagrafica:
        print(f"{dipendente.cognome} {dipendente.nome} | {dipendente.cliente} | {dipendente.email}")
    for mail in dati.mail_malattia + dati.mail_permesso:
        print("\n" + "-" * 60 + "\n" + mail.testo)


if __name__ == "__main__":
    main()
