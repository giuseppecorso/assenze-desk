"""Schemi BPMN dell'analisi funzionale: SVG per il documento e file BPMN 2.0.

Da un'unica descrizione di ogni processo (corsie, nodi, flussi) escono:
- `docs/analisi/<nome>.svg`, che GitHub mostra dentro `docs/analisi-funzionale.md`;
- `docs/analisi/<nome>.bpmn`, file BPMN 2.0 con le coordinate (DI), da aprire e
  modificare con bpmn.io o Camunda Modeler.
I processi lunghi sono divisi in due schemi uniti da un evento di collegamento
(link), come un rimando "continua nello schema 2".

Uso: python scripts/genera_bpmn.py
"""

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

CARTELLA = Path(__file__).resolve().parents[1] / "docs" / "analisi"

# Misure (pixel)
TESTATA_POOL = 30
TESTATA_CORSIA = 30
X_INIZIO = TESTATA_POOL + TESTATA_CORSIA + 55
COLONNA = 140
RIGA = 110
ALTEZZA_BASE = 130
ATTIVITA = (118, 64)
EVENTO = 34
GATEWAY = 44
Y_POOL = 46

COLORI = {
    "testo": "#1f2937",
    "secondario": "#4b5563",
    "bordo": "#374151",
    "corsia_app": "#eef4ff",
    "attivita_app": "#dbe7ff",
    "problema": "#dc2626",
    "sfondo": "#ffffff",
}


@dataclass
class Nodo:
    id: str
    tipo: str  # inizio, fine, utente, sistema, attivita, gateway, link_lancio, link_cattura
    testo: str
    corsia: str
    colonna: int
    riga: int = 0
    problema: int | None = None
    nota: str = ""  # documentazione nel file BPMN


@dataclass
class Diagramma:
    nome: str
    titolo: str
    pool: str
    corsie: list[tuple[str, str]]  # (id, nome)
    nodi: list[Nodo]
    flussi: list[tuple[str, str, str]]  # (da, a, etichetta)
    corsie_app: set[str] = field(default_factory=set)


# --- Layout ---


def _corsie(d: Diagramma) -> dict[str, tuple[float, float, int]]:
    """id corsia → (y alto, altezza, riga minima)."""
    risultato, y = {}, Y_POOL
    for id_corsia, _nome in d.corsie:
        righe = [n.riga for n in d.nodi if n.corsia == id_corsia] or [0]
        altezza = ALTEZZA_BASE + RIGA * (max(righe) - min(righe))
        risultato[id_corsia] = (y, altezza, min(righe))
        y += altezza
    return risultato


def _centro(n: Nodo, corsie) -> tuple[float, float]:
    alto, _altezza, riga_min = corsie[n.corsia]
    return X_INIZIO + n.colonna * COLONNA, alto + ALTEZZA_BASE / 2 + RIGA * (n.riga - riga_min)


def _misura(n: Nodo) -> tuple[float, float]:
    if n.tipo in ("inizio", "fine", "link_lancio", "link_cattura"):
        return EVENTO, EVENTO
    if n.tipo == "gateway":
        return GATEWAY, GATEWAY
    return ATTIVITA


def _riquadro(n: Nodo, corsie) -> tuple[float, float, float, float]:
    cx, cy = _centro(n, corsie)
    w, h = _misura(n)
    return cx - w / 2, cy - h / 2, w, h


