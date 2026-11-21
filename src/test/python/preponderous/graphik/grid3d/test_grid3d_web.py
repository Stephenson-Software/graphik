"""grid3d's browser backend: the grid relay's wire format (Strata's
web/kit/grid-relay/WIRE.md, format 1.0), Grid3DWebView against a recording
relay, the event adapter and the pygbag page template. No browser needed."""

import base64
import json
import struct
import sys
import types

import pygame
import pytest

from preponderous.graphik.grid3d import (
    CAPSULE,
    CUBE,
    SPHERE,
    Camera,
    Grid3DView,
    GridBoard,
    Label,
    Light,
    Panel,
    Piece,
    PieceStyle,
    Scene,
    Shape,
    Theme,
    Unavailable,
)
from preponderous.graphik.grid3d import web


def theme():
    def eyes(piece, x, z, baseY):
        return [Shape(SPHERE, (x + 0.2, baseY + 0.4, z - 0.3), (0.1, 0.1, 0.1), (1, 1, 1, 1))]

    return Theme(
        pieces={
            "head": PieceStyle(SPHERE, (0.9, 0.2, 0.2), extras=eyes),
            "body": PieceStyle(SPHERE, (0.4, 0.8, 0.4), tones=(0.92, 0.78)),
            "gem": PieceStyle(CAPSULE, (0.2, 0.9, 0.9), glow=(2.0, 1.5)),
        }
    )


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


# -- the header (WIRE.md: magic, major, minor, kind, flags, reserved)


@pytest.mark.parametrize("kind", [web.BOARD, web.PIECES, web.HUD, web.VIEW])
def test_every_message_starts_with_the_8_byte_version_header(kind):
    head = web.header(kind)
    assert len(head) == 8
    assert head[:2] == b"G3" and head[:2] == bytes([0x47, 0x33])
    assert head[2] == 1 and head[3] == 0
    assert head[4] == kind and head[5] == 0 and head[6:8] == b"\0\0"


def test_another_major_version_is_refused_as_the_relay_refuses_it():
    message = bytearray(web.encodeHud([], []))
    message[2] = 2
    with pytest.raises(web.WireError, match="2.0") as caught:
        web.readHeader(bytes(message))
    assert caught.value.status == -2
    assert web.RecordingRelay().send(bytes(message)) == -2


def test_bad_magic_an_unknown_kind_and_a_truncated_header_are_refused():
    with pytest.raises(web.WireError) as caught:
        web.readHeader(b"XX\x01\x00\x01\x00\x00\x00")
    assert caught.value.status == -1
    unknown = bytearray(web.header(web.HUD))
    unknown[4] = 9
    with pytest.raises(web.WireError) as caught:
        web.readHeader(bytes(unknown))
    assert caught.value.status == -4
    with pytest.raises(web.WireError) as caught:
        web.readHeader(web.header(web.HUD)[:6])
    assert caught.value.status == -3


def test_a_later_minor_version_is_read_and_its_extra_fields_ignored():
    message = bytearray(web.encodeView(Camera((0.0, 5.0, 5.0), (0.0, 0.0, 0.0))))
    message[3] = 3
    kind, view = web.decode(bytes(message) + b"\x01\x02\x03\x04")
    assert kind == web.VIEW and view["fovDegrees"] == pytest.approx(42.0)


def test_a_body_shorter_than_its_counts_is_truncated():
    message = web.encodeBoard([Shape(CUBE, (0, 0, 0), (1, 1, 1), (1, 1, 1, 1))])
    with pytest.raises(web.WireError) as caught:
        web.decode(message[:-4])
    assert caught.value.status == -3


# -- record and message layouts


def test_record_sizes_match_the_spec():
    assert web.SHAPE.size == 48
    assert web.LIGHT.size == 36
    assert web.ANCHOR.size == 16
    assert web.PANEL.size == 32
    assert web.LABEL.size == 32
    assert web.VIEW_BODY.size == 64


