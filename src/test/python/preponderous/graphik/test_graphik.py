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
    # The constructor docstring and the README both promise 900x600
    # specifically, so pin the size and not merely the display's existence.
    assert graphik.getGameDisplay().get_size() == (900, 600)


@pytest.mark.parametrize("supplied", [True, False], ids=["supplied_display", "default_display"])
def test_game_display_attribute_is_the_bound_surface(supplied):
    # Consumers read the gameDisplay attribute directly rather than going
    # through getGameDisplay() -- Apex sizes its layout off
    # graphik.gameDisplay.get_size() -- so the attribute name is part of the
    # public contract. Renaming it to something private would leave every
    # test above green while breaking those call sites, so pin it on both
    # constructor paths.
    pygame.display.init()
    if supplied:
        display = pygame.display.set_mode((10, 10))
        graphik = Graphik(display)
        assert graphik.gameDisplay is display
    else:
        graphik = Graphik()
    assert graphik.gameDisplay is graphik.getGameDisplay()


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


def test_package_rejects_unknown_attribute_names():
    # Defining __getattr__ on the package takes over every failed attribute
    # lookup, so the miss path has to keep raising AttributeError -- returning
    # None or letting a different error escape would make a typo'd import read
    # as something other than "no such name".
    with pytest.raises(AttributeError):
        getattr(graphik_pkg, "Graphic")


def test_star_import_exposes_graphik_and_version():
    # `from preponderous.graphik import *` resolves every name in __all__ via
    # the package's __getattr__, so Graphik must be reachable that way even
    # though it is not bound in the module namespace until first access. A
    # name listed in __all__ that __getattr__ cannot serve would make the star
    # import itself raise AttributeError.
    namespace = {}
    exec("from preponderous.graphik import *", namespace)

    assert namespace["Graphik"] is Graphik
    assert namespace["__version__"] == graphik_pkg.__version__
    assert set(graphik_pkg.__all__) == {"Graphik", "__version__"}


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


def test_draw_image_fills_exactly_the_requested_region(tmp_path):
    # Every other drawImage test scales to a square (or a single-pixel-high)
    # size, so nothing distinguishes `width` from `height`: scaling to
    # (height, width) instead passes all of them. Pin the exact edges of a
    # non-square region at an offset, as the drawRectangle test below does,
    # which also pins the documented top-left anchoring down to the pixel.
    graphik = _make_graphik((20, 20))
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)

    image_path = tmp_path / "red.bmp"
    _write_solid_image(image_path, (255, 0, 0))

    graphik.drawImage(str(image_path), 3, 4, 6, 5)

    # Every corner of the 6x5 region at (3,4)-(8,8) is painted...
    assert _rgb(display, (3, 4)) == (255, 0, 0)
    assert _rgb(display, (8, 4)) == (255, 0, 0)
    assert _rgb(display, (3, 8)) == (255, 0, 0)
    assert _rgb(display, (8, 8)) == (255, 0, 0)
    # ...and the first coordinate past each edge is not.
    assert _rgb(display, (2, 6)) == Graphik.black
    assert _rgb(display, (9, 6)) == Graphik.black
    assert _rgb(display, (5, 3)) == Graphik.black
    assert _rgb(display, (5, 9)) == Graphik.black


def test_draw_image_missing_file_raises_file_not_found_error(tmp_path):
    # The docstring promises FileNotFoundError for a path with no file behind
    # it, distinct from the pygame.error an undecodable file raises (see the
    # next test). Accepting either type here would let the two failure modes
    # collapse into one without any test noticing.
    graphik = _make_graphik()
    missing = tmp_path / "does_not_exist.bmp"
    with pytest.raises(FileNotFoundError):
        graphik.drawImage(str(missing), 0, 0, 10, 10)


def test_draw_image_undecodable_file_raises_pygame_error(tmp_path):
    # The docstring separates the two failure modes: a path with no file behind
    # it raises FileNotFoundError (pinned above), while a file pygame cannot
    # decode raises pygame.error.
    graphik = _make_graphik()
    notAnImage = tmp_path / "not_really.bmp"
    notAnImage.write_text("this is text, not an image")

    with pytest.raises(pygame.error):
        graphik.drawImage(str(notAnImage), 0, 0, 10, 10)


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


def test_draw_image_does_not_cache_a_failed_load(monkeypatch, tmp_path):
    # The counterpart to the test above: only a *successful* load is cached, so
    # a path that fails keeps raising and keeps being retried. Caching the
    # failure instead would turn the second call into a silent no-op or a
    # KeyError, and an asset that appears on disk later would never be picked
    # up even though the process was told to draw it again.
    graphik = _make_graphik()
    missing = tmp_path / "appears_later.bmp"

    loaded = _count_image_loads(monkeypatch)

    for _ in range(3):
        with pytest.raises(FileNotFoundError):
            graphik.drawImage(str(missing), 0, 0, 10, 10)

    # Every call re-attempted the load rather than being served from a cache.
    assert len(loaded) == 3

    # And once the file exists, the very next call draws it -- no restart needed.
    _write_solid_image(missing, (255, 0, 0))
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)
    graphik.drawImage(str(missing), 0, 0, 5, 5)

    assert _rgb(display, (2, 2)) == (255, 0, 0)


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