def _percorso(sorgente: Nodo, arrivo: Nodo, corsie) -> list[tuple[float, float]]:
    sx, sy = _centro(sorgente, corsie)
    tx, ty = _centro(arrivo, corsie)
    sw, sh = _misura(sorgente)
    tw, _th = _misura(arrivo)
    destra, sinistra = sx + sw / 2, tx - tw / 2
    if abs(sy - ty) < 1:
        return [(destra, sy), (sinistra, ty)]
    if sorgente.tipo == "gateway" and arrivo.colonna == sorgente.colonna + 1:
        # verso la colonna accanto esce dall'alto o dal basso; più lontano, di lato
        uscita = sy - sh / 2 if ty < sy else sy + sh / 2
        return [(sx, uscita), (sx, ty), (sinistra, ty)]
    # tra colonne vicine la svolta sta a metà; più lontano subito prima dell'arrivo,
    # così la linea non passa sotto le attività in mezzo
    svolta = (destra + sinistra) / 2 if arrivo.colonna - sorgente.colonna <= 1 else sinistra - 22
    return [(destra, sy), (svolta, sy), (svolta, ty), (sinistra, ty)]


def _dimensioni(d: Diagramma, corsie) -> tuple[float, float]:
    larghezza = X_INIZIO + max(n.colonna for n in d.nodi) * COLONNA + 70
    alto, altezza, _ = list(corsie.values())[-1]
    return larghezza, alto + altezza + 12


# --- SVG ---


def _righe_testo(testo: str, massimo: int = 18) -> list[str]:
    righe, attuale = [], ""
    for parola in testo.split():
        prova = f"{attuale} {parola}".strip()
        if len(prova) > massimo and attuale:
            righe.append(attuale)
            attuale = parola
        else:
            attuale = prova
    return [*righe, attuale] if attuale else righe


def _testo_svg(
    x: float,
    y: float,
    testo: str,
    dimensione=11,
    peso=400,
    colore=None,
    ancora="middle",
    massimo=18,
):
    righe = _righe_testo(testo, massimo)
    inizio = y - (len(righe) - 1) * (dimensione + 2) / 2
    colore = colore or COLORI["testo"]
    return "".join(
        f'<text x="{x:.1f}" y="{inizio + i * (dimensione + 2):.1f}" font-size="{dimensione}" '
        f'font-weight="{peso}" fill="{colore}" text-anchor="{ancora}" '
        f'dominant-baseline="middle">{escape(riga)}</text>'
        for i, riga in enumerate(righe)
    )


def _icona(n: Nodo, x: float, y: float) -> str:
    c = COLORI["secondario"]
    if n.tipo == "utente":
        return (
            f'<circle cx="{x + 11}" cy="{y + 9}" r="3" fill="none" stroke="{c}"/>'
            f'<path d="M{x + 5} {y + 18}a6 5 0 0 1 12 0" fill="none" stroke="{c}"/>'
        )
    if n.tipo == "sistema":
        return (
            f'<circle cx="{x + 11}" cy="{y + 12}" r="5" fill="none" stroke="{c}" '
            f'stroke-width="2.4" stroke-dasharray="2.2 1.6"/>'
            f'<circle cx="{x + 11}" cy="{y + 12}" r="1.6" fill="{c}"/>'
        )
    return ""


