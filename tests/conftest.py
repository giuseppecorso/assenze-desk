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
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent

    widget = []
    yield widget.append
    for elemento in widget:
        if shiboken6.isValid(elemento):  # alcuni si distruggono da soli alla chiusura
            elemento.close()
            elemento.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