def test_draw_image_scaled_cache_is_kept_per_path(monkeypatch, tmp_path):
    # The scaled cache holds the most recent (size, surface) pair *per path*,
    # not one pair overall. Rescaling one asset must therefore leave another
    # asset's cached scale intact -- a single shared "last size" slot would
    # rescale the blue image below even though its size never changed.
    graphik = _make_graphik()
    redPath = tmp_path / "red.bmp"
    bluePath = tmp_path / "blue.bmp"
    _write_solid_image(redPath, (255, 0, 0))
    _write_solid_image(bluePath, (0, 0, 255))

    scaled = _count_image_scales(monkeypatch)

    graphik.drawImage(str(redPath), 0, 0, 10, 10)
    graphik.drawImage(str(bluePath), 0, 0, 10, 10)
    graphik.drawImage(str(redPath), 0, 0, 12, 12)
    graphik.drawImage(str(bluePath), 0, 0, 10, 10)

    # Red scaled twice (two sizes), blue once: its repeat is served from cache
    # despite the red rescale in between.
    assert [args[1] for args in scaled] == [(10, 10), (10, 10), (12, 12)]


def test_draw_image_caches_each_path_independently(monkeypatch, tmp_path):
    # Both caches are keyed on filePath alone, so a second asset must get its
    # own entry rather than evicting the first (which would reload on every
    # alternating call) or reusing it (which would draw the wrong image).
    pygame.display.init()
    display = pygame.display.set_mode((20, 20))
    display.fill(Graphik.black)
    graphik = Graphik(display)

    redPath = tmp_path / "red.bmp"
    bluePath = tmp_path / "blue.bmp"
    _write_solid_image(redPath, (255, 0, 0))
    _write_solid_image(bluePath, (0, 0, 255))

    loaded = _count_image_loads(monkeypatch)

    graphik.drawImage(str(redPath), 0, 0, 10, 10)
    graphik.drawImage(str(bluePath), 10, 0, 10, 10)
    graphik.drawImage(str(redPath), 0, 10, 10, 10)
    graphik.drawImage(str(bluePath), 10, 10, 10, 10)

    # One load per distinct path; the alternating repeats are served from cache.
    assert [args[0] for args in loaded] == [str(redPath), str(bluePath)]
    # And each quadrant carries the color of the path it was drawn from.
    assert _rgb(display, (5, 5)) == (255, 0, 0)
    assert _rgb(display, (15, 5)) == (0, 0, 255)
    assert _rgb(display, (5, 15)) == (255, 0, 0)
    assert _rgb(display, (15, 15)) == (0, 0, 255)


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


def test_draw_image_leaves_display_visible_through_transparent_pixels(tmp_path):
    # The test above only proves an alpha channel was *added*. drawImage's
    # comment also promises convert_alpha() preserves any per-pixel alpha the
    # file already carries, which is what lets a sprite's transparent
    # background show whatever was drawn underneath it. A conversion that adds
    # an alpha channel but discards the file's own -- e.g.
    # convert().convert_alpha() -- would satisfy the SRCALPHA check above
    # while painting those pixels opaque.
    graphik = _make_graphik()
    display = graphik.getGameDisplay()
    display.fill(Graphik.blue)

    # Left pixel opaque red, right pixel fully transparent. A 32-bit BMP keeps
    # the alpha channel without needing SDL_image, like _write_solid_image.
    sprite = pygame.Surface((2, 1), pygame.SRCALPHA)
    sprite.fill((0, 0, 0, 0))
    sprite.set_at((0, 0), (255, 0, 0, 255))
    image_path = tmp_path / "sprite.bmp"
    pygame.image.save(sprite, str(image_path))

    graphik.drawImage(str(image_path), 0, 0, 2, 1)

    assert _rgb(display, (0, 0)) == (255, 0, 0)
    assert _rgb(display, (1, 0)) == Graphik.blue


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