def _nodo_svg(n: Nodo, corsie, app: bool, sale: bool = False) -> str:
    """`sale`: da questo gateway esce una freccia verso l'alto (la scritta va sotto)."""
    x, y, w, h = _riquadro(n, corsie)
    cx, cy = x + w / 2, y + h / 2
    bordo = COLORI["bordo"]
    if n.tipo in ("inizio", "fine", "link_lancio", "link_cattura"):
        spessore = 3 if n.tipo == "fine" else 1.4
        parti = [
            f'<circle cx="{cx}" cy="{cy}" r="{w / 2}" fill="#fff" stroke="{bordo}" '
            f'stroke-width="{spessore}"/>'
        ]
        if n.tipo.startswith("link"):
            parti.append(
                f'<circle cx="{cx}" cy="{cy}" r="{w / 2 - 3}" fill="none" stroke="{bordo}"/>'
                f'<path d="M{cx - 7} {cy - 3}h7v-4l7 7-7 7v-4h-7z" '
                f'fill="{bordo if n.tipo == "link_lancio" else "none"}" stroke="{bordo}"/>'
            )
        parti.append(_testo_svg(cx, y + h + 16, n.testo, 10, colore=COLORI["secondario"]))
        return "".join(parti)
    if n.tipo == "gateway":
        return (
            f'<path d="M{cx} {y}L{x + w} {cy}L{cx} {y + h}L{x} {cy}Z" fill="#fff" '
            f'stroke="{bordo}" stroke-width="1.4"/>'
            f'<path d="M{cx - 7} {cy - 7}l14 14M{cx + 7} {cy - 7}l-14 14" stroke="{bordo}" '
            f'stroke-width="2.6"/>'
            + _testo_svg(
                cx, y + h + 16 if sale else y - 18, n.testo, 10, colore=COLORI["secondario"]
            )
        )
    sfondo = COLORI["attivita_app"] if app else "#fff"
    parti = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{sfondo}" '
        f'stroke="{bordo}" stroke-width="1.4"/>',
        _icona(n, x, y),
        _testo_svg(cx + 4, cy + 5, n.testo, 10.5, massimo=19),
    ]
    if n.problema is not None:
        parti.append(
            f'<circle cx="{x + w - 2}" cy="{y + 2}" r="9" fill="{COLORI["problema"]}"/>'
            f'<text x="{x + w - 2}" y="{y + 2.5}" font-size="10" font-weight="700" fill="#fff" '
            f'text-anchor="middle" dominant-baseline="middle">{n.problema}</text>'
        )
    return "".join(parti)


def _svg(d: Diagramma) -> str:
    corsie = _corsie(d)
    larghezza, altezza = _dimensioni(d, corsie)
    nodi = {n.id: n for n in d.nodi}
    parti = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {larghezza:.0f} {altezza:.0f}" '
        f'width="{larghezza:.0f}" height="{altezza:.0f}" '
        'font-family="Segoe UI, Helvetica, Arial, sans-serif">',
        f'<rect width="100%" height="100%" fill="{COLORI["sfondo"]}"/>',
        '<defs><marker id="freccia" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="{COLORI["bordo"]}"/>'
        "</marker></defs>",
        _testo_svg(12, 22, d.titolo, 14, 600, ancora="start", massimo=200),
    ]
    alto_pool = Y_POOL
    altezza_pool = sum(a for _y, a, _r in corsie.values())
    parti.append(
        f'<rect x="10" y="{alto_pool}" width="{larghezza - 20}" height="{altezza_pool}" '
        f'fill="none" stroke="{COLORI["bordo"]}" stroke-width="1.4"/>'
        f'<line x1="{10 + TESTATA_POOL}" y1="{alto_pool}" x2="{10 + TESTATA_POOL}" '
        f'y2="{alto_pool + altezza_pool}" stroke="{COLORI["bordo"]}"/>'
        f'<text transform="translate({10 + TESTATA_POOL / 2},{alto_pool + altezza_pool / 2}) '
        f'rotate(-90)" font-size="12" font-weight="600" fill="{COLORI["testo"]}" '
        f'text-anchor="middle" dominant-baseline="middle">{escape(d.pool)}</text>'
    )
    for id_corsia, nome in d.corsie:
        y, h, _ = corsie[id_corsia]
        x0 = 10 + TESTATA_POOL
        if id_corsia in d.corsie_app:
            parti.append(
                f'<rect x="{x0}" y="{y}" width="{larghezza - 20 - TESTATA_POOL}" height="{h}" '
                f'fill="{COLORI["corsia_app"]}"/>'
            )
        parti.append(
            f'<rect x="{x0}" y="{y}" width="{larghezza - 20 - TESTATA_POOL}" height="{h}" '
            f'fill="none" stroke="{COLORI["bordo"]}"/>'
            f'<line x1="{x0 + TESTATA_CORSIA}" y1="{y}" x2="{x0 + TESTATA_CORSIA}" y2="{y + h}" '
            f'stroke="{COLORI["bordo"]}"/>'
            f'<text transform="translate({x0 + TESTATA_CORSIA / 2},{y + h / 2}) rotate(-90)" '
            f'font-size="11" fill="{COLORI["testo"]}" text-anchor="middle" '
            f'dominant-baseline="middle">{escape(nome)}</text>'
        )
    for da, a, etichetta in d.flussi:
        punti = _percorso(nodi[da], nodi[a], corsie)
        linea = " ".join(f"{x:.1f},{y:.1f}" for x, y in punti)
        parti.append(
            f'<polyline points="{linea}" fill="none" stroke="{COLORI["bordo"]}" '
            'stroke-width="1.3" marker-end="url(#freccia)"/>'
        )
        if etichetta:
            (x1, y1), (x2, y2) = punti[0], punti[1]
            verticale = abs(x1 - x2) < 1
            lx, ly = (x1 + 6, (y1 + y2) / 2) if verticale else (x1 + 8, y1 - 9)
            parti.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="10" fill="{COLORI["secondario"]}" '
                f'dominant-baseline="middle">{escape(etichetta)}</text>'
            )
    for n in d.nodi:
        sale = any(
            da == n.id and _percorso(n, nodi[a], corsie)[1][1] < _centro(n, corsie)[1]
            for da, a, _e in d.flussi
        )
        parti.append(_nodo_svg(n, corsie, n.corsia in d.corsie_app, sale))
    parti.append("</svg>\n")
    return "".join(parti)