def test_a_board_message_lays_out_counts_then_48_byte_shapes_then_36_byte_lights():
    shapes = [Shape(CUBE, (1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (0.1, 0.2, 0.3)),
              Shape(SPHERE, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0, 0.5))]
    lights = [Light((1.0, 2.0, 3.0), (1.0, 0.5, 0.25), 4.0, 2.0, castShadows=True)]
    message = web.encodeBoard(shapes, lights)
    assert len(message) == 8 + 8 + 2 * 48 + 36
    assert struct.unpack_from("<II", message, 8) == (2, 1)
    first = 16
    assert message[first] == CUBE and message[first + 1] == web.WORLD
    assert struct.unpack_from("<HHH", message, first + 2) == (0, 0, 0)
    assert struct.unpack_from("<3f", message, first + 8) == (1.0, 2.0, 3.0)
    assert struct.unpack_from("<3f", message, first + 20) == (4.0, 5.0, 6.0)
    # a 3-component colour is sent opaque
    assert struct.unpack_from("<4f", message, first + 32) == pytest.approx((0.1, 0.2, 0.3, 1.0))
    light = 16 + 2 * 48
    assert message[light] == web.WORLD and message[light + 1] == 1  # casts shadows
    assert struct.unpack_from("<3f3fff", message, light + 4) == (1.0, 2.0, 3.0, 1.0, 0.5, 0.25, 4.0, 2.0)


def test_a_hud_message_pads_each_labels_text_to_four_bytes():
    panels = [Panel(1.0, 2.0, 3.0, 4.0, (0.0, 0.0, 0.0, 0.5))]
    labels = [Label("Score", 10.0, 20.0, 16.0), Label("ok", 0.0, 0.0, 8.0, (1.0, 0.0, 0.0, 1.0))]
    message = web.encodeHud(labels, panels)
    assert struct.unpack_from("<II", message, 8) == (1, 2)  # panels, then labels
    assert struct.unpack_from("<4f4f", message, 16) == (1.0, 2.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.5)
    label = 16 + 32
    x, y, size = struct.unpack_from("<3f", message, label)
    length, reserved = struct.unpack_from("<HH", message, label + 28)
    assert (x, y, size, length, reserved) == (10.0, 20.0, 16.0, 5, 0)
    assert message[label + 32:label + 40] == b"Score\0\0\0"
    second = label + 40
    assert struct.unpack_from("<HH", message, second + 28) == (2, 0)
    assert message[second + 32:second + 36] == b"ok\0\0"
    assert len(message) == second + 36
    kind, hud = web.decode(message)
    assert [l["text"] for l in hud["labels"]] == ["Score", "ok"]


def test_label_text_is_utf8_with_no_nul_inside():
    message = web.encodeHud([Label("café\0!", 0, 0, 8)])
    _, hud = web.decode(message)
    assert hud["labels"][0]["text"] == "café!"


def test_a_view_message_is_64_bytes_of_camera_clear_colour_and_sun():
    camera = Camera((0.0, 10.0, 8.0), (0.0, -0.3, -0.5), 42.0)
    message = web.encodeView(camera, (0.1, 0.2, 0.3, 1.0))
    assert len(message) == 8 + 64
    values = struct.unpack_from("<16f", message, 8)
    assert values[0:3] == (0.0, 10.0, 8.0)
    assert values[3:6] == pytest.approx((0.0, -0.3, -0.5))
    assert values[6:9] == pytest.approx((42.0, 0.3, 200.0))
    assert values[9:13] == pytest.approx((0.1, 0.2, 0.3, 1.0))
    assert values[13:16] == pytest.approx(web.SUN_DIRECTION)


