"""Phones: the board framed for a portrait screen (fitCamera, the views'
insets) and the on-screen keys (touchkeys.TouchKeys), drawn alike in 2D
and 3D. No GPU; pygame only for its events and a Graphik on a surface."""

import sys
import types

import pygame
import pytest

from preponderous.graphik import Graphik
from preponderous.graphik.grid3d import (
    MIN_TARGET,
    MORE,
    GridBoard,
    TouchKey,
    TouchKeys,
    fitCamera,
    projectToScreen,
)
from preponderous.graphik.grid3d import board as boardModule
from preponderous.graphik.grid3d import web
from preponderous.graphik.grid3d.view import ViewGeometry

SIZES = [(390, 844), (844, 390), (800, 600), (1280, 800), (900, 700), (430, 932), (600, 800)]


def boardBox(camera, columns, rows, width, height):
    """The board's (frame included) bounding box on screen: (left, top,
    right, bottom) in pixels."""
    points = []
    for x in (-columns / 2.0 - 0.35, columns / 2.0 + 0.35):
        for z in (-rows / 2.0 - 0.35, rows / 2.0 + 0.35):
            for y in (-0.18, 0.3):
                points.append(projectToScreen(camera, (x, y, z), width, height))
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def share(box, width, height):
    """The share of the screen the box covers (what is off screen doesn't
    count)."""
    left, top, right, bottom = box
    left, top, right, bottom = max(left, 0), max(top, 0), min(right, width), min(bottom, height)
    return (right - left) * (bottom - top) / float(width * height)


# -- framing


def test_landscape_and_desktop_framing_is_unchanged():
    # graphik 0.5.1's formula, for every landscape or square window
    for columns, rows in [(4, 3), (5, 5), (16, 16), (64, 64), (20, 8)]:
        for width, height in [(844, 390), (800, 600), (1280, 800), (900, 700), (700, 700)]:
            aspect = width / float(height)
            size = (max(columns, rows) + 1.0) * max(1.0, 1.0 / max(aspect, 0.5))
            distance = 0.86 * size + 0.9
            camera = fitCamera(columns, rows, aspect)
            assert camera.eye == (0.0, 1.35 * distance, 0.95 * distance)
            assert camera.target == (0.0, -0.3, -0.04 * size)


@pytest.mark.parametrize("columns, rows", [(3, 3), (5, 5), (4, 3), (16, 16), (64, 64), (20, 8), (8, 20)])
@pytest.mark.parametrize("width, height", SIZES)
def test_the_whole_board_is_on_screen_at_every_aspect(columns, rows, width, height):
    box = boardBox(fitCamera(columns, rows, width / float(height)), columns, rows, width, height)
    left, top, right, bottom = box
    assert left >= 0 and right <= width and top >= 0 and bottom <= height


@pytest.mark.parametrize("columns, rows", [(3, 3), (5, 5), (16, 16), (64, 64)])
def test_a_portrait_phone_fills_its_width_and_centres_the_board(columns, rows):
    width, height = 390, 844
    camera = fitCamera(columns, rows, width / float(height))
    left, top, right, bottom = boardBox(camera, columns, rows, width, height)
    assert right - left >= 0.9 * width  # the board fills the width
    # in the middle of the space below the default HUD room
    middle = (top + bottom) / 2.0
    space = (boardModule.DEFAULT_TOP * height, height - boardModule.DEFAULT_BOTTOM * height)
    # (fitCamera centres the board with a piece's height on it; this box has less)
    assert abs(middle - (space[0] + space[1]) / 2.0) < 8
    # it stands taller than 0.5.1's framing made it, and no lower
    old = boardModule._desktopCamera(columns, rows, width / float(height), 42.0)
    oldBox = boardBox(old, columns, rows, width, height)
    assert bottom - top > oldBox[3] - oldBox[1]
    # bigger on screen, unless 0.5.1's ran off the sides
    assert share((left, top, right, bottom), width, height) > share(oldBox, width, height) \
        or oldBox[0] < 0 or oldBox[2] > width