# --- BPMN 2.0 ---

NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
}
TIPI_BPMN = {
    "inizio": "startEvent",
    "fine": "endEvent",
    "utente": "userTask",
    "sistema": "serviceTask",
    "attivita": "task",
    "gateway": "exclusiveGateway",
    "link_lancio": "intermediateThrowEvent",
    "link_cattura": "intermediateCatchEvent",
}


def _bpmn(d: Diagramma) -> str:
    for prefisso, uri in NS.items():
        ET.register_namespace(prefisso, uri)

    def b(nome):
        return f"{{{NS['bpmn']}}}{nome}"

    def di(prefisso, nome):
        return f"{{{NS[prefisso]}}}{nome}"

    corsie = _corsie(d)
    larghezza, _ = _dimensioni(d, corsie)
    nodi = {n.id: n for n in d.nodi}
    radice = ET.Element(
        b("definitions"),
        {"id": f"Definizioni_{d.nome}", "targetNamespace": "https://example.org/assenze-desk"},
    )
    collaborazione = ET.SubElement(radice, b("collaboration"), {"id": f"Collab_{d.nome}"})
    ET.SubElement(
        collaborazione,
        b("participant"),
        {"id": f"Pool_{d.nome}", "name": d.pool, "processRef": f"Processo_{d.nome}"},
    )
    processo = ET.SubElement(
        radice,
        b("process"),
        {"id": f"Processo_{d.nome}", "name": d.titolo, "isExecutable": "false"},
    )
    insieme = ET.SubElement(processo, b("laneSet"), {"id": f"Corsie_{d.nome}"})
    for id_corsia, nome in d.corsie:
        corsia = ET.SubElement(insieme, b("lane"), {"id": f"Corsia_{id_corsia}", "name": nome})
        for n in d.nodi:
            if n.corsia == id_corsia:
                ET.SubElement(corsia, b("flowNodeRef")).text = f"N_{n.id}"
    entrate = {n.id: [] for n in d.nodi}
    uscite = {n.id: [] for n in d.nodi}
    for numero, (da, a, _e) in enumerate(d.flussi, 1):
        uscite[da].append(f"F_{numero}")
        entrate[a].append(f"F_{numero}")
    for n in d.nodi:
        attributi = {"id": f"N_{n.id}", "name": n.testo}
        elemento = ET.SubElement(processo, b(TIPI_BPMN[n.tipo]), attributi)
        if n.nota:
            ET.SubElement(elemento, b("documentation")).text = n.nota
        for f in entrate[n.id]:
            ET.SubElement(elemento, b("incoming")).text = f
        for f in uscite[n.id]:
            ET.SubElement(elemento, b("outgoing")).text = f
        if n.tipo.startswith("link"):
            ET.SubElement(elemento, b("linkEventDefinition"), {"id": f"L_{n.id}", "name": "A"})
    for numero, (da, a, etichetta) in enumerate(d.flussi, 1):
        attributi = {"id": f"F_{numero}", "sourceRef": f"N_{da}", "targetRef": f"N_{a}"}
        if etichetta:
            attributi["name"] = etichetta
        ET.SubElement(processo, b("sequenceFlow"), attributi)

    diagramma = ET.SubElement(radice, di("bpmndi", "BPMNDiagram"), {"id": f"DI_{d.nome}"})
    piano = ET.SubElement(
        diagramma,
        di("bpmndi", "BPMNPlane"),
        {"id": f"Piano_{d.nome}", "bpmnElement": f"Collab_{d.nome}"},
    )

    def forma(id_elemento, x, y, w, h, **extra):
        shape = ET.SubElement(
            piano,
            di("bpmndi", "BPMNShape"),
            {"id": f"DI_{id_elemento}", "bpmnElement": id_elemento, **extra},
        )
        ET.SubElement(
            shape,
            di("dc", "Bounds"),
            {"x": f"{x:.0f}", "y": f"{y:.0f}", "width": f"{w:.0f}", "height": f"{h:.0f}"},
        )

    altezza_pool = sum(a for _y, a, _r in corsie.values())
    forma(f"Pool_{d.nome}", 10, Y_POOL, larghezza - 20, altezza_pool, isHorizontal="true")
    for id_corsia, _nome in d.corsie:
        y, h, _ = corsie[id_corsia]
        forma(
            f"Corsia_{id_corsia}",
            10 + TESTATA_POOL,
            y,
            larghezza - 20 - TESTATA_POOL,
            h,
            isHorizontal="true",
        )
    for n in d.nodi:
        extra = {"isMarkerVisible": "true"} if n.tipo == "gateway" else {}
        forma(f"N_{n.id}", *_riquadro(n, corsie), **extra)
    for numero, (da, a, _e) in enumerate(d.flussi, 1):
        arco = ET.SubElement(
            piano,
            di("bpmndi", "BPMNEdge"),
            {"id": f"DI_F_{numero}", "bpmnElement": f"F_{numero}"},
        )
        for x, y in _percorso(nodi[da], nodi[a], corsie):
            ET.SubElement(arco, di("di", "waypoint"), {"x": f"{x:.0f}", "y": f"{y:.0f}"})
    ET.indent(radice)
    xml = ET.tostring(radice, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml}\n'


