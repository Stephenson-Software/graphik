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


def _count_image_loads(monkeypatch):
    # Wrap pygame.image.load so tests can observe how often it is called.
    loaded = []
    realLoad = pygame.image.load

    def counting_load(*args, **kwargs):
        loaded.append(args)
        return realLoad(*args, **kwargs)

    monkeypatch.setattr(pygame.image, "load", counting_load)
    return loaded


def _count_image_scales(monkeypatch):
    # Wrap pygame.transform.scale so tests can observe how often it is called.
    scaled = []
    realScale = pygame.transform.scale

    def counting_scale(*args, **kwargs):
        scaled.append(args)
        return realScale(*args, **kwargs)

    monkeypatch.setattr(pygame.transform, "scale", counting_scale)
    return scaled


def test_draw_image_reuses_loaded_surface_across_calls(monkeypatch, tmp_path):
    graphik = _make_graphik()
    image_path = tmp_path / "red.bmp"
    _write_solid_image(image_path, (255, 0, 0))

    loaded = _count_image_loads(monkeypatch)

    for _ in range(5):
        graphik.drawImage(str(image_path), 0, 0, 10, 10)

    assert len(loaded) == 1


def test_draw_image_reuses_scaled_surface_for_the_same_size(monkeypatch, tmp_path):
    graphik = _make_graphik()
    image_path = tmp_path / "red.bmp"
    _write_solid_image(image_path, (255, 0, 0))

    scaled = _count_image_scales(monkeypatch)

    for _ in range(5):
        graphik.drawImage(str(image_path), 0, 0, 10, 10)

    assert len(scaled) == 1


def test_draw_image_rescales_when_size_changes(monkeypatch, tmp_path):
    graphik = _make_graphik()
    image_path = tmp_path / "red.bmp"
    _write_solid_image(image_path, (255, 0, 0))

    scaled = _count_image_scales(monkeypatch)

    graphik.drawImage(str(image_path), 0, 0, 10, 10)
    graphik.drawImage(str(image_path), 0, 0, 12, 12)
    graphik.drawImage(str(image_path), 0, 0, 10, 10)

    # One scale per distinct size requested, in request order.
    assert [args[1] for args in scaled] == [(10, 10), (12, 12), (10, 10)]


def test_draw_image_converts_loaded_surface_for_faster_blits(monkeypatch, tmp_path):
    # pygame.Surface is a builtin type (its methods can't be monkeypatched),
    # so observe the conversion through the surface actually handed to
    # transform.scale rather than spying on convert_alpha() directly.
    graphik = _make_graphik()
    image_path = tmp_path / "red.bmp"
    _write_solid_image(image_path, (255, 0, 0))

    rawImage = pygame.image.load(str(image_path))
    scaled = _count_image_scales(monkeypatch)

    graphik.drawImage(str(image_path), 0, 0, 10, 10)

    sourcePassedToScale = scaled[0][0]
    # convert_alpha() adds a per-pixel alpha channel that a plain BMP load
    # does not have; its presence proves the cached surface was converted.
    assert not rawImage.get_flags() & pygame.SRCALPHA
    assert sourcePassedToScale.get_flags() & pygame.SRCALPHA


def test_draw_image_still_blits_correctly_after_caching(tmp_path):
    pygame.display.init()
    display = pygame.display.set_mode((20, 20))
    display.fill((0, 0, 0))
    graphik = Graphik(display)

    image_path = tmp_path / "red.bmp"
    _write_solid_image(image_path, (255, 0, 0))

    graphik.drawImage(str(image_path), 0, 0, 10, 10)
    display.fill((0, 0, 0))
    graphik.drawImage(str(image_path), 0, 0, 10, 10)

    assert tuple(display.get_at((5, 5)))[:3] == (255, 0, 0)
    assert tuple(display.get_at((15, 15)))[:3] == (0, 0, 0)


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


