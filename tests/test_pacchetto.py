"""Il pacchetto è installato ed espone la versione scritta in pyproject.toml."""

from importlib.metadata import version

import assenze_desk


def test_espone_la_versione_di_pyproject():
    assert assenze_desk.__version__ == version("assenze-desk")
    assert assenze_desk.__version__ != "0.0.0"