# --- Processi ---

OP, APP = "operatore", "app"
CORSIE_TO_BE = [(OP, "Operatore"), (APP, "Assenze Desk")]


def processi() -> list[Diagramma]:
    as_is_1 = Diagramma(
        "as-is-malattia-1",
        "AS-IS · Malattia, parte 1: dalla mail al certificato",
        "Ufficio del personale",
        [(OP, "Operatore")],
        [
            Nodo("inizio", "inizio", "Mail di malattia ricevuta", OP, 0),
            Nodo(
                "leggi",
                "utente",
                "Legge la mail e copia protocollo, CF e date",
                OP,
                1,
                problema=1,
                nota="Dati ricopiati a mano: errori di trascrizione.",
            ),
            Nodo(
                "cerca",
                "utente",
                "Cerca il dipendente nell'Excel per email o nome",
                OP,
                2,
                problema=2,
                nota="Con un indirizzo diverso da quello in anagrafica non lo trova.",
            ),
            Nodo("trovato", "gateway", "Trovato?", OP, 3),
            Nodo("cerca_mano", "utente", "Cerca a mano per CF o JobOrder", OP, 4, riga=1),
            Nodo("portale", "utente", "Apre il portale INPS e incolla CF e protocollo", OP, 5),
            Nodo(
                "scarica",
                "utente",
                "Scarica il PDF, lo rinomina e lo archivia",
                OP,
                6,
                problema=3,
                nota="Nomi dei file non uniformi: certificati difficili da ritrovare.",
            ),
            Nodo("verso_2", "link_lancio", "Continua (A)", OP, 7),
        ],
        [
            ("inizio", "leggi", ""),
            ("leggi", "cerca", ""),
            ("cerca", "trovato", ""),
            ("trovato", "portale", "Sì"),
            ("trovato", "cerca_mano", "No"),
            ("cerca_mano", "portale", ""),
            ("portale", "scarica", ""),
            ("scarica", "verso_2", ""),
        ],
    )
    as_is_2 = Diagramma(
        "as-is-malattia-2",
        "AS-IS · Malattia, parte 2: comunicazioni e registrazione",
        "Ufficio del personale",
        [(OP, "Operatore")],
        [
            Nodo("da_1", "link_cattura", "Da parte 1 (A)", OP, 0),
            Nodo(
                "episodio",
                "utente",
                "Ricostruisce l'episodio a mano",
                OP,
                1,
                problema=4,
                nota="Calcolo a mano dei giorni dell'episodio.",
            ),
            Nodo("soglia", "gateway", "Oltre 3 giorni?", OP, 2),
            Nodo("ufficio", "utente", "Scrive la mail all'ufficio e allega i PDF", OP, 3, riga=1),
            Nodo(
                "risposta",
                "utente",
                "Scrive la risposta al lavoratore",
                OP,
                4,
                problema=5,
                nota="Risposta creata sulla mail selezionata, non su quella gestita.",
            ),
            Nodo(
                "tracking",
                "utente",
                "Aggiorna l'Excel di tracking",
                OP,
                5,
                problema=6,
                nota="File riscritto per intero a ogni modifica, senza storico.",
            ),
            Nodo("sistemi", "utente", "Registra nei sistemi interni e sposta la mail", OP, 6),
            Nodo("fine", "fine", "Pratica gestita", OP, 7),
        ],
        [
            ("da_1", "episodio", ""),
            ("episodio", "soglia", ""),
            ("soglia", "risposta", "No"),
            ("soglia", "ufficio", "Sì"),
            ("ufficio", "risposta", ""),
            ("risposta", "tracking", ""),
            ("tracking", "sistemi", ""),
            ("sistemi", "fine", ""),
        ],
    )
    to_be_1 = Diagramma(
        "to-be-malattia-1",
        "TO-BE · Malattia con Assenze Desk, parte 1: dalla mail al certificato",
        "Ufficio del personale",
        CORSIE_TO_BE,
        [
            Nodo("inizio", "inizio", "Mail di malattia ricevuta", OP, 0),
            Nodo("importa", "utente", "Importa la mail da Outlook", OP, 1),
            Nodo(
                "analizza",
                "sistema",
                "Legge i dati e trova il dipendente",
                APP,
                2,
                nota="Dipendente da JobOrder, mittente (anche indirizzi ricordati), CF, nome.",
            ),
            Nodo("completi", "gateway", "Dati completi e plausibili?", APP, 3),
            Nodo("corregge", "utente", "Corregge o sceglie (campi protetti)", OP, 4),
            Nodo("portale", "utente", "Apre il portale: CF e protocollo già copiati", OP, 5),
            Nodo("pdf", "sistema", "Trova il PDF, lo archivia e lo legge", APP, 6),
            Nodo("verso_2", "link_lancio", "Continua (A)", APP, 7),
        ],
        [
            ("inizio", "importa", ""),
            ("importa", "analizza", ""),
            ("analizza", "completi", ""),
            ("completi", "corregge", "No"),
            ("completi", "portale", "Sì"),
            ("corregge", "portale", ""),
            ("portale", "pdf", ""),
            ("pdf", "verso_2", ""),
        ],
        {APP},
    )
    to_be_2 = Diagramma(
        "to-be-malattia-2",
        "TO-BE · Malattia con Assenze Desk, parte 2: comunicazioni e registrazione",
        "Ufficio del personale",
        CORSIE_TO_BE,
        [
            Nodo("da_1", "link_cattura", "Da parte 1 (A)", APP, 0),
            Nodo("episodio", "sistema", "Calcola episodio e stato della pratica", APP, 1),
            Nodo("chi", "utente", "Sceglie a chi rispondere (proposta automatica)", OP, 2),
            Nodo("bozze", "sistema", "Bozze al lavoratore e, oltre soglia, all'ufficio", APP, 3),
            Nodo("invia", "utente", "Controlla e invia le bozze", OP, 4),
            Nodo("salva", "sistema", "Salva pratica e storico, sposta la mail", APP, 5),
            Nodo(
                "sistemi",
                "utente",
                "Registra nei sistemi interni",
                OP,
                6,
                nota="Fuori dall'ambito del prodotto.",
            ),
            Nodo("fine", "fine", "Pratica gestita", OP, 7),
        ],
        [
            ("da_1", "episodio", ""),
            ("episodio", "chi", ""),
            ("chi", "bozze", ""),
            ("bozze", "invia", ""),
            ("invia", "salva", ""),
            ("salva", "sistemi", ""),
            ("sistemi", "fine", ""),
        ],
        {APP},
    )
    giustificativo = Diagramma(
        "to-be-giustificativo",
        "TO-BE · Richiesta di ferie o permesso con Assenze Desk",
        "Ufficio del personale",
        CORSIE_TO_BE,
        [
            Nodo("inizio", "inizio", "Richiesta ricevuta", OP, 0),
            Nodo("importa", "utente", "Importa o incolla la richiesta", OP, 1),
            Nodo("analizza", "sistema", "Legge tipo, giorni e ore; trova il dipendente", APP, 2),
            Nodo(
                "righe",
                "sistema",
                "Righe per giorno con l'orario del cliente; avvisi",
                APP,
                3,
                nota="Weekend esclusi salvo scelta; avviso se supera le ore residue.",
            ),
            Nodo("avvisi", "gateway", "Avvisi?", APP, 4),
            Nodo("corregge", "utente", "Corregge giorni, ore o tipo", OP, 5),
            Nodo("salva", "utente", "Salva le righe", OP, 6),
            Nodo("bozza", "sistema", "Bozza di conferma al lavoratore", APP, 7),
            Nodo("export", "sistema", "Export in Excel delle righe da caricare", APP, 8),
            Nodo("fine", "fine", "Richiesta registrata", APP, 9),
        ],
        [
            ("inizio", "importa", ""),
            ("importa", "analizza", ""),
            ("analizza", "righe", ""),
            ("righe", "avvisi", ""),
            ("avvisi", "corregge", "Sì"),
            ("avvisi", "salva", "No"),
            ("corregge", "salva", ""),
            ("salva", "bozza", ""),
            ("bozza", "export", ""),
            ("export", "fine", ""),
        ],
        {APP},
    )
    return [as_is_1, as_is_2, to_be_1, to_be_2, giustificativo]


def main() -> None:
    CARTELLA.mkdir(parents=True, exist_ok=True)
    for diagramma in processi():
        (CARTELLA / f"{diagramma.nome}.svg").write_text(
            _svg(diagramma), encoding="utf-8", newline="\n"
        )
        (CARTELLA / f"{diagramma.nome}.bpmn").write_text(
            _bpmn(diagramma), encoding="utf-8", newline="\n"
        )
        print(f"Creati: docs/analisi/{diagramma.nome}.svg e .bpmn")


if __name__ == "__main__":
    main()
