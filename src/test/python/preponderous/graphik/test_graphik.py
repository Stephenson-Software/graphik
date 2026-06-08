import os
import subprocess
import sys

import pygame

import preponderous.graphik as graphik_pkg
from preponderous.graphik import Graphik

_SRC_MAIN = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "main", "python")
)


def _make_graphik():
    pygame.display.init()
    display = pygame.display.set_mode((10, 10))
    return Graphik(display)


def test_canonical_import_exposes_graphik_class():
    # `from preponderous.graphik import Graphik` resolves to the class.
    assert Graphik is graphik_pkg.Graphik


def test_get_version_matches_package_version():
    # getVersion() must read the single version source, not an unset attribute.
    graphik = _make_graphik()
    assert graphik.getVersion() == graphik_pkg.__version__


def test_package_imports_without_pygame():
    # Regression guard for the lazy Graphik import: importing the package (as
    # setuptools does to resolve the dynamic version) must not require pygame.
    # Run in a fresh interpreter with pygame blocked so the eager-import
    # variant would fail here.
    code = (
        "import sys; sys.modules['pygame'] = None; "
        "import preponderous.graphik as p; "
        "print(p.__version__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=dict(os.environ, PYTHONPATH=_SRC_MAIN),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == graphik_pkg.__version__
