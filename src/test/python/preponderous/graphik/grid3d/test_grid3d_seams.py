"""Characterization tests for grid3d's seams: where the desktop and browser
views touch Strata, pygbag's platform.window, pygame, the clock, the
environment and the temporary folder.

They pin what the code does today (graphik 0.5.3), before a ports-and-adapters
refactor moves it, so a behaviour change during the move shows up here. They
use no GPU, no browser and no network.
"""

import base64
import json
import os
import sys
import tempfile
import types

import pygame
import pytest

from preponderous.graphik.grid3d import (
    CUBE,
    Camera,
    GridBoard,
    Grid3DView,
    Label,
    Light,
    Piece,
    PieceStyle,
    Scene,
    SceneLimitError,
    Shape,
    Theme,
    Unavailable,
)
from preponderous.graphik.grid3d import view as viewModule
from preponderous.graphik.grid3d import web
from preponderous.graphik.grid3d.view import ViewGeometry

from test_grid3d_view import fakeStrata

# pygame.key.key_code names keys without pygame.init(); it warns that it might not
pytestmark = pytest.mark.filterwarnings("ignore:pygame.init\\(\\) has not been called")


def theme():
    return Theme(pieces={
        "pawn": PieceStyle(CUBE, (0.9, 0.9, 0.9)),
        "lamp": PieceStyle(CUBE, (0.9, 0.9, 0.2), glow=(2.0, 1.0)),
    })


def inBrowser(monkeypatch, **window):
    monkeypatch.setattr(sys, "platform", "emscripten")
    fake = types.ModuleType("platform")
    fake.window = types.SimpleNamespace(**window)
    monkeypatch.setitem(sys.modules, "platform", fake)


# -- PlatformRelay: pygbag's bridge passes strings, so the transport marshals


class PageRelay:
    """window.StrataGridRelay as pygbag shows it: JS values, strings in."""

    def __init__(self, state="ready", motion=0, events="[]", rc=0):
        self.calls = []
        self._state, self._motion, self._events, self._rc = state, motion, events, rc

    def request(self, options):
        self.calls.append(("request", options))
        return self._state

    def state(self):
        self.calls.append(("state",))
        return self._state

    def send(self, b64):
        self.calls.append(("send", b64))
        return self._rc

    def poll(self):
        self.calls.append(("poll",))
        return self._events

    def reducedMotion(self):
        self.calls.append(("reducedMotion",))
        return self._motion

    def close(self):
        self.calls.append(("close",))


def test_platform_relay_sends_options_as_json_and_messages_as_base64():
    page = PageRelay()
    relay = web.PlatformRelay(page)
    assert relay.js is page
    assert relay.request({"canvas": "relay", "maxBytes": 5}) == "ready"
    (name, options), = page.calls
    assert name == "request" and isinstance(options, str)
    assert json.loads(options) == {"canvas": "relay", "maxBytes": 5}
    assert relay.send(b"G3\x01\x00\x03\x00\x00\x00") == 0
    _, b64 = page.calls[-1]
    assert b64 == base64.b64encode(b"G3\x01\x00\x03\x00\x00\x00").decode("ascii")
    relay.close()
    assert page.calls[-1] == ("close",)


@pytest.mark.parametrize("raw, expected", [(0, False), (1, True), ("0", False), ("1", True)])
def test_platform_relay_reads_reduced_motion_as_an_int(raw, expected):
    assert web.PlatformRelay(PageRelay(motion=raw)).reducedMotion() is expected


def test_platform_relay_reads_state_as_a_string_and_events_as_json():
    page = PageRelay(state=7, events='[{"type": 8, "width": 3, "height": 4}]', rc="-6")
    relay = web.PlatformRelay(page)
    assert relay.state() == "7"
    assert relay.poll() == [{"type": 8, "width": 3, "height": 4}]
    assert relay.send(b"x") == -6  # int() of what the page returned


def test_platform_relay_without_a_page_says_why_in_words(monkeypatch):
    # outside a browser there is no page object either
    with pytest.raises(Unavailable) as outside:
        web.PlatformRelay()
    assert str(outside.value) == (
        "this page has no 3D view (grid-relay.js isn't loaded; on graphik's "
        "template it loads once the 3D toggle is on, when wants3D() turns true)")
    inBrowser(monkeypatch)
    with pytest.raises(Unavailable, match="grid-relay.js isn't loaded"):
        web.PlatformRelay()


