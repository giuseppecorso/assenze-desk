# Sicurezza e protezione dei dati

Assenze Desk tratta dati personali di lavoratori, compresi i periodi di
malattia. Questo documento dice dove stanno i dati, cosa l'app non fa mai e
come si evita di perderli. Ogni punto è verificato sul codice.

## In breve

- **I dati restano sul PC.** L'app non si collega a nessun server: nel codice
  non c'è nessuna connessione di rete, niente cloud, niente statistiche
  d'uso inviate, nessun servizio di intelligenza artificiale esterno.
- **Le mail non partono mai da sole.** L'app prepara bozze; le invia
  l'operatore dopo averle controllate.
- **L'anagrafica Excel non viene modificata.** Si legge soltanto; le correzioni
  fatte nell'app restano nell'archivio dell'app.
- **Copie di sicurezza automatiche** dell'archivio, una al giorno, con
  ripristino se il file si danneggia.

## Dove stanno i dati

| Dato | Dove | Note |
|---|---|---|
| Archivio (pratiche, righe, storico, correzioni, indirizzi ricordati) | `%LOCALAPPDATA%\AssenzeDesk\archivio.db` | Database SQLite, un solo file |
| Impostazioni | `%LOCALAPPDATA%\AssenzeDesk\impostazioni.json` | Percorsi, destinatari, template |
| Log | `%LOCALAPPDATA%\AssenzeDesk\log` | Codice fiscale sempre mascherato (`R************X`), file da 1 MB a rotazione, al massimo 6 |
| Copie di sicurezza | `%LOCALAPPDATA%\AssenzeDesk\backup` o la cartella scelta | Ultime 14 |
| Certificati PDF | Cartella scelta nelle impostazioni | Nome `<protocollo>.pdf` |
| Anagrafica | Il file Excel dell'utente | Solo lettura |

Le cartelle si cambiano in Impostazioni > Generali. La modalità demo lavora in
una cartella temporanea con soli dati finti e la cancella alla chiusura.

## Cosa l'app non fa

| L'app non… | Come si verifica |
|---|---|
| si collega a internet | Nessuna libreria di rete nel codice; l'unico indirizzo web è il portale INPS, aperto nel browser dall'utente con un clic |
| invia mail | Con Outlook la bozza si apre e basta (`Display`); con il programma di posta predefinito si apre una bozza `mailto:` |
| usa servizi di intelligenza artificiale | L'estrazione dei dati è fatta con regole scritte nel codice e testate |
| modifica l'anagrafica o i file della versione precedente | Si leggono soltanto (anche l'import della versione precedente) |
| scrive il codice fiscale in chiaro nei log o nello storico | Mascheramento sul testo finale di ogni riga, traceback compresi ([test_registro.py](../tests/test_registro.py)) |
| esegue contenuti delle mail | I dati inseriti nelle bozze HTML sono sempre trattati come testo ([test_template.py](../tests/test_template.py)) |

## Protezione dalla perdita di dati

- **Modifiche atomiche.** Ogni salvataggio nell'archivio è una transazione
  SQLite: o va a buon fine tutto, o niente. Si modifica solo la riga
  interessata, mai l'intero file.
- **Copia di sicurezza giornaliera.** All'apertura dell'app, una volta al
  giorno, l'archivio viene copiato con l'API di backup di SQLite (copia
  coerente anche ad archivio aperto). Si tengono le ultime 14 copie.
- **Copia fuori dal PC.** Per proteggersi anche da un guasto del disco basta
  scegliere come cartella delle copie una cartella sincronizzata (per esempio
  OneDrive) o di rete. L'archivio invece resta nella cartella locale: un
  database aperto dentro una cartella sincronizzata si può rovinare.
- **Controllo di integrità.** All'apertura l'archivio viene controllato. Se è
  danneggiato si mette da parte (non si cancella mai) e si riprende l'ultima
  copia integra; un avviso dice la data della copia, così si sa quali pratiche
  ricontrollare.
- **Niente cancellazioni a sorpresa.** Eliminare pratiche chiede conferma e
  resta nello storico; disinstallare l'app non tocca i dati.

Verifica: [test_backup.py](../tests/test_backup.py),
[test_servizi.py](../tests/test_servizi.py), [test_archivio.py](../tests/test_archivio.py).

## Privacy nello sviluppo

- Nel repository ci sono solo dati finti generati (codici fiscali con un luogo
  di nascita inesistente, indirizzi `@example.com`).
- Prima di ogni modifica un controllo automatico blocca dati reali, nomi
  aziendali, percorsi personali ed estensioni di file con dati veri; lo stesso
  controllo gira nella CI. Prima della pubblicazione è stata controllata tutta
  la cronologia.

## Limiti e raccomandazioni

| Limite | Raccomandazione |
|---|---|
| L'archivio e le copie non sono cifrati | Usare un account Windows con password e la cifratura del disco (BitLocker), come per gli altri dati di lavoro |
| Un utente per volta | Non condividere l'archivio tra più persone contemporaneamente |
| Nessuna cancellazione automatica dopo un periodo | Eliminare periodicamente le pratiche non più necessarie, secondo le regole di conservazione dell'organizzazione |
| L'eseguibile non è firmato digitalmente | Windows può mostrare "PC protetto da Windows" al primo avvio; scaricarlo solo dalla pagina Releases del repository |
| Il PDF del certificato contiene dati personali | La cartella dei certificati va protetta come l'archivio |
