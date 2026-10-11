Prima versione di Assenze Desk: gestione di malattie e giustificativi a
partire dalle mail, per Windows.

## Come provarla senza installare niente

1. Scarica `AssenzeDesk-…-windows.zip` qui sotto ed estrai la cartella.
2. Apri il prompt dei comandi in quella cartella e scrivi:
   `AssenzeDesk.exe --demo`

La modalità demo usa solo dati finti in una cartella temporanea, cancellata
alla chiusura. Senza `--demo` l'app usa i dati in `%LOCALAPPDATA%\AssenzeDesk`.

## Cosa contiene

- Nuova pratica di malattia e giustificativo in un'unica schermata, con
  l'origine di ogni dato e i campi manuali protetti.
- Import da Outlook Classic, incolla, testo selezionato, OCR (con Tesseract
  installato), certificato PDF INPS e assistente per il portale.
- Archivio con filtri, storico ed export in Excel; statistiche; impostazioni
  in un file; tema chiaro e scuro.
- Le mail restano sempre bozze.

Dettagli, architettura e limiti nel [README](https://github.com/giuseppecorso/assenze-desk#readme).

## Componenti di terze parti

L'eseguibile contiene Python e le librerie elencate in `pyproject.toml`, tra
cui Qt for Python (PySide6, licenza LGPL v3): le sue librerie sono file
separati nella cartella e si possono sostituire.
