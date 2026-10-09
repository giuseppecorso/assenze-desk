"""Controllo privacy: blocca i commit che contengono dati reali.

Cerca nei file (nome e contenuto) e nel messaggio di commit:
- i termini della denylist locale `.privacy-denylist.txt`, che non entra mai nel repo;
- regole fisse, valide anche senza denylist: email reali, percorsi personali di
  Windows, cartelle OneDrive aziendali, estensioni di file con dati veri.

L'output mostra solo l'inizio di ciò che trova (`te***`): può finire nei log della CI.

Uso:
    python scripts/check_privacy.py FILE...            file in commit (hook pre-commit)
    python scripts/check_privacy.py --commit-msg FILE  messaggio di commit (hook commit-msg)
    python scripts/check_privacy.py --all              tutti i file tracciati da git
"""

import argparse
import re
import subprocess
import sys
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

DENYLIST = Path(__file__).resolve().parents[1] / ".privacy-denylist.txt"

DENYLIST_MANCANTE = """\
Controllo privacy: manca la denylist ({percorso}).
Senza denylist il controllo non è completo, quindi il commit è bloccato.
Crea il file nella cartella del progetto con un termine vietato per riga:
    parola         maiuscole indifferenti, parola intera
    esatto:SIGLA   maiuscole esatte (per le sigle)
    re:REGEX       espressione regolare Python
Le righe vuote e quelle che iniziano con # sono ignorate.
Il file resta solo sul tuo PC: è escluso da git."""


@dataclass(frozen=True)
class Regola:
    descrizione: str
    pattern: re.Pattern[str]
    # Eccezioni: corrispondenze che la regola trova ma che sono ammesse
    ammesso: Callable[[str], bool] | None = None

    def cerca(self, testo: str) -> Iterator[re.Match[str]]:
        for corrispondenza in self.pattern.finditer(testo):
            trovato = corrispondenza.group()
            if trovato and not (self.ammesso and self.ammesso(trovato)):
                yield corrispondenza


@dataclass(frozen=True)
class Segnalazione:
    dove: str
    descrizione: str
    trovato: str = ""

    def __str__(self) -> str:
        dettaglio = f" ({maschera(self.trovato)})" if self.trovato else ""
        return f"{self.dove}: {self.descrizione}{dettaglio}"


def maschera(testo: str) -> str:
    """Mostra solo l'inizio: abbastanza per ritrovarlo, non per diffonderlo."""
    return testo[: 2 if len(testo) >= 6 else 1] + "***"


# --- Denylist ---


def regole_denylist(testo: str) -> list[Regola]:
    regole = []
    for numero, riga in enumerate(testo.splitlines(), start=1):
        termine = riga.strip()
        if not termine or termine.startswith("#"):
            continue
        if termine.startswith("re:"):
            try:
                pattern = re.compile(termine.removeprefix("re:"))
            except re.error as errore:
                # Il messaggio non riporta la regex: potrebbe contenere il termine
                raise ValueError(f"riga {numero}: regex non valida ({errore.msg})") from None
        elif termine.startswith("esatto:"):
            pattern = _pattern_parola(termine.removeprefix("esatto:").strip(), numero, 0)
        else:
            pattern = _pattern_parola(termine, numero, re.IGNORECASE)
        regole.append(Regola(f"termine vietato alla riga {numero} della denylist", pattern))
    return regole


def _pattern_parola(termine: str, numero: int, flag: int) -> re.Pattern[str]:
    """Termine a parola intera: underscore e punteggiatura contano come separatori."""
    if not termine:
        raise ValueError(f"riga {numero}: termine vuoto")
    prima = r"(?<![^\W_])" if termine[0].isalnum() else ""
    dopo = r"(?![^\W_])" if termine[-1].isalnum() else ""
    parti = r"\s+".join(re.escape(parte) for parte in termine.split())
    return re.compile(prima + parti + dopo, flag)


# --- Regole fisse ---

DOMINI_EMAIL_AMMESSI = ("example.com", "example.org", "example.net", "users.noreply.github.com")
TLD_EMAIL_AMMESSI = ("test", "example", "invalid", "localhost")
EMAIL_AMMESSE = ("noreply@anthropic.com",)  # trailer Co-Authored-By dei commit


def _email_ammessa(email: str) -> bool:
    email = email.lower()
    dominio = email.rpartition("@")[2]
    return (
        email in EMAIL_AMMESSE
        or dominio.rpartition(".")[2] in TLD_EMAIL_AMMESSI
        or any(dominio == d or dominio.endswith("." + d) for d in DOMINI_EMAIL_AMMESSI)
    )


