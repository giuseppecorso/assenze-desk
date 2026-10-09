"""Logica pura: le regole di business dell'app.

Conterrà la lettura del testo delle mail (protocollo, codice fiscale, JobOrder,
date, ore), la classificazione dei giustificativi, l'episodio di malattia, lo
stato della pratica, il match del dipendente, i template delle mail e le
statistiche.

Regola: qui non si importano librerie grafiche, di Office, di PDF, di OCR o di
database e non si leggono file. I dati entrano come argomenti e i risultati
escono come valori, così ogni regola si prova con un test che gira ovunque.
Il controllo è in `tests/test_architettura.py`.
"""
