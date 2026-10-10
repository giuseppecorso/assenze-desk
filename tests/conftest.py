"""Impostazioni comuni ai test."""

import os

import pytest

# Le finestre dei test dell'interfaccia non compaiono sullo schermo e girano
# anche nella CI su Linux, che non ha uno schermo.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def distruggi():
    """Distrugge davvero i widget a fine test: quelli rimasti in vita rallentano
    ogni cambio di tema dei test successivi."""
    from PySide6.QtCore import QCoreApplication, QEvent

    widget = []
    yield widget.append
    for elemento in widget:
        elemento.close()
        elemento.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