def test_draw_rectangle_fills_exactly_the_requested_region():
    # drawButton's hit test is written against these bounds -- xpos through
    # xpos + width - 1 on both axes -- so pin them on the fill itself, or the
    # two can drift apart and leave the button's edges dead again.
    graphik = _make_graphik()
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)

    graphik.drawRectangle(2, 2, 5, 5, Graphik.red)

    # Every edge of the 5x5 region at (2,2)-(6,6) is painted...
    assert _rgb(display, (2, 2)) == Graphik.red
    assert _rgb(display, (6, 2)) == Graphik.red
    assert _rgb(display, (2, 6)) == Graphik.red
    assert _rgb(display, (6, 6)) == Graphik.red
    # ...and the first coordinate past each far edge is not.
    assert _rgb(display, (7, 4)) == Graphik.black
    assert _rgb(display, (4, 7)) == Graphik.black
    assert _rgb(display, (1, 4)) == Graphik.black
    assert _rgb(display, (4, 1)) == Graphik.black


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


def test_draw_text_renders_in_the_requested_color():
    # The `color` argument is what the glyphs are painted with. Rendering is
    # antialiased, so edge pixels are blends of the text color and the
    # background -- but on a black background a red glyph can only ever
    # produce shades of red, and its stems (several pixels wide at this size)
    # contain fully-covered pixels that match the color exactly.
    graphik = _make_graphik((100, 100))
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)

    graphik.drawText("W", 50, 50, 40, Graphik.red)

    width, height = display.get_size()
    inked = [
        _rgb(display, (x, y))
        for x in range(width)
        for y in range(height)
        if _rgb(display, (x, y)) != Graphik.black
    ]
    assert inked, "drawText left the surface untouched"
    assert Graphik.red in inked
    # No pixel picked up a green or blue component the requested color lacks.
    assert all(g == 0 and b == 0 for _, g, b in inked)


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


def test_draw_text_keeps_cached_font_across_a_display_resize(monkeypatch):
    # The session check compares display surface *objects*, and set_mode returns
    # the same object when only the size changes. That is what stops a resizable
    # window from discarding the font cache on every resize event, so it needs a
    # test of its own -- the invalidation tests above pass either way.
    graphik = _make_graphik((20, 20))
    graphik.drawText("A", 5, 5, 12, Graphik.white)

    resized = pygame.display.set_mode((30, 30))
    assert resized is graphik.getGameDisplay(), "resize returned a new surface"

    constructed = _count_font_constructions(monkeypatch)
    graphik.drawText("A", 5, 5, 12, Graphik.white)

    assert constructed == []


def test_caches_belong_to_the_instance_not_the_class(monkeypatch, tmp_path):
    # Both caches are built in __init__, so they are per-instance state. Moving
    # either to a class attribute would share it across every Graphik and, for
    # the font cache, defeat the display-session invalidation in _getFont:
    # one instance's entries would survive into another instance bound to a
    # display that instance never checked against. Pin the isolation on the
    # observable work instead of on the private dictionaries.
    pygame.display.init()
    display = pygame.display.set_mode((20, 20))
    first = Graphik(display)
    second = Graphik(display)

    imagePath = tmp_path / "red.bmp"
    _write_solid_image(imagePath, (255, 0, 0))

    constructed = _count_font_constructions(monkeypatch)
    loaded = _count_image_loads(monkeypatch)

    # Warm the first instance's caches at two font sizes and one asset...
    first.drawText("A", 5, 5, 12, Graphik.white)
    first.drawText("A", 5, 5, 14, Graphik.white)
    first.drawImage(str(imagePath), 0, 0, 10, 10)

    # ...then let the second instance draw one of those sizes and that asset...
    second.drawText("A", 5, 5, 12, Graphik.white)
    second.drawImage(str(imagePath), 0, 0, 10, 10)

    # ...and ask the first instance for the size the second never touched.
    first.drawText("A", 5, 5, 14, Graphik.white)

    # The interleaving is what makes this sensitive to both ways the caches
    # could stop being per-instance. If the dictionaries moved to the class
    # along with _fontDisplay, the second instance would be handed the first's
    # size-12 font and build nothing. If only the dictionaries moved, the
    # second instance's first drawText would instead clear the shared cache --
    # discarding the first's size-14 entry, which the final call would rebuild.
    # Either way the sequence below stops matching.
    assert [args[1] for args in constructed] == [12, 14, 12]
    assert len(loaded) == 2


def _draw_rectangle(graphik, imagePath):
    graphik.drawRectangle(2, 2, 10, 10, Graphik.red)


def _draw_text(graphik, imagePath):
    graphik.drawText("W", 10, 10, 16, Graphik.white)


def _draw_button(graphik, imagePath):
    graphik.drawButton(2, 2, 16, 16, Graphik.blue, Graphik.white, 10, "Go", lambda: None)


def _draw_image(graphik, imagePath):
    graphik.drawImage(str(imagePath), 2, 2, 10, 10)