def test_a_portrait_camera_looks_down_more_steeply():
    portrait = fitCamera(5, 5, 390 / 844.0)
    desktop = fitCamera(5, 5, 900 / 700.0)

    def pitch(camera):
        import math

        dy = camera.eye[1] - camera.target[1]
        dz = camera.eye[2] - camera.target[2]
        return math.degrees(math.atan2(dy, dz))

    assert pitch(portrait) == pytest.approx(boardModule.PORTRAIT_PITCH, abs=0.01)
    assert pitch(desktop) == pytest.approx(boardModule.LANDSCAPE_PITCH, abs=0.5)


@pytest.mark.parametrize("width, height", SIZES)
def test_reserved_space_at_the_top_and_bottom_is_kept_clear(width, height):
    top, bottom = 0.12, 0.2
    camera = fitCamera(6, 6, width / float(height), top=top, bottom=bottom)
    left, boxTop, right, boxBottom = boardBox(camera, 6, 6, width, height)
    assert boxTop >= top * height - 1
    assert boxBottom <= height - bottom * height + 1
    assert left >= 0 and right <= width
    # and the board fills that space one way or the other
    room = (height * (1 - top - bottom), width)
    assert boxBottom - boxTop >= 0.9 * room[0] * (1 - 2 * boardModule.END_MARGIN) or \
        right - left >= 0.9 * room[1] * (1 - 2 * boardModule.SIDE_MARGIN)


def test_nearly_square_windows_blend_without_a_jump():
    def eye(aspect):
        return fitCamera(5, 5, aspect).eye

    square = eye(1.0)
    almost = eye(0.999)
    assert all(abs(a - b) < 0.2 for a, b in zip(square, almost))
    # and the blend reaches the portrait framing at PORTRAIT_ASPECT
    assert fitCamera(5, 5, boardModule.PORTRAIT_ASPECT) == boardModule._fittedCamera(
        5, 5, boardModule.PORTRAIT_ASPECT, 42.0, boardModule.PORTRAIT_PITCH,
        boardModule.DEFAULT_TOP, boardModule.DEFAULT_BOTTOM)


class Geometry(ViewGeometry):
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.board = GridBoard(5, 5)


def test_a_views_insets_reach_its_camera_and_picking():
    view = Geometry(390, 844)
    plain = view.camera()
    assert view.setInsets(top=100, bottom=180) is True
    assert view.setInsets(top=100, bottom=180) is False
    assert view.insetFractions() == (100 / 844.0, 180 / 844.0)
    framed = view.camera()
    assert framed != plain
    assert framed == fitCamera(5, 5, 390 / 844.0, top=100 / 844.0, bottom=180 / 844.0)
    # a press on a tile's middle picks it, with the insets' camera
    x, y = view.cellScreenPosition(2, 4)
    assert view.pickCell(x, y) == (2, 4)
    assert view.setInsets() is True and view.camera() == plain


def test_the_web_view_sends_the_new_camera_when_its_insets_change():
    relay = web.RecordingRelay()
    view = web.Grid3DWebView.open(390, 844, relay=relay)
    view.setBoard(GridBoard(5, 5))
    sent = len(relay.messages)
    view.setInsets(top=90, bottom=170)
    assert len(relay.messages) == sent + 1
    kind, body = web.decode(relay.messages[-1])
    assert kind == web.VIEW
    camera = fitCamera(5, 5, 390 / 844.0, top=90 / 844.0, bottom=170 / 844.0)
    assert body["eye"] == pytest.approx(camera.eye, abs=1e-4)
    view.setInsets(top=90, bottom=170)
    assert len(relay.messages) == sent + 1  # nothing changed, nothing sent
    assert view.scene().camera == camera


# -- the keys


OPHIDIAN = [("Pause", "space"), ("Shop", "p"), ("Retry", "r"), ("Skin", "c"), ("Speed", "l")]
MANY = [("K%d" % i, "abcdefghijklmnopqrstuvwxyz"[i]) for i in range(19)]


def test_a_few_keys_make_one_row_of_equal_buttons_at_the_bottom():
    keys = TouchKeys(OPHIDIAN)
    slots = keys.layout(390, 844)
    assert [s.label for s in slots] == ["Pause", "Shop", "Retry", "Skin", "Speed"]
    assert len({s.y for s in slots}) == 1 and len({round(s.width, 6) for s in slots}) == 1
    band = keys.bandHeight(390, 844)
    assert band == MIN_TARGET + 2 * 8
    for slot in slots:
        assert slot.width >= MIN_TARGET and slot.height >= MIN_TARGET
        assert slot.y >= 844 - band and slot.y + slot.height <= 844
        assert slot.x >= 0 and slot.x + slot.width <= 390