def test_page_object_is_none_outside_a_browser_even_with_a_platform_module(monkeypatch):
    fake = types.ModuleType("platform")
    fake.window = types.SimpleNamespace(Graphik3D=object())
    monkeypatch.setitem(sys.modules, "platform", fake)
    monkeypatch.setattr(sys, "platform", "linux")
    assert web.pageObject("Graphik3D") is None
    monkeypatch.setattr(sys, "platform", "emscripten")
    assert web.pageObject("Graphik3D") is fake.window.Graphik3D
    assert web.pageObject("Nothing") is None


# -- Grid3DView.open in a browser


def test_open_in_a_browser_lets_the_page_decide_reduced_motion_unless_the_game_asks(monkeypatch):
    page = PageRelay(motion=1)
    inBrowser(monkeypatch, StrataGridRelay=page)
    # reducedMotion=False (the default) becomes None: the page decides
    assert Grid3DView.open(320, 200).reducedMotion is True
    page._motion = 0
    assert Grid3DView.open(320, 200, reducedMotion=True).reducedMotion is True
    assert Grid3DView.open(320, 200).reducedMotion is False


def test_open_in_a_browser_passes_the_clock_and_title(monkeypatch):
    page = PageRelay()
    inBrowser(monkeypatch, StrataGridRelay=page)
    clock = lambda: 42.0  # noqa: E731
    view = Grid3DView.open(320, 200, "Title", clock=clock)
    assert view.clock is clock
    _, options = page.calls[0]
    assert json.loads(options) == {"canvas": "relay", "maxBytes": 4000000, "title": "Title"}


def test_a_page_that_failed_to_load_is_unavailable_with_its_reason(monkeypatch):
    inBrowser(monkeypatch, StrataGridRelay=PageRelay(state="failed:no WebGL 2"))
    with pytest.raises(Unavailable) as error:
        Grid3DView.open(320, 200)
    assert str(error.value) == "no WebGL 2"


# -- Grid3DView.open on the desktop: environment defaults


def test_headless_on_linux_defaults_the_sdl_driver_to_dummy_but_keeps_a_set_one(monkeypatch):
    strata = fakeStrata()
    monkeypatch.setitem(sys.modules, "strata", strata)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    monkeypatch.delenv("SDL_VIDEODRIVER", raising=False)
    Grid3DView.open(320, 200, headless=True)
    assert os.environ["SDL_VIDEODRIVER"] == "dummy"
    monkeypatch.setenv("SDL_VIDEODRIVER", "x11")
    Grid3DView.open(320, 200, headless=True)
    assert os.environ["SDL_VIDEODRIVER"] == "x11"


def test_a_window_leaves_the_sdl_driver_alone(monkeypatch):
    monkeypatch.setitem(sys.modules, "strata", fakeStrata())
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    monkeypatch.delenv("SDL_VIDEODRIVER", raising=False)
    Grid3DView.open(320, 200)
    assert "SDL_VIDEODRIVER" not in os.environ


def test_loading_strata_defaults_gallium_to_llvmpipe_but_keeps_a_set_one(monkeypatch):
    monkeypatch.setitem(sys.modules, "strata", fakeStrata())
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    monkeypatch.delenv("GALLIUM_DRIVER", raising=False)
    viewModule.loadStrata(platform="linux")
    assert os.environ["GALLIUM_DRIVER"] == "llvmpipe"
    monkeypatch.setenv("GALLIUM_DRIVER", "zink")
    viewModule.loadStrata(platform="win32")
    assert os.environ["GALLIUM_DRIVER"] == "zink"


def test_an_unsupported_system_is_refused_before_the_environment_is_touched(monkeypatch):
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    monkeypatch.delenv("GALLIUM_DRIVER", raising=False)
    with pytest.raises(Unavailable) as error:
        viewModule.loadStrata(platform="darwin")
    assert str(error.value) == "Strata has no library for this system (darwin)"
    assert "GALLIUM_DRIVER" not in os.environ