@pytest.mark.parametrize(
    "draw",
    [
        pytest.param(_draw_rectangle, id="drawRectangle"),
        pytest.param(_draw_text, id="drawText"),
        pytest.param(_draw_button, id="drawButton"),
        pytest.param(_draw_image, id="drawImage"),
    ],
)
def test_draw_methods_render_to_the_bound_surface_not_the_display(draw, tmp_path):
    # The class docstring promises every draw method renders to the surface the
    # instance was constructed with. Every other test binds Graphik to the
    # display itself, so none of them pins that: a draw method that wrote to
    # pygame.display.get_surface() instead would only trip the font-session
    # test above, and only incidentally. Bind an off-screen surface here and
    # require the display to stay untouched.
    pygame.display.init()
    pygame.font.init()
    display = pygame.display.set_mode((20, 20))
    display.fill(Graphik.black)
    target = pygame.Surface((20, 20))
    target.fill(Graphik.black)
    graphik = Graphik(target)

    imagePath = tmp_path / "green.bmp"
    _write_solid_image(imagePath, (0, 255, 0))

    draw(graphik, imagePath)

    pixels = [(x, y) for x in range(20) for y in range(20)]
    assert any(_rgb(target, p) != Graphik.black for p in pixels), "nothing was drawn to the bound surface"
    assert all(_rgb(display, p) == Graphik.black for p in pixels), "the display was drawn to"


def test_draw_button_draws_box_with_given_color():
    graphik = _make_graphik((40, 40))
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)

    graphik.drawButton(10, 10, 20, 20, Graphik.blue, Graphik.white, 10, "Go", lambda: None)

    # A corner of the box, away from the centered text, keeps the box color.
    assert _rgb(display, (11, 11)) == Graphik.blue


def _button_label_ink(display, colorBox, background=Graphik.black):
    # Pixels that are neither the untouched background nor the box fill are
    # the rendered label (its antialiased edges included).
    width, height = display.get_size()
    return [
        (x, y)
        for x in range(width)
        for y in range(height)
        if _rgb(display, (x, y)) not in (background, colorBox)
    ]


def test_draw_button_centers_the_label_within_the_box():
    # Pins the documented "rectangle and centered text": the label is anchored
    # on the box's midpoint, so it sits inside the box and straddles that
    # point rather than hanging off the top-left corner the box is drawn from.
    graphik = _make_graphik((200, 100))
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)

    xpos, ypos, width, height = 20, 10, 160, 80
    graphik.drawButton(xpos, ypos, width, height, Graphik.blue, Graphik.white, 30, "WWWW", lambda: None)

    ink = _button_label_ink(display, Graphik.blue)
    assert ink, "drawButton drew no label"
    xs = [x for x, _ in ink]
    ys = [y for _, y in ink]
    centerX, centerY = xpos + width // 2, ypos + height // 2

    # Entirely within the drawn box...
    assert xpos <= min(xs) and max(xs) < xpos + width
    assert ypos <= min(ys) and max(ys) < ypos + height
    # ...straddling the box midpoint on both axes...
    assert min(xs) < centerX < max(xs)
    assert min(ys) < centerY < max(ys)
    # ...and horizontally centered on it. As in the drawText centering test,
    # only the horizontal midpoint is asserted tightly, because glyph ink is
    # vertically asymmetric within the rect that is actually centered.
    assert abs((min(xs) + max(xs)) / 2 - centerX) <= 1


def test_draw_button_renders_the_label_in_color_text():
    # colorBox and colorText are separate arguments, and the label must be
    # painted with the second one -- swapping them, or passing colorBox to
    # drawText, would leave the label invisible against its own box.
    graphik = _make_graphik((200, 100))
    display = graphik.getGameDisplay()
    display.fill(Graphik.black)

    graphik.drawButton(20, 10, 160, 80, Graphik.blue, Graphik.red, 30, "WWWW", lambda: None)

    ink = _button_label_ink(display, Graphik.blue)
    assert ink, "drawButton drew no label"
    # Fully-covered glyph pixels carry the exact text color; the rest are
    # antialiased blends of it with the blue box, never any other hue.
    colors = {_rgb(display, p) for p in ink}
    assert Graphik.red in colors
    assert all(g == 0 for _, g, _ in colors)


@pytest.mark.parametrize(
    "mouse_pos, mouse_pressed, expect_call",
    [
        pytest.param((15, 15), (1, 0, 0), True, id="clicked_inside"),
        pytest.param((0, 0), (1, 0, 0), False, id="outside_box"),
        pytest.param((15, 15), (0, 0, 0), False, id="not_pressed"),
        # The docstring promises button 1 specifically, so a press of only the
        # middle and/or right buttons must not fire the callback -- a hit test
        # written against any() rather than click[0] would pass every other case.
        pytest.param((15, 15), (0, 1, 0), False, id="middle_button_only"),
        pytest.param((15, 15), (0, 0, 1), False, id="right_button_only"),
        # ...while button 1 held together with the others still counts.
        pytest.param((15, 15), (1, 1, 1), True, id="all_buttons"),
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