@pytest.mark.parametrize("width, height", SIZES)
def test_buttons_never_overlap_and_stay_on_screen(width, height):
    keys = TouchKeys(MANY)
    slots = keys.layout(width, height)
    for a in slots:
        assert a.width >= MIN_TARGET and a.height >= MIN_TARGET
        assert a.x >= 0 and a.x + a.width <= width and a.y + a.height <= height
        for b in slots:
            if a is not b:
                assert not (a.x < b.x + b.width and b.x < a.x + a.width
                            and a.y < b.y + b.height and b.y < a.y + a.height)


def test_too_many_keys_page_through_more():
    keys = TouchKeys(MANY)
    # a landscape phone: one row, the last button More
    seen = []
    for page in range(5):
        slots = keys.layout(844, 390)
        assert len({s.y for s in slots}) == 1
        assert slots[-1].key is None
        seen += [s.key.key for s in slots if s.key is not None]
        assert keys.press((slots[-1].x + 1, slots[-1].y + 1), 844, 390) == MORE
    assert set(seen) == {key for _, key in MANY}
    assert keys.layout(844, 390)[-1].label in ("More", "Back")
    # portrait: up to three rows
    keys.page = 0
    slots = keys.layout(390, 844)
    assert len({s.y for s in slots}) <= 3


def test_the_last_page_says_back():
    keys = TouchKeys(MANY)
    labels = []
    for _ in range(10):
        slots = keys.layout(844, 390)
        labels.append(slots[-1].label)
        keys.press((slots[-1].x + 1, slots[-1].y + 1), 844, 390)
        if keys.page == 0:
            break
    assert labels[-1] == "Back" and set(labels[:-1]) == {"More"}


def test_new_keys_start_on_the_first_page():
    keys = TouchKeys(MANY)
    keys.page = 2
    keys.setKeys(MANY)
    assert keys.page == 2  # the same keys
    keys.setKeys(OPHIDIAN)
    assert keys.page == 0


def test_a_press_on_a_key_posts_the_keyboards_keydown_and_keyup():
    pygame.display.init()
    try:
        pygame.event.clear()
        keys = TouchKeys(OPHIDIAN)
        slot = keys.layout(390, 844)[0]  # Pause
        assert keys.press((slot.x + 5, slot.y + 5), 390, 844, pygame) == TouchKey("Pause", "space")
        down, up = pygame.event.get([pygame.KEYDOWN, pygame.KEYUP])
        assert down.type == pygame.KEYDOWN and down.key == pygame.K_SPACE and down.unicode == " "
        assert up.type == pygame.KEYUP and up.key == pygame.K_SPACE
        assert down.touchKey and up.touchKey
        # off the bar: the press is the game's
        assert keys.press((195, 300), 390, 844, pygame) is None
        assert pygame.event.get([pygame.KEYDOWN]) == []
    finally:
        pygame.display.quit()


@pytest.mark.parametrize("name, code, text", [
    ("p", "K_p", "p"), ("[", "K_LEFTBRACKET", "["), ("]", "K_RIGHTBRACKET", "]"),
    ("up", "K_UP", ""), ("down", "K_DOWN", ""), ("return", "K_RETURN", "\r"),
    ("escape", "K_ESCAPE", "\x1b"), ("space", "K_SPACE", " "),
])
def test_key_events_name_pygames_keys(name, code, text):
    pygame.display.init()
    try:
        down, up = TouchKeys.keyEvents(TouchKey("x", name), pygame)
    finally:
        pygame.display.quit()
    assert down.key == getattr(pygame, code) == up.key
    assert down.unicode == text