def test_pieces_are_anchors_plus_shapes_measured_from_them():
    board = GridBoard(6, 4, theme())
    head = Piece("h", 3, 1, "head", chain="s", link=0)
    body = Piece("b", 2, 1, "body", chain="s", link=1)
    gem = Piece("g", 0, 3, "gem")
    tracks = {"h": ((-0.5, -0.5), board.cellCenter(3, 1))}
    message = web.encodePieces(board, [head, body, gem], tracks, 0.15)
    tick, anchors, shapes, lights = struct.unpack_from("<fIII", message, 8)
    assert tick == pytest.approx(0.15) and anchors == 3 and lights == 1
    kind, pieces = web.decode(message)
    assert pieces["anchors"][0] == pytest.approx((-0.5, -0.5) + board.cellCenter(3, 1))
    assert pieces["anchors"][1] == pytest.approx(board.cellCenter(2, 1) * 2)
    # the desktop's shapes for the pieces standing on their cells, with x and
    # z measured from each piece's anchor, and the bridge from both
    desktop, glow = board.pieceShapes([head, body, gem])
    sent = pieces["shapes"]
    assert len(sent) == len(desktop) == shapes
    centres = [board.cellCenter(p.column, p.row) for p in (head, body, gem)]
    for got, want in zip(sent, desktop):
        if got["attach"] == web.PIECE:
            cx, cz = centres[got["a"]]
            assert (got["position"][0] + cx, got["position"][2] + cz) == pytest.approx(
                (want.position[0], want.position[2]))
        else:
            assert got["attach"] == web.BRIDGE and (got["a"], got["b"]) == (0, 1)
            assert got["position"][0] == 0.0 and got["position"][2] == 0.0
        assert got["position"][1] == pytest.approx(want.position[1])
        assert got["color"] == pytest.approx(want.color)
    assert [s["attach"] for s in sent].count(web.PIECE) == 4  # head, its eye, body, gem
    light = pieces["lights"][0]
    assert light["attach"] == web.PIECE and light["a"] == 2
    assert (light["position"][0], light["position"][2]) == pytest.approx((0.0, 0.0))


def test_a_wire_recording_is_json_of_base64_messages():
    relay = web.RecordingRelay()
    relay.send(web.encodeHud([Label("x", 0, 0, 8)]))
    decoded = [base64.b64decode(m) for m in json.loads(relay.wireJson())]
    assert decoded == relay.messages


# -- the view


def openWeb(relay=None, **kwargs):
    relay = relay or web.RecordingRelay()
    return web.Grid3DWebView.open(800, 600, relay=relay, **kwargs), relay


def test_opening_asks_the_page_for_its_3d_view_and_a_failure_is_unavailable():
    view, relay = openWeb(maxBytes=123)
    assert relay.options["maxBytes"] == 123 and relay.options["canvas"] == "relay"
    assert view.ready and view.failure() is None
    with pytest.raises(Unavailable, match="no WebGL 2"):
        openWeb(web.RecordingRelay(state="failed:no WebGL 2"))
    loading, _ = openWeb(web.RecordingRelay(state="loading"))
    assert not loading.ready


def test_the_page_decides_reduced_motion_unless_the_game_does():
    view, _ = openWeb(web.RecordingRelay(reducedMotion=True))
    assert view.reducedMotion
    view, _ = openWeb(web.RecordingRelay(reducedMotion=True), reducedMotion=False)
    assert not view.reducedMotion


def test_a_board_sends_board_view_and_pieces_and_a_tick_sends_only_pieces():
    clock = Clock()
    view, relay = openWeb(clock=clock)
    board = GridBoard(6, 4, theme())
    view.setBoard(board)
    assert [m[4] for m in relay.messages] == [web.BOARD, web.VIEW, web.PIECES]
    _, sentBoard = web.decode(relay.messages[0])
    assert len(sentBoard["shapes"]) == len(board.boardShapes())
    view.setPieces([Piece("h", 1, 1, "head")], 0.2)
    view.setPieces([Piece("h", 2, 1, "head")], 0.2)
    assert relay.messages[-1][4] == web.PIECES
    _, pieces = web.decode(relay.messages[-1])
    assert pieces["tickSeconds"] == pytest.approx(0.2)
    assert pieces["anchors"][0] == pytest.approx(board.cellCenter(1, 1) + board.cellCenter(2, 1))
    view.setLabels([Label("Score", 0, 0, 16)])
    assert relay.messages[-1][4] == web.HUD
    view.resize(400, 800)
    _, sentView = web.decode(relay.messages[-1])
    assert sentView["eye"] == pytest.approx(board.camera(0.5).eye)
    view.frame()  # nothing per frame
    assert len(relay.messages) == 7


