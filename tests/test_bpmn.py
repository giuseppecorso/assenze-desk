"""Schemi BPMN dell'analisi funzionale: file aggiornati e coerenti.

Gli SVG e i file .bpmn in docs/analisi si generano con scripts/genera_bpmn.py;
se qualcuno cambia un processo senza rigenerarli, questo test lo segnala.
"""

import importlib.util
from pathlib import Path
from xml.etree import ElementTree as ET

RADICE = Path(__file__).resolve().parents[1]
B = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"


def _generatore():
    spec = importlib.util.spec_from_file_location(
        "genera_bpmn", RADICE / "scripts" / "genera_bpmn.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_schemi_aggiornati():
    generatore = _generatore()
    for diagramma in generatore.processi():
        for estensione, crea in (("svg", generatore._svg), ("bpmn", generatore._bpmn)):
            file = RADICE / "docs" / "analisi" / f"{diagramma.nome}.{estensione}"
            assert file.read_text(encoding="utf-8") == crea(diagramma), (
                f"{file.name} non aggiornato: python scripts/genera_bpmn.py"
            )


def test_bpmn_coerenti():
    for file in (RADICE / "docs" / "analisi").glob("*.bpmn"):
        processo = ET.parse(file).getroot().find(f"{B}process")
        nodi = {e.get("id") for e in processo if e.get("id", "").startswith("N_")}
        flussi = processo.findall(f"{B}sequenceFlow")
        assert flussi
        for flusso in flussi:
            assert flusso.get("sourceRef") in nodi and flusso.get("targetRef") in nodi
        inizi = processo.findall(f"{B}startEvent") + processo.findall(f"{B}intermediateCatchEvent")
        assert inizi, f"{file.name}: manca l'inizio"


def test_documento_cita_tutti_gli_schemi():
    testo = (RADICE / "docs" / "analisi-funzionale.md").read_text(encoding="utf-8")
    for diagramma in _generatore().processi():
        assert f"analisi/{diagramma.nome}.svg" in testo
        assert f"analisi/{diagramma.nome}.bpmn" in testo