def test_the_2d_layout_is_the_3d_layout_scaled():
    keys = TouchKeys(OPHIDIAN)
    css = keys.layout(390, 844)
    scale = 0.5  # a canvas drawn at half size: twice the pixels
    canvas = keys.layout(780, 1688, scale)
    assert [s.label for s in css] == [s.label for s in canvas]
    for a, b in zip(css, canvas):
        assert (b.x * scale, b.y * scale, b.width * scale, b.height * scale) == pytest.approx(
            (a.x, a.y, a.width, a.height))
    assert keys.bandHeight(780, 1688, scale) == keys.bandHeight(390, 844) / scale
    # the same hit test, in each surface's pixels
    a = css[2]
    assert keys.slotAt((a.x + 1, a.y + 1), 390, 844).label == "Retry"
    assert keys.slotAt(((a.x + 1) / scale, (a.y + 1) / scale), 780, 1688, scale).label == "Retry"


def test_below_fits_a_2d_board_and_its_bar_to_a_phone():
    keys = TouchKeys(OPHIDIAN)
    band, scale = keys.below(500, 500, 390, 844)
    assert scale == pytest.approx(390 / 500.0)
    assert band * scale >= MIN_TARGET + 16
    # on a landscape phone the canvas is fitted by its height, band included
    band, scale = keys.below(500, 500, 844, 390)
    assert (500 + band) * scale <= 390 + 1e-6
    for slot in keys.layout(500, 500 + band, scale, portrait=False):
        assert slot.height * scale >= MIN_TARGET - 1e-6
        assert slot.y >= 500


def test_the_2d_bar_is_drawn_with_graphik():
    surface = pygame.Surface((500, 600))
    surface.fill((255, 255, 255))
    keys = TouchKeys(OPHIDIAN)
    slots = keys.draw(Graphik(surface), 500, 600, scale=390 / 500.0)
    band = keys.bandHeight(500, 600, 390 / 500.0)
    assert slots and surface.get_at((2, 599))[:3] == keys.barColor
    slot = slots[0]
    assert surface.get_at((int(slot.x) + 2, int(slot.y) + 2))[:3] == keys.color
    # nothing above the band is touched
    assert surface.get_at((250, int(600 - band) - 2))[:3] == (255, 255, 255)


def test_the_3d_bar_is_the_same_buttons_as_screen_panels_and_labels():
    keys = TouchKeys(OPHIDIAN)
    labels, panels = keys.overlay(390, 844)
    slots = keys.layout(390, 844)
    band = keys.bandHeight(390, 844)
    assert (panels[0].x, panels[0].y, panels[0].width, panels[0].height) == (0, 844 - band, 390, band)
    assert [(p.x, p.y, p.width, p.height) for p in panels[1:]] == [
        (s.x, s.y, s.width, s.height) for s in slots]
    assert [l.text for l in labels] == [s.label for s in slots]
    # the buttons' hit test is the slots'
    for button, slot in zip(keys.buttons(390, 844), slots):
        assert button.rect() == (slot.x, slot.y, slot.width, slot.height)


def test_no_keys_no_bar():
    keys = TouchKeys()
    assert keys.layout(390, 844) == [] and keys.bandHeight(390, 844) == 0
    assert keys.overlay(390, 844) == ([], [])
    assert keys.press((10, 830), 390, 844) is None


# -- the page says whether it is a touch screen


def pageWith(monkeypatch, toggle):
    monkeypatch.setattr(sys, "platform", "emscripten")
    fake = types.ModuleType("platform")
    fake.window = types.SimpleNamespace(Graphik3D=toggle)
    monkeypatch.setitem(sys.modules, "platform", fake)


def test_the_page_says_whether_it_is_a_touch_screen(monkeypatch):
    class Toggle:
        value = "1"

        def touch(self):
            return self.value

    toggle = Toggle()
    pageWith(monkeypatch, toggle)
    assert web.touchScreen() is True
    toggle.value = 0
    assert web.touchScreen() is False


def test_an_older_template_is_no_touch_screen(monkeypatch):
    pageWith(monkeypatch, types.SimpleNamespace())
    assert web.touchScreen() is False


def test_outside_a_browser_touch_is_off_unless_asked_for(monkeypatch):
    monkeypatch.delenv("GRAPHIK_TOUCH", raising=False)
    assert web.touchScreen() is False
    monkeypatch.setenv("GRAPHIK_TOUCH", "1")
    assert web.touchScreen() is True


def test_the_template_offers_touch():
    with open(web.templatePath(), encoding="utf-8") as handle:
        page = handle.read()
    assert "touch: touchScreen" in page
    assert '"(pointer: coarse)"' in page and '"touchstart"' in page
    assert 'get("touch")' in page
