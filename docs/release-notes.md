Prima versione di Assenze Desk: gestione di malattie e giustificativi a
partire dalle mail, per Windows.

## Installazione

1. Scarica `AssenzeDesk-…-windows.zip` qui sotto ed estrai tutto lo zip.
2. Nella cartella estratta fai doppio clic su `Installa.cmd`: l'app si copia
   nella cartella dei programmi dell'utente (senza permessi di amministratore)
   e compare l'icona "Assenze Desk" sul Desktop e nel menu Start.
3. Per aggiornare si ripete lo stesso passo; per togliere l'app c'è
   `Disinstalla.cmd`. I dati restano sempre.

## Come provarla senza installare niente

1. Estrai lo zip.
2. Apri il prompt dei comandi nella cartella estratta e scrivi:
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
- Pulsante facoltativo per aprire il portale o il programma aziendale,
  con l'indirizzo scelto nelle impostazioni.
- Le mail restano sempre bozze.

Dettagli, architettura e limiti nel [README](https://github.com/giuseppecorso/assenze-desk#readme).

## Componenti di terze parti

L'eseguibile contiene Python e le librerie elencate in `pyproject.toml`, tra
cui Qt for Python (PySide6, licenza LGPL v3): le sue librerie sono file
separati nella cartella e si possono sostituire.