def test_a_snap_puts_pieces_on_their_cells():
    view, relay = openWeb(clock=Clock())
    board = GridBoard(6, 4, theme())
    view.setBoard(board)
    view.setPieces([Piece("h", 1, 1, "head")], 0.2)
    view.setPieces([Piece("h", 2, 1, "head")], 0.2, snap=True)
    _, pieces = web.decode(relay.messages[-1])
    assert pieces["tickSeconds"] == 0.0
    assert pieces["anchors"][0] == pytest.approx(board.cellCenter(2, 1) * 2)


def test_the_web_view_picks_cells_as_the_desktop_does():
    view, _ = openWeb()
    board = GridBoard(5, 5, theme())
    assert view.pickCell(400, 300) is None  # no board yet
    view.setBoard(board)
    at = view.cellScreenPosition(1, 3)
    assert view.pickCell(*at) == (1, 3)
    assert view.camera() == board.camera(800 / 600.0)


def test_draw_scene_sends_only_what_changed():
    view, relay = openWeb()
    scene = Scene(shapes=[Shape(CUBE, (0, 0, 0), (1, 1, 1), (1, 1, 1, 1))],
                  labels=[Label("hi", 0, 0, 8)], camera=Camera((0, 5, 5), (0, 0, 0)))
    view.drawScene(scene)
    assert sorted(m[4] for m in relay.messages) == [web.BOARD, web.PIECES, web.HUD, web.VIEW]
    view.drawScene(scene)
    assert len(relay.messages) == 4
    scene.labels = [Label("ho", 0, 0, 8)]
    view.drawScene(scene)
    assert len(relay.messages) == 5 and relay.messages[-1][4] == web.HUD


def test_a_refused_message_raises():
    class Refusing(web.RecordingRelay):
        def send(self, message):
            return -6

    view, _ = openWeb(Refusing())
    with pytest.raises(web.WireError, match="limits"):
        view.setLabels([Label("x", 0, 0, 8)])


def test_events_come_back_as_strata_style_events():
    view, relay = openWeb()
    relay.events = [{"type": web.EVENT_MOUSE_BUTTON_DOWN, "button": 1, "x": 10, "y": 20, "pointer": "touch"}]
    (event,) = view.pollEvents()
    assert event.type == view.strata.EVENT_MOUSE_BUTTON_DOWN and (event.x, event.y) == (10, 20)
    assert event.scancode == 0 and event.text == ""
    assert view.pollEvents() == []


class FakePageRelay:
    """window.StrataGridRelay as pygbag's bridge shows it: strings in and out."""

    def __init__(self):
        self.requests, self.sent = [], []

    def request(self, options):
        self.requests.append(json.loads(options))
        return "loading"

    def state(self):
        return "ready"

    def send(self, b64):
        self.sent.append(base64.b64decode(b64))
        return 0

    def poll(self):
        return '[{"type": 8, "width": 320, "height": 200}]'

    def reducedMotion(self):
        return 0

    def close(self):
        pass


def test_open_picks_the_web_view_in_a_browser(monkeypatch):
    page = FakePageRelay()
    monkeypatch.setattr(sys, "platform", "emscripten")
    fake = types.ModuleType("platform")
    fake.window = types.SimpleNamespace(StrataGridRelay=page)
    monkeypatch.setitem(sys.modules, "platform", fake)
    view = Grid3DView.open(640, 480, "Game")
    assert type(view).__name__ == "Grid3DWebView"
    assert (view.width, view.height) == (640, 480)
    assert page.requests == [{"canvas": "relay", "maxBytes": 4000000, "title": "Game"}]
    view.setLabels([Label("hi", 0, 0, 8)])
    assert page.sent[-1][:2] == b"G3" and page.sent[-1][4] == web.HUD
    (event,) = view.pollEvents()
    assert (event.type, event.width, event.height) == (web.EVENT_RESIZED, 320, 200)
    with pytest.raises(Unavailable, match="headless"):
        Grid3DView.open(640, 480, headless=True)


