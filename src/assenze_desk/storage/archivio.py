"""Archivio SQLite: pratiche di malattia, righe dei giustificativi, storico delle
azioni, indirizzi email ricordati e correzioni dell'anagrafica.

Prende il posto dei due file Excel della v6.20, che venivano riaperti e
risalvati per intero a ogni modifica: qui ogni modifica tocca solo la riga
interessata. Lo stato della pratica non si salva: si calcola con il core
(si salva solo l'eventuale stato impostato a mano). L'ora corrente arriva da
`adesso`, così i test sono ripetibili. Lo storico non contiene mai il CF in chiaro.
"""

import sqlite3
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime
from pathlib import Path
from typing import Any, Self

from assenze_desk.core.episodio import Certificato
from assenze_desk.core.privacy import maschera_cf
from assenze_desk.core.stato import SOGLIA_UFFICIO, Stato, calcola_stato

VERSIONE_SCHEMA = 2  # 2: email ricordate e correzioni dell'anagrafica

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pratiche (
    protocollo TEXT PRIMARY KEY,
    cf TEXT NOT NULL DEFAULT '',
    dipendente TEXT NOT NULL DEFAULT '',
    joborder TEXT NOT NULL DEFAULT '',
    cliente TEXT NOT NULL DEFAULT '',
    inizio TEXT,
    fine TEXT,
    data_presentazione TEXT,
    giorni_episodio INTEGER,
    mail_lavoratore INTEGER NOT NULL DEFAULT 0,
    mail_ufficio INTEGER NOT NULL DEFAULT 0,
    stato_manuale TEXT,
    tempo_gestione_sec REAL,
    note TEXT NOT NULL DEFAULT '',
    creata_il TEXT NOT NULL,
    aggiornata_il TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS pratiche_cf ON pratiche (cf);

CREATE TABLE IF NOT EXISTS righe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cf TEXT NOT NULL,
    dipendente TEXT NOT NULL DEFAULT '',
    joborder TEXT NOT NULL DEFAULT '',
    cliente TEXT NOT NULL DEFAULT '',
    giorno TEXT NOT NULL,
    tipo TEXT NOT NULL,
    codice TEXT NOT NULL,
    minuti INTEGER,
    esportata INTEGER NOT NULL DEFAULT 0,
    creata_il TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS storico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quando TEXT NOT NULL,
    azione TEXT NOT NULL,
    protocollo TEXT NOT NULL DEFAULT '',
    dettaglio TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS email_note (
    email TEXT PRIMARY KEY,
    cf TEXT NOT NULL,
    quando TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS correzioni_anagrafica (
    cf TEXT NOT NULL,
    joborder TEXT NOT NULL,
    campo TEXT NOT NULL,
    valore TEXT,
    PRIMARY KEY (cf, joborder, campo)
);
"""

_CAMPI_DATA = {"inizio_joborder", "fine_joborder"}


@dataclass(frozen=True)
class Pratica:
    protocollo: str
    cf: str = ""
    dipendente: str = ""
    joborder: str = ""
    cliente: str = ""
    inizio: date | None = None
    fine: date | None = None
    data_presentazione: date | None = None
    giorni_episodio: int | None = None
    mail_lavoratore: bool = False
    mail_ufficio: bool = False
    stato_manuale: Stato | None = None
    tempo_gestione_sec: float | None = None
    note: str = ""
    creata_il: datetime | None = None  # impostati dall'archivio
    aggiornata_il: datetime | None = None

    @property
    def stato(self) -> Stato:
        return self.stato_per(SOGLIA_UFFICIO)

    def stato_per(self, soglia_ufficio: int) -> Stato:
        """Lo stato con la soglia della mail all'ufficio scelta nelle impostazioni."""
        return calcola_stato(
            protocollo=self.protocollo,
            cf=self.cf,
            inizio=self.inizio,
            fine=self.fine,
            mail_lavoratore=self.mail_lavoratore,
            mail_ufficio=self.mail_ufficio,
            giorni_episodio=self.giorni_episodio,
            stato_manuale=self.stato_manuale,
            soglia_ufficio=soglia_ufficio,
        )


@dataclass(frozen=True)
class RigaSalvata:
    cf: str
    dipendente: str
    joborder: str
    cliente: str
    giorno: date
    tipo: str
    codice: str
    minuti: int | None
    esportata: bool = False
    id: int | None = None
    creata_il: datetime | None = None


@dataclass(frozen=True)
class Azione:
    quando: datetime
    azione: str
    protocollo: str
    dettaglio: str


_CAMPI_MODIFICABILI = {f.name for f in fields(Pratica)} - {
    "protocollo",
    "creata_il",
    "aggiornata_il",
}
_CAMPI_RIGA_MODIFICABILI = {"giorno", "tipo", "codice", "minuti"}


class Archivio:
    def __init__(
        self,
        percorso: Path | str,
        adesso: Callable[[], datetime] = datetime.now,
        soglia_ufficio: int = SOGLIA_UFFICIO,
    ) -> None:
        if str(percorso) != ":memory:":
            Path(percorso).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(percorso))
        self._db.row_factory = sqlite3.Row
        self._adesso = adesso
        self.soglia_ufficio = soglia_ufficio
        with self._db:
            self._db.executescript(_SCHEMA)
            self._db.execute(f"PRAGMA user_version = {VERSIONE_SCHEMA}")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_errore: object) -> None:
        self.chiudi()

    def chiudi(self) -> None:
        self._db.close()

    @property
    def modifiche_totali(self) -> int:
        """Righe toccate dall'apertura: serve a verificare che le modifiche siano mirate."""
        return self._db.total_changes

    # --- Pratiche di malattia ---

    def salva_pratica(self, pratica: Pratica) -> None:
        """Inserisce la pratica o, se il protocollo esiste già, ne aggiorna i dati."""
        if not pratica.protocollo.strip():
            raise ValueError("serve il protocollo per salvare una pratica")
        valori = _in_colonne(pratica)
        adesso = _testo(self._adesso())
        colonne = [c for c in valori if c not in {"creata_il", "aggiornata_il"}]
        with self._db:
            self._db.execute(
                f"INSERT INTO pratiche ({', '.join(colonne)}, creata_il, aggiornata_il) "
                f"VALUES ({', '.join('?' for _ in colonne)}, ?, ?) "
                "ON CONFLICT (protocollo) DO UPDATE SET "
                + ", ".join(f"{c} = excluded.{c}" for c in colonne if c != "protocollo")
                + ", aggiornata_il = excluded.aggiornata_il",
                [valori[c] for c in colonne] + [adesso, adesso],
            )

    def aggiorna(self, protocollo: str, **campi: Any) -> None:
        sconosciuti = set(campi) - _CAMPI_MODIFICABILI
        if sconosciuti:
            raise ValueError(f"campi non modificabili: {sorted(sconosciuti)}")
        valori = {campo: _in_colonna(campo, valore) for campo, valore in campi.items()}
        valori["aggiornata_il"] = _testo(self._adesso())
        with self._db:
            cursore = self._db.execute(
                f"UPDATE pratiche SET {', '.join(f'{c} = ?' for c in valori)} WHERE protocollo = ?",
                [*valori.values(), protocollo],
            )
        if cursore.rowcount == 0:
            raise KeyError(f"pratica {protocollo} non trovata")

    def elimina_pratiche(self, protocolli: Sequence[str]) -> None:
        with self._db:
            self._db.executemany(
                "DELETE FROM pratiche WHERE protocollo = ?", [(p,) for p in protocolli]
            )

    def pratica(self, protocollo: str) -> Pratica | None:
        riga = self._db.execute(
            "SELECT * FROM pratiche WHERE protocollo = ?", (protocollo,)
        ).fetchone()
        return _pratica(riga) if riga else None

    def pratiche(self, *, cf: str | None = None, stato: Stato | None = None) -> list[Pratica]:
        if cf is None:
            righe = self._db.execute("SELECT * FROM pratiche ORDER BY creata_il, protocollo")
        else:
            righe = self._db.execute(
                "SELECT * FROM pratiche WHERE cf = ? ORDER BY creata_il, protocollo",
                (cf.strip().upper(),),
            )
        pratiche = [_pratica(riga) for riga in righe]
        return [p for p in pratiche if stato is None or p.stato_per(self.soglia_ufficio) is stato]

    def certificati(self, cf: str) -> list[Certificato]:
        """Le pratiche del CF con le date, come certificati per calcolare l'episodio."""
        return sorted(
            (
                Certificato(p.protocollo, p.cf, p.inizio, p.fine)
                for p in self.pratiche(cf=cf)
                if p.inizio and p.fine and p.inizio <= p.fine
            ),
            key=lambda c: (c.inizio, c.protocollo),
        )

    # --- Righe dei giustificativi ---

    def aggiungi_righe(self, righe: Iterable[RigaSalvata]) -> list[int]:
        adesso = _testo(self._adesso())
        ids = []
        with self._db:
            for riga in righe:
                cursore = self._db.execute(
                    "INSERT INTO righe (cf, dipendente, joborder, cliente, giorno, tipo, codice, "
                    "minuti, esportata, creata_il) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        riga.cf.strip().upper(),
                        riga.dipendente,
                        riga.joborder,
                        riga.cliente,
                        riga.giorno.isoformat(),
                        riga.tipo,
                        riga.codice,
                        riga.minuti,
                        int(riga.esportata),
                        adesso,
                    ),
                )
                ids.append(int(cursore.lastrowid or 0))
        return ids

    def righe(self, solo_da_esportare: bool = False) -> list[RigaSalvata]:
        filtro = "WHERE esportata = 0" if solo_da_esportare else ""
        return [
            _riga(r) for r in self._db.execute(f"SELECT * FROM righe {filtro} ORDER BY giorno, id")
        ]

    def modifica_riga(self, id_riga: int, **campi: Any) -> None:
        sconosciuti = set(campi) - _CAMPI_RIGA_MODIFICABILI
        if sconosciuti:
            raise ValueError(f"campi non modificabili: {sorted(sconosciuti)}")
        valori = {c: v.isoformat() if isinstance(v, date) else v for c, v in campi.items()}
        with self._db:
            self._db.execute(
                f"UPDATE righe SET {', '.join(f'{c} = ?' for c in valori)} WHERE id = ?",
                [*valori.values(), id_riga],
            )

    def segna_esportate(self, ids: Sequence[int]) -> None:
        with self._db:
            self._db.executemany("UPDATE righe SET esportata = 1 WHERE id = ?", [(i,) for i in ids])

    def elimina_righe(self, ids: Sequence[int]) -> None:
        with self._db:
            self._db.executemany("DELETE FROM righe WHERE id = ?", [(i,) for i in ids])

    # --- Indirizzi ricordati: chi scrive da una mail diversa da quella in anagrafica ---

    def email_note(self) -> dict[str, str]:
        righe = self._db.execute("SELECT email, cf FROM email_note")
        return {r["email"]: r["cf"] for r in righe}

    def ricorda_email(self, email: str, cf: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO email_note (email, cf, quando) VALUES (?, ?, ?)",
                (email.strip().lower(), cf.strip().upper(), _testo(self._adesso())),
            )

    def email_di(self, cf: str) -> list[str]:
        righe = self._db.execute(
            "SELECT email FROM email_note WHERE cf = ? ORDER BY email", (cf.strip().upper(),)
        )
        return [r["email"] for r in righe]

    def imposta_email_di(self, cf: str, indirizzi: Iterable[str]) -> None:
        """Sostituisce gli indirizzi ricordati per quel CF."""
        cf = cf.strip().upper()
        puliti = dict.fromkeys(i.strip().lower() for i in indirizzi if i.strip())
        with self._db:
            self._db.execute("DELETE FROM email_note WHERE cf = ?", (cf,))
            self._db.executemany(
                "INSERT OR REPLACE INTO email_note (email, cf, quando) VALUES (?, ?, ?)",
                [(email, cf, _testo(self._adesso())) for email in puliti],
            )

    # --- Correzioni dell'anagrafica (l'Excel non si tocca) ---

    def correzioni(self) -> dict[tuple[str, str], dict[str, Any]]:
        risultato: dict[tuple[str, str], dict[str, Any]] = {}
        for r in self._db.execute("SELECT * FROM correzioni_anagrafica"):
            valore = r["valore"]
            if r["campo"] in _CAMPI_DATA and valore is not None:
                valore = date.fromisoformat(valore)
            risultato.setdefault((r["cf"], r["joborder"]), {})[r["campo"]] = valore
        return risultato

    def salva_correzione(self, cf: str, joborder: str, campi: dict[str, Any]) -> None:
        """Sostituisce la correzione di quella riga; senza campi la toglie."""
        cf, joborder = cf.strip().upper(), joborder.strip()
        with self._db:
            self._db.execute(
                "DELETE FROM correzioni_anagrafica WHERE cf = ? AND joborder = ?", (cf, joborder)
            )
            self._db.executemany(
                "INSERT INTO correzioni_anagrafica (cf, joborder, campo, valore) "
                "VALUES (?, ?, ?, ?)",
                [
                    (cf, joborder, campo, None if valore is None else _in_colonna(campo, valore))
                    for campo, valore in campi.items()
                ],
            )

    def togli_correzione(self, cf: str, joborder: str) -> None:
        self.salva_correzione(cf, joborder, {})

    # --- Storico delle azioni ---

    def registra(self, azione: str, protocollo: str = "", dettaglio: str = "") -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO storico (quando, azione, protocollo, dettaglio) VALUES (?, ?, ?, ?)",
                (_testo(self._adesso()), azione, protocollo, maschera_cf(dettaglio)),
            )

    def storico(self, limite: int = 200) -> list[Azione]:
        righe = self._db.execute(
            "SELECT * FROM storico ORDER BY quando DESC, id DESC LIMIT ?", (limite,)
        )
        return [
            Azione(
                datetime.fromisoformat(r["quando"]), r["azione"], r["protocollo"], r["dettaglio"]
            )
            for r in righe
        ]