def test_the_desktop_camera_uses_the_shared_projection_and_the_sun(monkeypatch):
    strata = fakeStrata()
    monkeypatch.setitem(sys.modules, "strata", strata)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    view = Grid3DView.open(300, 200)
    view.drawScene(Scene(camera=Camera((0, 5, 5), (0, 0, 0), fovDegrees=50.0)))
    (camera,), _ = view.engine.call("set_camera")
    assert camera[3] == {"fov_y_degrees": 50.0, "aspect": 1.5,
                         "near_plane": web.NEAR_PLANE, "far_plane": web.FAR_PLANE}
    assert view.engine.call("set_sun_direction") == ((web.SUN_DIRECTION,), {})
    assert view.strata is strata  # games read event types from view.strata


# -- the clock


def test_both_views_read_the_clock_once_per_set_board_and_set_pieces(monkeypatch):
    monkeypatch.setitem(sys.modules, "strata", fakeStrata())
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    reads = []

    def clock():
        reads.append(1)
        return 10.0

    desktop = Grid3DView.open(300, 200, clock=clock)
    browser = web.Grid3DWebView(web.RecordingRelay(), 300, 200, clock=clock)
    for view in (desktop, browser):
        del reads[:]
        view.setBoard(GridBoard(4, 4, theme()))
        view.setPieces([Piece(1, 0, 0, "pawn")], 0.1)
        assert len(reads) == 2
        view.scene(now=11.0)  # an explicit time reads no clock
        assert len(reads) == 2
        view.scene()
        assert len(reads) == 3


# -- Grid3DWebView: what is sent, and when


def test_the_web_view_counts_what_it_sends_and_keeps_the_last_of_each_kind():
    relay = web.RecordingRelay()
    view = web.Grid3DWebView(relay, 300, 200)
    assert view.sent == 0 and view.lastSent == {}
    view.setBoard(GridBoard(3, 3, theme()))
    assert view.sent == 3
    assert set(view.lastSent) == {web.BOARD, web.VIEW, web.PIECES}
    assert view.lastSent[web.VIEW] == relay.messages[1]


def test_the_web_view_sends_nothing_for_a_frame_or_a_resize_before_its_board():
    relay = web.RecordingRelay()
    view = web.Grid3DWebView(relay, 300, 200)
    view.frame()
    view.resize(400, 300)
    assert (view.width, view.height) == (400, 300)
    assert view.setInsets(top=10) is True
    assert relay.messages == []


def test_a_web_scene_without_a_camera_sends_no_view():
    relay = web.RecordingRelay()
    view = web.Grid3DWebView(relay, 300, 200)
    view.drawScene(Scene(shapes=[Shape(CUBE, (0, 0, 0), (1, 1, 1), (1, 1, 1, 1))]))
    assert [m[4] for m in relay.messages] == [web.BOARD, web.PIECES, web.HUD]


def test_a_web_scene_over_the_limits_sends_nothing():
    relay = web.RecordingRelay()
    view = web.Grid3DWebView(relay, 300, 200)
    with pytest.raises(SceneLimitError):
        view.drawScene(Scene(shapes=[Shape(99, (0, 0, 0), (1, 1, 1), (1, 1, 1, 1))]))
    assert relay.messages == []


def test_too_many_lights_on_a_web_board_or_its_pieces_are_refused_before_sending():
    relay = web.RecordingRelay()
    view = web.Grid3DWebView(relay, 300, 200)
    shadowed = [Light((0, 1, 0), (1, 1, 1), 2.0, 1.0, castShadows=True)] * 5
    with pytest.raises(SceneLimitError, match="shadow-casting"):
        view.setBoard(GridBoard(3, 3, theme()), lights=shadowed)
    assert relay.messages == []
    view.setBoard(GridBoard(9, 9, theme()), lights=[Light((0, 1, 0), (1, 1, 1), 2.0, 1.0)] * 30)
    sent = len(relay.messages)
    lamps = [Piece(i, i, 0, "lamp") for i in range(3)]  # 30 + 3 glows > 32
    with pytest.raises(SceneLimitError, match="point lights"):
        view.setPieces(lamps)
    assert len(relay.messages) == sent and view.pieces == []


def test_a_web_tick_sends_the_animators_tick_not_the_games():
    relay = web.RecordingRelay()
    view = web.Grid3DWebView(relay, 300, 200, clock=lambda: 1.0)
    view.setBoard(GridBoard(3, 3, theme()))
    view.setPieces([Piece(1, 0, 0, "pawn")], tickSeconds=-1.0)
    _, body = web.decode(relay.messages[-1])
    assert body["tickSeconds"] == view.animator.tickSeconds