def test_a_page_without_the_relay_is_unavailable(monkeypatch):
    monkeypatch.setattr(sys, "platform", "emscripten")
    fake = types.ModuleType("platform")
    fake.window = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "platform", fake)
    with pytest.raises(Unavailable, match="no 3D view"):
        web.Grid3DWebView.open()
    assert web.wants3D() is False


def test_the_page_toggle_is_read_and_set_through_window_graphik3d(monkeypatch):
    calls = []

    class Toggle:
        on = 1

        def wanted(self):
            return self.on

        def set(self, value, reason):
            calls.append((value, reason))

    monkeypatch.setattr(sys, "platform", "emscripten")
    fake = types.ModuleType("platform")
    fake.window = types.SimpleNamespace(Graphik3D=Toggle())
    monkeypatch.setitem(sys.modules, "platform", fake)
    assert web.wants3D() is True
    web.set3D(False, "no WebGL 2")
    assert calls == [(0, "no WebGL 2")]


def test_outside_a_browser_there_is_no_toggle():
    assert web.wants3D() is False
    web.set3D(True)  # does nothing
    assert web.buttonArea() is None


def test_the_buttons_area_is_read_from_the_page(monkeypatch):
    class Toggle:
        shown = "326,8,56,36"

        def area(self):
            return self.shown

    toggle = Toggle()
    monkeypatch.setattr(sys, "platform", "emscripten")
    fake = types.ModuleType("platform")
    fake.window = types.SimpleNamespace(Graphik3D=toggle)
    monkeypatch.setitem(sys.modules, "platform", fake)
    assert web.buttonArea() == (326, 8, 56, 36)
    toggle.shown = ""  # hidden
    assert web.buttonArea() is None


def test_a_template_without_area_has_no_button_area(monkeypatch):
    class OldToggle:
        def area(self):
            raise AttributeError("area")

    monkeypatch.setattr(sys, "platform", "emscripten")
    fake = types.ModuleType("platform")
    fake.window = types.SimpleNamespace(Graphik3D=OldToggle())
    monkeypatch.setitem(sys.modules, "platform", fake)
    assert web.buttonArea() is None


@pytest.mark.parametrize(
    "text, area",
    [
        ("326,8,56,36", (326, 8, 56, 36)),
        ("326.4,8.6,56,36", (326, 8, 56, 36)),
        ("", None),
        ("1,2,3", None),
        ("1,2,0,4", None),
        ("a,b,c,d", None),
    ],
)
def test_parse_area(text, area):
    assert web.parseArea(text) == area


# -- pygame events


def ev(**fields):
    return web.Event(fields)


def test_pointer_events_become_pygame_mouse_events():
    events = web.toPygameEvents([
        ev(type=web.EVENT_MOUSE_BUTTON_DOWN, button=1, x=10.6, y=20.2, pointer="touch"),
        ev(type=web.EVENT_MOUSE_MOTION, x=12, y=22, dx=2, dy=2, pointer="mouse"),
        ev(type=web.EVENT_MOUSE_BUTTON_UP, button=1, x=12, y=22),
        ev(type=web.EVENT_MOUSE_WHEEL, x=0, y=1),
        ev(type=web.EVENT_RESIZED, width=640, height=480),
    ], pygame)
    assert [e.type for e in events] == [pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION,
                                        pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL, pygame.VIDEORESIZE]
    assert events[0].pos == (10, 20) and events[0].button == 1 and events[0].touch
    assert events[1].rel == (2, 2) and not events[1].touch
    assert events[3].y == 1
    assert events[4].size == (640, 480)


