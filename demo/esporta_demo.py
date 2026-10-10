"""Crea file Excel di prova con dati finti in demo/output/ (cartella esclusa da git).

- anagrafica_demo.xlsx: anagrafica da importare (fogli Dipendenti, Orari, Capienze)
- giustificativi_demo.xlsx: export delle righe dei giustificativi
- pratiche_demo.xlsx: export dell'archivio delle pratiche

Uso: python demo/esporta_demo.py
"""

from datetime import date
from pathlib import Path

from assenze_desk.core.episodio import Certificato, calcola_episodio
from assenze_desk.core.giustificativi import TIPI_PREDEFINITI, righe_giustificativo
from assenze_desk.core.permessi import leggi_permesso
from assenze_desk.demo.generatore import genera_dati
from assenze_desk.storage.anagrafica import scrivi_anagrafica
from assenze_desk.storage.archivio import Pratica, RigaSalvata
from assenze_desk.storage.export import esporta_giustificativi, esporta_pratiche

CARTELLA = Path(__file__).resolve().parent / "output"


def main() -> None:
    dati = genera_dati(date(2026, 10, 7), seme=1)
    per_cf = {d.cf: d for d in dati.anagrafica}
    capienze = {d.joborder: {"Ferie": 9600, "ROL": 2400} for d in dati.anagrafica[:5]}
    scrivi_anagrafica(CARTELLA / "anagrafica_demo.xlsx", dati.anagrafica, dati.orari, capienze)

    righe = []
    for mail in dati.mail_permesso:
        permesso = leggi_permesso(mail.testo, mail.ricevuta.date())
        dipendente = per_cf[mail.atteso["cf"]]
        tipo = permesso.tipo or TIPI_PREDEFINITI[1]
        orario = dati.orari.get(dipendente.cliente)
        for riga in righe_giustificativo(tipo, permesso.giorni, permesso.minuti, orario):
            righe.append(
                RigaSalvata(
                    dipendente.cf,
                    f"{dipendente.cognome} {dipendente.nome}",
                    dipendente.joborder,
                    dipendente.cliente,
                    riga.giorno,
                    riga.tipo,
                    riga.codice,
                    riga.minuti,
                )
            )
    esporta_giustificativi(righe, CARTELLA / "giustificativi_demo.xlsx")

    pratiche = []
    for mail in dati.mail_malattia:
        dipendente = per_cf[mail.atteso["cf"]]
        certificato = Certificato(
            mail.atteso["protocollo"], dipendente.cf, mail.atteso["inizio"], mail.atteso["fine"]
        )
        pratiche.append(
            Pratica(
                protocollo=certificato.protocollo,
                cf=dipendente.cf,
                dipendente=f"{dipendente.cognome} {dipendente.nome}",
                joborder=dipendente.joborder,
                cliente=dipendente.cliente,
                inizio=certificato.inizio,
                fine=certificato.fine,
                giorni_episodio=calcola_episodio(certificato, []).giorni,
                mail_lavoratore=True,
            )
        )
    esporta_pratiche(pratiche, CARTELLA / "pratiche_demo.xlsx")
    print(f"File creati in {CARTELLA}")


if __name__ == "__main__":
    main()
