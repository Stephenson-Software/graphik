import os
import subprocess
import sys

import pygame
import pytest

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


def test_constructor_stores_supplied_display():
    # The explicit-display form every consumer uses keeps working.
    pygame.display.init()
    display = pygame.display.set_mode((10, 10))
    graphik = Graphik(display)
    assert graphik.getGameDisplay() is display


def test_no_arg_constructor_creates_default_display():
    # Graphik() must be reachable (it was dead code behind a duplicate __init__)
    # and fall back to a default display rather than raising TypeError.
    graphik = Graphik()
    assert graphik.getGameDisplay() is not None


def test_color_constants_are_reachable():
    # The color constants used to be assigned only in an unreachable __init__;
    # they must now be present on both the class and any instance.
    assert Graphik.white == (255, 255, 255)
    assert Graphik.black == (0, 0, 0)
    assert Graphik.red == (200, 0, 0)
    assert Graphik.green == (0, 200, 0)
    assert Graphik.blue == (0, 0, 200)
    assert _make_graphik().white == (255, 255, 255)


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


def _write_solid_image(path, color, size=(4, 4)):
    # BMP is supported by pygame without SDL_image, so the fixture is portable.
    surface = pygame.Surface(size)
    surface.fill(color)
    pygame.image.save(surface, str(path))


def test_draw_image_blits_scaled_image_to_position(tmp_path):
    pygame.display.init()
    display = pygame.display.set_mode((20, 20))
    display.fill((0, 0, 0))
    graphik = Graphik(display)

    image_path = tmp_path / "red.bmp"
    _write_solid_image(image_path, (255, 0, 0))

    # Scale a 4x4 red image up to 10x10 and blit it at the origin.
    graphik.drawImage(str(image_path), 0, 0, 10, 10)

    # A pixel inside the drawn 10x10 region is red; one outside stays untouched.
    assert tuple(display.get_at((5, 5)))[:3] == (255, 0, 0)
    assert tuple(display.get_at((15, 15)))[:3] == (0, 0, 0)


def test_draw_image_missing_file_raises(tmp_path):
    graphik = _make_graphik()
    missing = tmp_path / "does_not_exist.bmp"
    with pytest.raises((FileNotFoundError, pygame.error)):
        graphik.drawImage(str(missing), 0, 0, 10, 10)