def test_fingers_become_pygame_finger_events():
    events = web.toPygameEvents([
        ev(type=web.EVENT_FINGER_DOWN, id=3, nx=0.25, ny=0.5, pressure=0.7),
        ev(type=web.EVENT_FINGER_MOTION, id=3, nx=0.3, ny=0.5, dx=0.05, dy=0.0),
        ev(type=web.EVENT_FINGER_UP, id=3, nx=0.3, ny=0.5),
        ev(type=web.EVENT_FINGER_CANCELED, id=4, nx=0.1, ny=0.1),
    ], pygame)
    assert [e.type for e in events] == [pygame.FINGERDOWN, pygame.FINGERMOTION,
                                        pygame.FINGERUP, pygame.FINGERUP]
    assert (events[0].x, events[0].y, events[0].finger_id) == (0.25, 0.5, 3)
    assert events[0].pressure == pytest.approx(0.7)
    assert events[1].dx == pytest.approx(0.05)
    assert web.toPygameEvents([ev(type=web.EVENT_FINGER_DOWN, id=1)], pygame, fingers=False) == []


def test_keys_are_left_to_pygame_unless_asked_for():
    pygame.init()  # pygame.key.key_code wants it, as it is under pygbag
    down = ev(type=web.EVENT_KEY_DOWN, scancode=82, modifiers=0x1, key="ArrowUp")
    assert web.toPygameEvents([down], pygame) == []
    (event,) = web.toPygameEvents([down], pygame, keys=True)
    assert event.type == pygame.KEYDOWN and event.key == pygame.K_UP
    assert event.mod & pygame.KMOD_LSHIFT and event.unicode == ""
    (letter, text) = web.toPygameEvents([ev(type=web.EVENT_KEY_DOWN, scancode=4, key="a"),
                                          ev(type=web.EVENT_TEXT_INPUT, text="a")], pygame, keys=True)
    assert letter.key == pygame.K_a and letter.unicode == "a" and text.text == "a"


def test_desktop_strata_events_convert_too():
    # desktop events have no pointer, nx or pressure fields
    desktop = types.SimpleNamespace(type=web.EVENT_MOUSE_BUTTON_DOWN, button=1, x=5, y=6)
    (event,) = web.toPygameEvents([desktop], pygame)
    assert event.pos == (5, 6) and not event.touch


# -- the page template


def templatePage():
    with open(web.templatePath(), encoding="utf-8") as handle:
        return handle.read()


def graphikBlock(page):
    """The template's own part, after pygbag's default page."""
    return page[page.index("graphik grid3d:"):]


def test_the_template_is_package_data_with_the_relay_and_a_3d_toggle():
    page = templatePage()
    assert page.startswith("<html")
    assert '<canvas id="relay" hidden' in page
    assert 'id="graphik3d"' in page and "window.Graphik3D" in page
    # 3D loads only when asked for, and 2D comes back when it can't
    assert page.index("relay.request(JSON.stringify(") > page.index("function start(")
    assert 'state.indexOf("failed:") === 0' in page and "show2d(true)" in page
    # pygbag's own canvas is still there, and its python block intact
    assert 'id="canvas"' in page and "asyncio.run( custom_site() )" in page


def test_the_relays_scripts_are_fetched_only_when_3d_is_wanted():
    page = templatePage()
    block = graphikBlock(page)
    # no script tag fetches them with the page (a page starting in 2D
    # fetches nothing of the 3D view)
    for script in ("strata-loader.js", "strata-kit.js", "grid-relay.js"):
        assert '<script src="%s"' % script not in page
        assert "src='%s'" % script not in page
    # they are injected, in order, by set() turning 3D on
    assert '["strata-loader.js", "strata-kit.js", "grid-relay.js"]' in block
    assert 'document.createElement("script")' in block
    assert block.index("loadScripts(0)") > block.index("function set(")
    assert "tag.onload = function () { loadScripts(index + 1); }" in block
    # a missing file brings the 2D view back with a plain reason
    assert "tag.onerror" in block and "could not be downloaded" in block
    # the game is told 3D is wanted only once the scripts are in
    assert 'wanted: function () { return on && scripts === "ready" ? 1 : 0; }' in block


