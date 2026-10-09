# Registro delle decisioni

Ogni decisione: cosa si è deciso, perché, alternative scartate.
Le decisioni D1-D6 sono quelle di partenza (vedi `docs/BRIEF.md`) e si cambiano
solo su richiesta dell'utente.

| N. | Data | Decisione | Perché | Alternative scartate |
|---|---|---|---|---|
| D1 | prima del progetto | Si estrae e si testa prima il core | Le regole di business stanno lì | Partire dall'interfaccia |
| D2 | prima del progetto | Le mail restano sempre bozze | L'utente controlla sempre prima dell'invio | Invio automatico |
| D3 | prima del progetto | Fuori progetto: gestionale interno, report interni, macro VBA | Sono specifici dell'azienda; i codici diventano impostazioni con esempi finti | Portarli con dati anonimizzati |
| D4 | prima del progetto | Estrazione a regole, non con un modello AI esterno | Testi con dati personali e sanitari; regole testabili e ripetibili | API di un LLM |
| D5 | prima del progetto | Interfaccia PySide6 con design system QSS proprio | Licenza LGPL, nessuna libreria grafica vincolante | Librerie di temi esterne |
| D6 | prima del progetto | pyproject.toml, .venv, ruff, pytest, pytest-cov, pytest-qt; licenza MIT | Strumenti standard e diffusi | requirements.txt sparsi |
| D7 | 2026-10-09 | Python 3.14 (`requires-python >=3.14`) | Supportato da PySide6 dalla 6.10.1 (nov 2025) e da pywin32 312; supporto fino a ottobre 2030 | 3.15: uscita il 9/10/2026, PySide6 la supporta solo dalla 6.12.0 dell'8/10/2026. 3.13: un anno di supporto in meno |
| D8 | 2026-10-09 | Pacchetto con setuptools e layout `src/`; versione scritta solo in `pyproject.toml`; classificatore `Private :: Do Not Upload` | I test usano il pacchetto installato, non i file sparsi; una sola fonte per la versione; impossibile pubblicarlo per errore su PyPI | Layout piatto; versione ripetuta in più file |
| D9 | 2026-10-09 | Le librerie dell'app entrano nella fase che le usa; dev: pytest, pytest-cov, ruff (versione fissa 0.16.10), pre-commit. pytest-qt arriva con PySide6 in fase 4 | Senza una libreria Qt installata pytest-qt fa fallire tutti i test; ruff fisso evita differenze tra PC, pre-commit e CI | Installare tutto subito |
| D10 | 2026-10-09 | `.gitignore` orientato alla privacy: esclude per estensione i dati veri (Excel, CSV, PDF, mail, database, log), la denylist e i file della v6.20. Eventuali eccezioni solo esplicite | Prima difesa contro i commit di dati reali. I file finti per i test si generano durante i test | Escludere solo cartelle specifiche |
| D11 | 2026-10-09 | Fine riga LF per tutti i file di testo (`.gitattributes`) | Stessi file su Windows e nella CI Linux, niente avvisi di conversione | Lasciare la conversione automatica di Git |
| D12 | 2026-10-09 | Commit firmati con l'email noreply di GitHub (impostata solo nel repo); su GitHub attivo il blocco dei push che espongono l'email | L'email personale non finisce nella cronologia pubblica | Email personale |
| D13 | 2026-10-09 | Denylist locale con tre tipi di riga: parola (maiuscole indifferenti, parola intera), `esatto:` (maiuscole esatte, per le sigle), `re:` (regex). Nome e cognome dell'autore non bloccati; numeri dei report bloccati solo in contesto | Blocca i residui senza falsi allarmi su testo normale ("in corso", "127.0.0.1"); l'autore deve comparire in LICENSE e README | Ricerca semplice per sottostringa (troppi falsi allarmi) |
| D14 | 2026-10-09 | Il controllo privacy, oltre alla denylist, avrà regole fisse: email fuori da domini di esempio, percorsi `C:\Users\<nome>`, cartelle "OneDrive - <organizzazione>", estensioni vietate, la denylist stessa; controllo anche del messaggio di commit; output con termini mascherati (da implementare al passo c) | La denylist non può prevedere tutto; un output mascherato non diffonde i termini nei log | Solo denylist |
| D15 | 2026-10-09 | Dalla fine della sessione 1 si lavora con Claude Code sul PC dell'utente (estensione VS Code) | Il progetto è legato a Windows (Outlook, OCR, PySide6) e il controllo privacy usa la denylist locale | Sessione cloud con GitHub collegato: comandi più rapidi ma test solo su Linux e commit senza controllo privacy |
| D16 | 2026-10-09 | `CLAUDE.md` versionato nel repo con le regole di lavoro | Claude Code lo legge a ogni sessione; documenta in modo trasparente come è stata usata l'AI | Istruzioni ripetute a ogni sessione |
| D17 | 2026-10-09 | Generatore di dati finti dentro il pacchetto (`src/assenze_desk/demo/`); la cartella `demo/` in radice tiene solo script di comodo | La modalità demo funziona anche con l'app installata o con l'eseguibile | Generatore solo in `demo/` in radice, fuori dal pacchetto |
| D18 | 2026-10-09 | La regola di architettura del core è un test (`tests/test_architettura.py`): analizza il sorgente con `ast` e cerca import vietati e lettura o scrittura di file | Una regola scritta solo nei documenti si rompe senza che nessuno se ne accorga; il test la fa rispettare a ogni esecuzione e in CI | Affidarsi alla revisione del codice |