def test_the_web_view_has_no_screenshots_and_close_reaches_the_page():
    relay = web.RecordingRelay()
    view = web.Grid3DWebView(relay, 300, 200)
    with pytest.raises(Unavailable) as error:
        view.savePng("out.png")
    assert str(error.value) == "screenshots of the web view are taken by the page (canvas.toBlob)"
    view.close()
    assert relay.closed
    view.close()  # unlike the desktop view, every close reaches the page


def test_a_loading_page_has_no_failure_yet():
    view = web.Grid3DWebView(web.RecordingRelay(state="loading"), 300, 200)
    assert view.ready is False and view.failure() is None
    view.relay.status = "failed:lost the context"
    assert view.ready is False and view.failure() == "lost the context"


def test_the_two_views_poll_different_event_shapes(monkeypatch):
    # desktop: the binding's own events, as they come; web: Event objects
    monkeypatch.setitem(sys.modules, "strata", fakeStrata())
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    desktop = Grid3DView.open(300, 200)
    raw = object()
    desktop.engine.events = [raw]
    assert desktop.pollEvents() == [raw]
    relay = web.RecordingRelay()
    browser = web.Grid3DWebView(relay, 300, 200)
    relay.events = [{"type": web.EVENT_QUIT}]
    (event,) = browser.pollEvents()
    assert isinstance(event, web.Event) and event.type == browser.EVENT_QUIT == web.EVENT_QUIT
    assert browser.strata is web.EVENTS and browser.isWindow is True


# -- ViewGeometry


def test_inset_fractions_are_none_for_a_window_of_no_height():
    geometry = ViewGeometry()
    geometry.width, geometry.height, geometry.board = 300, 0, None
    geometry.setInsets(top=10, bottom=20)
    assert geometry.insetFractions() == (None, None)
    geometry.height = 200
    assert geometry.insetFractions() == (0.05, 0.1)
    assert geometry.setInsets(bottom=20) is True and geometry.insets == (0, 20)


# -- page helpers: the environment and the temporary folder


def test_touch_outside_a_browser_takes_only_exactly_1(monkeypatch):
    for value in ("true", "yes", "0", " 1", ""):
        monkeypatch.setenv("GRAPHIK_TOUCH", value)
        assert web.touchScreen() is False


def test_in_a_browser_the_environment_never_turns_touch_on(monkeypatch):
    monkeypatch.setenv("GRAPHIK_TOUCH", "1")
    inBrowser(monkeypatch)  # a page without the button
    assert web.touchScreen() is False


def test_a_toggle_that_says_no_to_wanted_and_set_takes_its_reason_as_text(monkeypatch):
    calls = []

    class Toggle:
        def wanted(self):
            return "0"

        def set(self, value, reason):
            calls.append((value, reason))

    inBrowser(monkeypatch, Graphik3D=Toggle())
    assert web.wants3D() is False
    web.set3D(True)
    web.set3D(0, Unavailable("no GPU"))
    assert calls == [(1, ""), (0, "no GPU")]


def test_a_2d_template_is_written_to_the_temporary_folder_by_a_fixed_name():
    path = web.templatePath("2D")
    assert path == os.path.join(tempfile.gettempdir(), "graphik-pygbag-2d.tmpl")
    assert web.templatePath("3D") == web.TEMPLATE
    with pytest.raises(ValueError, match="not '4d'"):
        web.templatePath("4d")


# -- pygame keys


@pytest.mark.parametrize("scancode, name", [
    (4, "a"), (29, "z"), (30, "1"), (39, "0"), (58, "f1"), (69, "f12"),
    (44, "space"), (82, "up"), (224, "left ctrl"),
])
def test_scancodes_name_pygames_keys(scancode, name):
    assert web.pygameKey(scancode, pygame) == pygame.key.key_code(name)


def test_an_unknown_scancode_or_a_pygame_without_key_names_is_key_0():
    assert web.pygameKey(0, pygame) == 0
    assert web.pygameKey(100, pygame) == 0
    assert web.pygameKey(4, types.SimpleNamespace()) == 0
