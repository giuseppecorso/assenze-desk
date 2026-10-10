"""Certificati di malattia PDF finti, per la modalità demo e per i test.

Riportano in alto "FAC-SIMILE CON DATI INVENTATI" e usano le stesse etichette del
certificato vero, così la lettura si prova senza mai usare documenti reali.
Le spunte sono scritte prima della voce ("X Inizio").
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from fpdf import FPDF

from assenze_desk.core.certificato import TIPI, VISITE


@dataclass(frozen=True)
class CertificatoFinto:
    protocollo: str
    cf: str
    cognome: str
    nome: str
    inizio: date
    fine: date
    tipo: str = "Inizio"
    visita: str = "Ambulatoriale"


def righe_certificato(c: CertificatoFinto) -> list[str]:
    def spunte(voci: tuple[str, ...], scelta: str) -> str:
        return " ".join(f"X {voce}" if voce == scelta else voce for voce in voci)

    return [
        "CERTIFICATO DI MALATTIA - FAC-SIMILE CON DATI INVENTATI",
        f"Protocollo univoco del certificato (PUC): {c.protocollo}",
        "DATI DEL LAVORATORE",
        f"Cognome {c.cognome.upper()} Nome {c.nome.upper()} C.F. {c.cf}",
        f"Trattasi di: {spunte(TIPI, c.tipo)}",
        f"Visita: {spunte(VISITE, c.visita)}",
        f"Data visita {c.inizio:%d/%m/%Y}",
        f"Il medico dichiara che il lavoratore è ammalato dal {c.inizio:%d/%m/%Y} "
        f"a tutto il {c.fine:%d/%m/%Y}",
    ]


def scrivi_certificato_finto(certificato: CertificatoFinto, percorso: Path) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for riga in righe_certificato(certificato):
        pdf.cell(0, 8, riga, new_x="LMARGIN", new_y="NEXT")
    percorso = Path(percorso)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(percorso))
    return percorso
