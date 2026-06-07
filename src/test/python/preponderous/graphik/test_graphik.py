import pygame

import preponderous.graphik as graphik_pkg
from preponderous.graphik import Graphik


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