REGOLE_FISSE = [
    Regola(
        "email non ammessa (usa un dominio example.com)",
        re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b"),
        _email_ammessa,
    ),
    Regola(
        "percorso personale (usa un segnaposto come <utente>)",
        # Segnaposto ammessi dopo Users: <utente>, %USERNAME%, {utente}, $env:USERNAME
        re.compile(r"\b[A-Za-z]:[\\/]+Users[\\/]+(?![<%{$])[^\\/\s\"'<>|]+", re.IGNORECASE),
    ),
    Regola(
        "cartella OneDrive aziendale (usa <organizzazione>)",
        re.compile(r"OneDrive\s*-\s*(?!<)[^\s\\/\"']+", re.IGNORECASE),
    ),
]

ESTENSIONI_VIETATE = {".xlsm", ".msg", ".eml", ".pst", ".ost"}


# --- Controlli ---


def controlla_testo(testo: str, dove: str, regole: list[Regola]) -> list[Segnalazione]:
    trovate = []
    for regola in regole:
        for corrispondenza in regola.cerca(testo):
            riga = testo.count("\n", 0, corrispondenza.start()) + 1
            trovate.append(
                Segnalazione(f"{dove}:{riga}", regola.descrizione, corrispondenza.group())
            )
    return trovate


def controlla_file(percorso: str, regole: list[Regola]) -> list[Segnalazione]:
    # Il percorso stampato è mascherato anch'esso, se contiene un termine vietato
    mostrato = percorso
    for regola in regole:
        mostrato = regola.pattern.sub(lambda c, r=regola: _maschera_se_vietato(c, r), mostrato)

    trovate = [
        Segnalazione(f"{mostrato} (nome del file)", s.descrizione, s.trovato)
        for s in controlla_testo(percorso, "", regole)
    ]
    if Path(percorso).suffix.lower() in ESTENSIONI_VIETATE:
        trovate.append(Segnalazione(mostrato, "estensione vietata: file con dati veri"))
    if Path(percorso).name.lower().startswith(".privacy-denylist"):
        trovate.append(Segnalazione(mostrato, "è la denylist: non deve mai entrare nel repo"))

    try:
        for interno, testo in _contenuti(Path(percorso)):
            trovate += controlla_testo(testo, mostrato + interno, regole)
    except zipfile.BadZipFile, RuntimeError, NotImplementedError:
        # Archivio protetto o rovinato: non si può controllare, quindi si blocca
        trovate.append(Segnalazione(mostrato, "archivio non leggibile: controllalo a mano"))
    return trovate


def _maschera_se_vietato(corrispondenza: re.Match[str], regola: Regola) -> str:
    trovato = corrispondenza.group()
    if not trovato or (regola.ammesso and regola.ammesso(trovato)):
        return trovato
    return maschera(trovato)


def _contenuti(percorso: Path) -> Iterator[tuple[str, str]]:
    """Coppie (parte interna, testo). I file Office sono zip: si controlla ogni parte."""
    if zipfile.is_zipfile(percorso):
        with zipfile.ZipFile(percorso) as archivio:
            for interno in archivio.namelist():
                yield "/" + interno, _decodifica(archivio.read(interno))
    else:
        yield "", _decodifica(percorso.read_bytes())


def _decodifica(dati: bytes) -> str:
    try:
        return dati.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dati.decode("latin-1")  # binari: ogni byte diventa un carattere


def _file_tracciati() -> list[str]:
    uscita = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    return [nome for nome in uscita.decode("utf-8").split("\0") if nome]


# --- Riga di comando ---


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blocca i commit che contengono dati reali.")
    modalita = parser.add_mutually_exclusive_group()
    modalita.add_argument("--commit-msg", metavar="FILE", help="controlla il messaggio di commit")
    modalita.add_argument("--all", action="store_true", help="controlla tutti i file tracciati")
    parser.add_argument("--denylist", type=Path, default=DENYLIST, help=argparse.SUPPRESS)
    parser.add_argument("file", nargs="*", help="file da controllare")
    args = parser.parse_args(argv)

    if not args.denylist.is_file():
        print(DENYLIST_MANCANTE.format(percorso=args.denylist.name), file=sys.stderr)
        return 1
    try:
        regole = regole_denylist(args.denylist.read_text(encoding="utf-8-sig"))
    except ValueError as errore:
        print(f"Controllo privacy: denylist non valida, {errore}", file=sys.stderr)
        return 1
    regole += REGOLE_FISSE

    if args.commit_msg:
        testo = Path(args.commit_msg).read_text(encoding="utf-8-sig")
        trovate = controlla_testo(testo, "messaggio di commit", regole)
    else:
        file = _file_tracciati() if args.all else args.file
        trovate = [s for f in file if Path(f).is_file() for s in controlla_file(f, regole)]

    for segnalazione in trovate:
        print(segnalazione)
    if trovate:
        quanti = "1 problema" if len(trovate) == 1 else f"{len(trovate)} problemi"
        print(
            f"\nControllo privacy: {quanti}. "
            "Correggi quanto indicato e ripeti il commit (mai --no-verify)."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