def test_draw_text_centers_the_text_on_the_given_position():
    # Pins the documented anchoring: drawText centers on (xpos, ypos), unlike
    # drawRectangle/drawButton/drawImage, which put their top-left corner there.
    graphik = _make_graphik((200, 100))
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)

    xpos, ypos = 100, 50
    graphik.drawText("WWWW", xpos, ypos, 20, Graphik.white)

    width, height = display.get_size()
    inked = [
        (x, y)
        for x in range(width)
        for y in range(height)
        if _rgb(display, (x, y)) != Graphik.black
    ]
    assert inked, "drawText left the surface untouched"

    xs = [x for x, _ in inked]
    ys = [y for _, y in inked]

    # The ink straddles the requested point on all four sides -- a top-left
    # anchor could never place ink above or to the left of it.
    assert min(xs) < xpos < max(xs)
    assert min(ys) < ypos < max(ys)
    # And it is centered there, not merely overlapping it. Only the horizontal
    # midpoint is asserted tightly: glyph ink is vertically asymmetric within
    # the rendered rect (capital letters sit above the baseline), so the
    # vertical ink midpoint is offset from the rect center that is centered.
    assert abs((min(xs) + max(xs)) / 2 - xpos) <= 1


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


def _click_at(monkeypatch, graphik, pos, box=(10, 10, 20, 20)):
    # Draw one button and report whether a press at `pos` reached the callback.
    calls = []
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (1, 0, 0))
    xpos, ypos, width, height = box
    graphik.drawButton(
        xpos, ypos, width, height, Graphik.blue, Graphik.white, 10, "Go", lambda: calls.append(True)
    )
    return bool(calls)


@pytest.mark.parametrize(
    "pos, expect_call",
    [
        # The box drawn at (10,10) 20x20 covers pixels 10..29 on both axes, so
        # every one of its four edges must be clickable...
        pytest.param((10, 15), True, id="left_edge"),
        pytest.param((15, 10), True, id="top_edge"),
        pytest.param((29, 15), True, id="right_edge"),
        pytest.param((15, 29), True, id="bottom_edge"),
        pytest.param((10, 10), True, id="top_left_corner"),
        # ...and nothing outside that region may be, including the first
        # coordinate past the far edge, which is not painted.
        pytest.param((9, 15), False, id="just_left_of_box"),
        pytest.param((15, 9), False, id="just_above_box"),
        pytest.param((30, 15), False, id="just_right_of_box"),
        pytest.param((15, 30), False, id="just_below_box"),
    ],
)
def test_draw_button_clickable_region_matches_the_drawn_box(monkeypatch, pos, expect_call):
    # Regression guard: the hit test used strict inequalities on both axes, which
    # left the painted left and top edge lines dead while the right and bottom
    # ones worked. The clickable region must be exactly the drawn region.
    graphik = _make_graphik((40, 40))
    assert _click_at(monkeypatch, graphik, pos) == expect_call


def test_draw_button_edges_are_painted_where_they_are_clickable():
    # Anchors the test above to what is actually drawn, so the two cannot drift:
    # the edge pixels asserted clickable are the same ones filled with colorBox.
    graphik = _make_graphik((40, 40))
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)

    graphik.drawButton(10, 10, 20, 20, Graphik.blue, Graphik.white, 10, "Go", lambda: None)

    assert _rgb(display, (10, 15)) == Graphik.blue
    assert _rgb(display, (15, 10)) == Graphik.blue
    assert _rgb(display, (29, 15)) == Graphik.blue
    assert _rgb(display, (15, 29)) == Graphik.blue
    # One past the far edge is outside the fill, matching the half-open bounds.
    assert _rgb(display, (30, 15)) == Graphik.black
    assert _rgb(display, (15, 30)) == Graphik.black


def test_adjacent_buttons_do_not_share_a_clickable_boundary(monkeypatch):
    # With half-open bounds a shared boundary belongs to exactly one button, so
    # stacking buttons edge to edge cannot fire both callbacks from one press.
    graphik = _make_graphik((60, 40))
    left = _click_at(monkeypatch, graphik, (30, 15), box=(10, 10, 20, 20))
    right = _click_at(monkeypatch, graphik, (30, 15), box=(30, 10, 20, 20))

    assert (left, right) == (False, True)


def test_draw_button_fires_callback_once_per_call_while_mouse_held(monkeypatch):
    # Pins the documented repeat-fire behavior: there is no click-edge
    # detection, so a held-down mouse inside the button fires the callback
    # on every call, not once per click.
    graphik = _make_graphik((40, 40))
    calls = []
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (15, 15))
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (1, 0, 0))

    held_down_frames = 5
    for _ in range(held_down_frames):
        graphik.drawButton(10, 10, 20, 20, Graphik.blue, Graphik.white, 10, "Go", lambda: calls.append(True))

    assert len(calls) == held_down_frames