# --- Conversioni tra oggetti Python e colonne SQLite ---


def _testo(momento: datetime) -> str:
    return momento.isoformat(timespec="seconds")


def _in_colonna(campo: str, valore: Any) -> Any:
    if valore is None:
        return None
    if campo == "cf":
        return str(valore).strip().upper()
    if isinstance(valore, Stato):
        return valore.value
    if isinstance(valore, bool):
        return int(valore)
    if isinstance(valore, datetime):
        return _testo(valore)
    if isinstance(valore, date):
        return valore.isoformat()
    return valore


def _in_colonne(pratica: Pratica) -> dict[str, Any]:
    return {f.name: _in_colonna(f.name, getattr(pratica, f.name)) for f in fields(Pratica)}


def _data(valore: str | None) -> date | None:
    return date.fromisoformat(valore) if valore else None


def _pratica(riga: sqlite3.Row) -> Pratica:
    return Pratica(
        protocollo=riga["protocollo"],
        cf=riga["cf"],
        dipendente=riga["dipendente"],
        joborder=riga["joborder"],
        cliente=riga["cliente"],
        inizio=_data(riga["inizio"]),
        fine=_data(riga["fine"]),
        data_presentazione=_data(riga["data_presentazione"]),
        giorni_episodio=riga["giorni_episodio"],
        mail_lavoratore=bool(riga["mail_lavoratore"]),
        mail_ufficio=bool(riga["mail_ufficio"]),
        stato_manuale=Stato(riga["stato_manuale"]) if riga["stato_manuale"] else None,
        tempo_gestione_sec=riga["tempo_gestione_sec"],
        note=riga["note"],
        creata_il=datetime.fromisoformat(riga["creata_il"]),
        aggiornata_il=datetime.fromisoformat(riga["aggiornata_il"]),
    )


def _riga(riga: sqlite3.Row) -> RigaSalvata:
    return RigaSalvata(
        cf=riga["cf"],
        dipendente=riga["dipendente"],
        joborder=riga["joborder"],
        cliente=riga["cliente"],
        giorno=date.fromisoformat(riga["giorno"]),
        tipo=riga["tipo"],
        codice=riga["codice"],
        minuti=riga["minuti"],
        esportata=bool(riga["esportata"]),
        id=riga["id"],
        creata_il=datetime.fromisoformat(riga["creata_il"]),
    )
