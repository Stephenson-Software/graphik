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


def _make_graphik(size=(10, 10)):
    pygame.display.init()
    pygame.font.init()
    display = pygame.display.set_mode(size)
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


def _rgb(display, pos):
    return tuple(display.get_at(pos))[:3]


def test_draw_rectangle_fills_expected_region_with_color():
    graphik = _make_graphik()
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)

    graphik.drawRectangle(2, 2, 5, 5, Graphik.red)

    # Inside the drawn 5x5 region at (2,2)-(7,7).
    assert _rgb(display, (4, 4)) == Graphik.red
    # Outside it, the background is untouched.
    assert _rgb(display, (8, 8)) == Graphik.black


def test_draw_text_blits_non_background_pixels():
    graphik = _make_graphik()
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)

    graphik.drawText("A", 5, 5, 12, Graphik.white)

    width, height = display.get_size()
    changed = any(
        _rgb(display, (x, y)) != Graphik.black
        for x in range(width)
        for y in range(height)
    )
    assert changed


def _count_font_constructions(monkeypatch):
    # Wrap pygame.font.Font so tests can observe how often it is built.
    constructed = []
    realFont = pygame.font.Font

    def counting_font(*args, **kwargs):
        constructed.append(args)
        return realFont(*args, **kwargs)

    monkeypatch.setattr(pygame.font, "Font", counting_font)
    return constructed


def test_draw_text_reuses_one_font_across_calls_at_the_same_size(monkeypatch):
    graphik = _make_graphik()
    constructed = _count_font_constructions(monkeypatch)

    for _ in range(5):
        graphik.drawText("A", 5, 5, 12, Graphik.white)

    assert len(constructed) == 1


def test_draw_text_builds_a_separate_font_per_size(monkeypatch):
    graphik = _make_graphik()
    constructed = _count_font_constructions(monkeypatch)

    graphik.drawText("A", 5, 5, 12, Graphik.white)
    graphik.drawText("A", 5, 5, 14, Graphik.white)
    graphik.drawText("A", 5, 5, 12, Graphik.white)

    # One font per distinct size, and the repeat of size 12 reuses the first.
    assert [args[1] for args in constructed] == [12, 14]


def test_draw_text_initializes_font_module_when_only_display_was_initialized():
    # The constructor only sets up a display, so a consumer can reasonably
    # reach drawText without ever calling pygame.font.init() themselves.
    pygame.display.init()
    display = pygame.display.set_mode((20, 20))
    graphik = Graphik(display)
    pygame.font.quit()
    assert not pygame.font.get_init()

    graphik.drawText("A", 10, 10, 12, Graphik.white)

    assert pygame.font.get_init()


def test_draw_text_rebuilds_cached_font_after_the_font_module_shuts_down(monkeypatch):
    # A Font built before the font module went down is freed memory, so the
    # cache must be dropped rather than reused when drawText restarts it.
    graphik = _make_graphik()
    graphik.drawText("A", 5, 5, 12, Graphik.white)

    pygame.font.quit()

    constructed = _count_font_constructions(monkeypatch)
    graphik.drawText("A", 5, 5, 12, Graphik.white)

    assert len(constructed) == 1


def test_draw_text_drops_cached_font_when_the_display_session_changes(monkeypatch):
    # Restarting pygame invalidates the cached font too, but leaves the font
    # module initialized, so the check above cannot catch it on its own.
    graphik = _make_graphik()
    graphik.drawText("A", 5, 5, 12, Graphik.white)

    pygame.quit()
    pygame.init()
    pygame.display.set_mode((20, 20))

    constructed = _count_font_constructions(monkeypatch)
    # The instance still holds the old display surface, so this fails the same
    # loud way it did before fonts were cached -- rather than the stale font
    # segfaulting first.
    with pytest.raises(pygame.error):
        graphik.drawText("A", 5, 5, 12, Graphik.white)

    assert len(constructed) == 1


def test_draw_button_draws_box_with_given_color():
    graphik = _make_graphik((40, 40))
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)

    graphik.drawButton(10, 10, 20, 20, Graphik.blue, Graphik.white, 10, "Go", lambda: None)

    # A corner of the box, away from the centered text, keeps the box color.
    assert _rgb(display, (11, 11)) == Graphik.blue


@pytest.mark.parametrize(
    "mouse_pos, mouse_pressed, expect_call",
    [
        pytest.param((15, 15), (1, 0, 0), True, id="clicked_inside"),
        pytest.param((0, 0), (1, 0, 0), False, id="outside_box"),
        pytest.param((15, 15), (0, 0, 0), False, id="not_pressed"),
    ],
)
def test_draw_button_invokes_callback_only_on_inside_click(
    monkeypatch, mouse_pos, mouse_pressed, expect_call
):
    graphik = _make_graphik((40, 40))
    calls = []
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: mouse_pos)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: mouse_pressed)

    graphik.drawButton(10, 10, 20, 20, Graphik.blue, Graphik.white, 10, "Go", lambda: calls.append(True))

    assert calls == ([True] if expect_call else [])