def test_the_page_starts_in_3d_unless_asked_otherwise():
    block = graphikBlock(templatePage())
    assert 'data-default-view="3d"' in block
    assert 'if (startingView() === "3d") {' in block
    # the address first, then the player's choice, then the game's default
    view = block[block.index("function startingView()"):]
    assert view.index('get("view")') < view.index("remembered()") < view.index(
        'getAttribute("data-default-view")'
    )
    # the choice on the button is remembered; storage that throws is fine
    assert 'remember(on ? "3d" : "2d")' in block
    assert block.count("try {") >= 3 and "localStorage" in block


def test_2d_shows_until_3d_draws_the_game_and_comes_back_with_a_reason():
    block = graphikBlock(templatePage())
    # the 2D canvas hides only once the game has sent the 3D view something
    assert "fed = true" in block
    assert 'const drawing = state === "ready" && fed && !(c && c.hidden);' in block
    assert "if (drawing) {\n      show2d(false);" in block
    # failures say why, in words, on the page
    assert 'id="graphik3d-note"' in block and 'role="status"' in block
    assert "No 3D view here: " in block and "The 2D view stays." in block
    assert 'indexOf("failed:") === 0) fail(' in block
    assert "this browser can't draw WebGL 2" in block and ".sk-loader { display: none !important; }" in block


def test_a_game_can_choose_2d_as_its_default_view():
    assert web.templatePath() == web.TEMPLATE == web.templatePath("3d")
    path = web.templatePath(defaultView="2d")
    assert path != web.TEMPLATE
    with open(path, encoding="utf-8") as handle:
        page = handle.read()
    assert 'data-default-view="2d"' in page and 'data-default-view="3d"' not in page
    # otherwise the same page
    assert page.replace('"2d"', '"3d"') == templatePage().replace('"2d"', '"3d"')
    with pytest.raises(ValueError):
        web.templatePath("4d")


def test_the_page_never_scrolls_so_the_button_stays_on_screen():
    block = graphikBlock(templatePage())
    assert "html, body { overflow: hidden; }" in block
    # the relay's canvas fills the viewport, not 100vw (wider than it with
    # a scrollbar)
    assert "width:100vw" not in block and "width:100%;height:100%" in block


def test_the_template_has_one_viewport_tag_with_device_width():
    page = templatePage()
    tags = [line.strip() for line in page.splitlines() if 'name="viewport"' in line]
    assert len(tags) == 1, tags
    assert "width=device-width" in tags[0] and "initial-scale=1.0" in tags[0]


def test_the_button_says_where_it_is():
    block = graphikBlock(templatePage())
    assert "area: function ()" in block and "getBoundingClientRect()" in block


def test_the_template_has_no_jinja_delimiters_in_graphiks_part():
    # pygbag renders the template: {{ }}, {% %} or {# #} in the JS would break it
    block = graphikBlock(templatePage())
    for delimiter in ("{{", "{%", "{#"):
        assert delimiter not in block


def test_the_button_is_a_switch_showing_both_views_and_a_finger_sized_target():
    block = graphikBlock(templatePage())
    button = block[block.index('<button id="graphik3d"'):block.index("</button>")]
    # both views on it, so it reads as a choice and not as a status
    assert '<span\n    id="graphik3d-2d"' in button and '<span\n    id="graphik3d-3d"' in button
    assert ">2D</span>" in button and ">3D</span>" in button
    # a toggle a screen reader can name: "3D view", pressed while 3D is on
    assert 'aria-label="3D view"' in button and 'aria-pressed="false"' in button
    assert 'aria-hidden="true"' in button
    # at least 44 CSS pixels each way, and the note sits clear below it
    assert "min-width:44px;min-height:44px" in button and "box-sizing:border-box" in button
    assert "top: 60px" in block
    assert ".graphik3d-segment.graphik3d-current" in block
