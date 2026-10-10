"""Campi di una pratica: valore, origine del dato e protezione dei campi manuali.

L'analisi propone i valori (`Proposta`) con la loro origine; l'utente può
cambiarli a mano. Un campo manuale non viene più sovrascritto dall'analisi, ma
l'ultima proposta resta disponibile per "ripristina valore automatico". Un campo
con un avviso è incerto: l'interfaccia lo evidenzia e mostra il motivo.
Logica pura: l'interfaccia la usa per sapere cosa mostrare.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum


class Origine(StrEnum):
    TESTO = "Testo"
    PDF = "PDF"
    ANAGRAFICA = "Anagrafica"
    MANUALE = "Manuale"


@dataclass(frozen=True)
class Proposta:
    valore: object = None
    origine: Origine | None = None
    avviso: str = ""  # se c'è, il campo è incerto
    scelte: tuple = ()  # valori tra cui scegliere (per esempio più tipi trovati)


VUOTA = Proposta()


@dataclass(frozen=True)
class Campo:
    valore: object = None
    origine: Origine | None = None
    avviso: str = ""
    scelte: tuple = ()
    proposta: Proposta = VUOTA  # l'ultima proposta dell'analisi, anche se il campo è manuale

    @property
    def manuale(self) -> bool:
        return self.origine is Origine.MANUALE

    @property
    def incerto(self) -> bool:
        return bool(self.avviso)

    @property
    def automatico_diverso(self) -> bool:
        """Campo manuale con una proposta diversa: si mostra con "Ripristina"."""
        return (
            self.manuale
            and self.proposta.valore is not None
            and self.proposta.valore != self.valore
        )


class Modulo:
    def __init__(self, nomi: Iterable[str]) -> None:
        self._campi = {nome: Campo() for nome in nomi}

    @property
    def nomi(self) -> tuple[str, ...]:
        return tuple(self._campi)

    def __getitem__(self, nome: str) -> Campo:
        return self._campi[nome]

    def proponi(self, proposte: Mapping[str, Proposta]) -> None:
        """Risultato di un'analisi: aggiorna i campi automatici, mai quelli manuali."""
        for nome, campo in self._campi.items():
            proposta = proposte.get(nome, VUOTA)
            if campo.manuale:
                self._campi[nome] = replace(campo, proposta=proposta)
            else:
                self._campi[nome] = _da_proposta(proposta)

    def scrivi(self, nome: str, valore: object) -> bool:
        """Valore inserito dall'utente; False se non è cambiato niente."""
        campo = self._campi[nome]
        valore = _pulito(valore)
        if valore == campo.valore:
            return False
        self._campi[nome] = replace(
            campo, valore=valore, origine=Origine.MANUALE, avviso="", scelte=()
        )
        return True

    def ripristina(self, nome: str) -> None:
        self._campi[nome] = _da_proposta(self._campi[nome].proposta)

    def svuota(self) -> None:
        self._campi = {nome: Campo() for nome in self._campi}

    def valori(self) -> dict[str, object]:
        return {nome: campo.valore for nome, campo in self._campi.items()}


def _da_proposta(proposta: Proposta) -> Campo:
    valore = _pulito(proposta.valore)
    origine = proposta.origine if valore is not None else None
    return Campo(valore, origine, proposta.avviso, proposta.scelte, proposta)


def _pulito(valore: object) -> object:
    if isinstance(valore, str):
        return valore.strip() or None
    return valore
