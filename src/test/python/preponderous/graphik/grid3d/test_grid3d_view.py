"""Grid3DView: why it can't start, what it asks of Strata, and a headless
render against a golden image.

The engine-call tests drive Grid3DView against a fake `strata` module, so
they run everywhere. The render tests need Strata's Python binding and its library; they skip when
Strata can't load here (Grid3DView.open raises Unavailable).
"""

import json
import os
import shutil
import subprocess
import sys
import types

import pytest

from preponderous.graphik.grid3d import (
    CAPSULE,
    SPHERE,
    GridBoard,
    Grid3DView,
    Label,
    Light,
    Panel,
    Piece,
    PieceStyle,
    Scene,
    SceneLimitError,
    Shape,
    Theme,
    Unavailable,
)
from preponderous.graphik.grid3d import view as viewModule

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "board-4x3.png")


# -- why it can't start (no GPU needed)


def test_a_system_without_a_strata_library_is_unavailable(monkeypatch):
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    with pytest.raises(Unavailable, match="no library for this system"):
        viewModule.loadStrata(platform="darwin")


def test_a_missing_binding_says_how_to_install_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "strata", None)  # makes `import strata` fail
    with pytest.raises(Unavailable, match=r"graphik\[strata\]"):
        viewModule.loadStrata(platform="linux")


# -- what the view asks of Strata (a fake binding, no GPU needed)


class FakeEngine:
    """Records every call Grid3DView makes on a Strata engine."""

    def __init__(self, lib, width, height, surface=None, title=None):
        self.lib = lib
        self.size = (width, height)
        self.surface, self.title = surface, title
        self.calls = []
        self.events = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record

    def poll_event(self):
        return self.events.pop(0) if self.events else None

    def names(self):
        return [name for name, _, _ in self.calls]

    def call(self, name):
        (found,) = [(args, kwargs) for n, args, kwargs in self.calls if n == name]
        return found


class FakeLib:
    def __init__(self):
        self.loaded = None

    def lighting_defaults(self, kind):
        return types.SimpleNamespace(kind=kind, shadow_distance=None, fog=None)

    def look_at(self, eye, target, **kwargs):
        return ("look_at", eye, target, kwargs)


def fakeStrata(engineError=None, loadError=None):
    """A stand-in for the `strata` module, with just what view.py uses."""
    strata = types.ModuleType("strata")
    strata.lib = FakeLib()
    strata.EVENT_QUIT, strata.EVENT_KEY_DOWN = "quit", "key-down"
    strata.EVENT_KEY_UP, strata.EVENT_RESIZED = "key-up", "resized"
    strata.SURFACE_HEADLESS, strata.SURFACE_WINDOW = "headless", "window"
    strata.LIGHTING_SUN = "sun"
    strata.POINT_LIGHT_CAST_SHADOWS = 7
    strata.TEXT_SHADOW = "shadow"
    strata.PointLight = types.SimpleNamespace
    strata.RenderItem = lambda *fields: ("item",) + fields
    strata.Rect = lambda *fields: ("rect",) + fields
    strata.Text = lambda *fields: ("text",) + fields
    strata.engines = []

    def load(*version):
        if loadError is not None:
            raise loadError
        strata.lib.loaded = version
        return strata.lib

    strata.load = lambda: load()
    strata.load_release = lambda version: load(version)

    def engine(*args, **kwargs):
        if engineError is not None:
            raise engineError
        made = FakeEngine(*args, **kwargs)
        strata.engines.append(made)
        return made

    strata.Engine = engine
    return strata


@pytest.fixture
def strata(monkeypatch):
    module = fakeStrata()
    monkeypatch.setitem(sys.modules, "strata", module)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    monkeypatch.setenv("GALLIUM_DRIVER", "llvmpipe")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    return module


def test_a_release_library_is_loaded_at_the_pinned_version(strata):
    module, lib = viewModule.loadStrata()
    assert module is strata and lib is strata.lib
    assert lib.loaded == (viewModule.STRATA_VERSION,)


def test_strata_library_loads_a_local_build_on_any_system(strata, monkeypatch):
    monkeypatch.setenv("STRATA_LIBRARY", "/opt/libstrata.so")
    _, lib = viewModule.loadStrata(platform="darwin")
    assert lib.loaded == ()  # strata.load(), not load_release()


def test_a_library_that_fails_to_load_is_unavailable_with_the_reason(monkeypatch):
    monkeypatch.setitem(sys.modules, "strata", fakeStrata(loadError=OSError("bad checksum")))
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    monkeypatch.setenv("GALLIUM_DRIVER", "llvmpipe")
    with pytest.raises(Unavailable, match="couldn't be loaded: bad checksum"):
        viewModule.loadStrata(platform="linux")


def test_open_makes_a_window_and_sets_the_sun(strata):
    view = Grid3DView.open(320, 200, "Game")
    (engine,) = strata.engines
    assert view.engine is engine and view.isWindow
    assert (engine.size, engine.surface, engine.title) == ((320, 200), "window", "Game")
    (lighting,), _ = engine.call("set_lighting")
    assert (lighting.kind, lighting.shadow_distance, lighting.fog) == ("sun", 40.0, 0)
    assert engine.call("set_sun_direction") == (((-0.45, 0.85, 0.35),), {})
    assert (view.EVENT_QUIT, view.EVENT_RESIZED) == ("quit", "resized")


def test_open_headless_has_no_window_or_title(strata):
    view = Grid3DView.open(320, 200, "Game", headless=True)
    (engine,) = strata.engines
    assert not view.isWindow
    assert (engine.surface, engine.title) == ("headless", None)


def test_an_engine_that_cant_open_is_unavailable_with_the_reason(monkeypatch):
    monkeypatch.setitem(sys.modules, "strata", fakeStrata(engineError=RuntimeError("no GPU")))
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    monkeypatch.setenv("GALLIUM_DRIVER", "llvmpipe")
    with pytest.raises(Unavailable, match="no Strata window could be opened: no GPU"):
        Grid3DView.open(320, 200)


def test_pieces_and_scenes_need_a_board_first(strata):
    view = Grid3DView.open(320, 200)
    assert view.pickCell(10, 10) is None
    with pytest.raises(RuntimeError, match="setBoard"):
        view.setPieces([])
    with pytest.raises(RuntimeError, match="setBoard"):
        view.scene()
    with pytest.raises(RuntimeError, match="setBoard"):
        view.camera()


def test_a_cells_screen_position_picks_that_cell_back(strata):
    view = Grid3DView.open(400, 300)
    view.setBoard(GridBoard(5, 4))
    x, y = view.cellScreenPosition(3, 1)
    assert view.pickCell(x, y) == (3, 1)
    cx, cz = view.board.cellCenter(3, 1)
    assert view.projectToScreen((cx, 0.0, cz)) == (x, y)


def test_a_frame_draws_the_scene_through_the_engine(strata):
    view = Grid3DView.open(400, 200, clock=lambda: 5.0)
    theme = Theme(pieces={"pawn": PieceStyle(SPHERE, (0.9, 0.25, 0.2))})
    view.setBoard(GridBoard(4, 3, theme), lights=[
        Light((0, 1, 0), (1, 1, 1), 3.0, 2.0, castShadows=True),
        Light((1, 1, 0), (1, 0, 0), 4.0, 1.0),
    ])
    view.setPieces([Piece("p", 1, 1, "pawn")])
    view.setLabels([Label("score", 4, 6, 12)], [Panel(0, 0, 50, 20)])
    scene = view.scene()
    engine = view.engine
    engine.calls.clear()

    view.frame()

    assert engine.names() == ["set_camera", "set_point_lights", "begin_frame",
                              "submit_primitives", "submit_rects", "submit_text",
                              "end_frame", "present"]
    (camera,), _ = engine.call("set_camera")
    assert camera[1:3] == (scene.camera.eye, scene.camera.target)
    assert camera[3]["aspect"] == 2.0
    (lights,), _ = engine.call("set_point_lights")
    assert [(l.range, l.intensity, l.flags) for l in lights] == [(3.0, 2.0, 7), (4.0, 1.0, 0)]
    assert engine.call("begin_frame") == ((), {"clear_color": scene.clearColor})
    (items,), _ = engine.call("submit_primitives")
    assert len(items) == len(scene.shapes)
    assert engine.call("submit_rects") == (([("rect", 0, 0, 50, 20, Panel(0, 0, 0, 0).color)],), {})
    (texts,), _ = engine.call("submit_text")
    assert texts == [("text", 4, 6, 12, "shadow", Label("", 0, 0, 0).color, b"score")]


def test_a_scene_without_text_panels_or_camera_skips_them_and_may_not_present(strata):
    view = Grid3DView.open(320, 200)
    view.drawScene(Scene(shapes=[Shape(SPHERE, (0, 0, 0), (1, 1, 1), (1, 1, 1, 1))]),
                   present=False)
    assert view.engine.names()[2:] == ["set_point_lights", "begin_frame",
                                        "submit_primitives", "end_frame"]


def test_a_scene_over_the_engine_limits_is_refused_before_drawing(strata):
    view = Grid3DView.open(320, 200)
    engine = view.engine
    engine.calls.clear()
    with pytest.raises(SceneLimitError):
        view.drawScene(Scene(shapes=[Shape(99, (0, 0, 0), (1, 1, 1), (1, 1, 1, 1))]))
    assert engine.calls == []


def test_events_are_drained_and_resize_and_close_reach_the_engine(strata):
    view = Grid3DView.open(320, 200)
    engine = view.engine
    engine.events = ["quit", "key-down"]
    assert view.pollEvents() == ["quit", "key-down"]
    assert view.pollEvents() == []
    view.resize(640, 480)
    assert (view.width, view.height) == (640, 480)
    assert engine.call("resize") == ((640, 480), {})
    view.savePng("out.png")
    assert engine.call("save_screenshot_png") == (("out.png",), {})
    view.close()
    view.close()  # a second close is a no-op
    assert engine.names().count("close") == 1 and view.engine is None


# -- rendering (needs Strata)


def openHeadless(width=240, height=180, clock=None):
    try:
        if clock is None:
            return Grid3DView.open(width, height, headless=True)
        return Grid3DView.open(width, height, headless=True, clock=clock)
    except Unavailable as reason:
        pytest.skip("Strata can't run here: %s" % reason)


def goldenScene(view):
    theme = Theme(
        pieces={
            "pawn": PieceStyle(SPHERE, (0.9, 0.25, 0.2)),
            "gem": PieceStyle(CAPSULE, (0.2, 0.8, 0.95), height=0.7, size=0.4, glow=(2.0, 1.6)),
        }
    )
    view.setBoard(GridBoard(4, 3, theme))
    view.setPieces([Piece("p", 1, 1, "pawn"), Piece("g", 3, 0, "gem")])
    view.setLabels([Label("grid3d", 8, 8, 14)])


def differingFraction(expected, actual, threshold=12.0):
    """Fraction of pixels whose RGB distance exceeds `threshold` (0-255 scale).
    Uses strata-imgcmp (STRATA_IMGCMP or on PATH) when available."""
    imgcmp = os.environ.get("STRATA_IMGCMP") or shutil.which("strata-imgcmp")
    if imgcmp:
        out = subprocess.run(
            [imgcmp, expected, actual, "--json", "--threshold", "4"],
            capture_output=True,
            text=True,
        )
        report = json.loads(out.stdout)
        for key in ("fraction_over", "fractionOver", "over_fraction"):
            if key in report:
                return float(report[key])
        if "pixels_over" in report and "pixels" in report:
            return report["pixels_over"] / float(report["pixels"])
    import pygame

    a = pygame.image.load(expected)
    b = pygame.image.load(actual)
    assert a.get_size() == b.get_size()
    width, height = a.get_size()
    over = 0
    for y in range(height):
        for x in range(width):
            pa, pb = a.get_at((x, y)), b.get_at((x, y))
            d = ((pa.r - pb.r) ** 2 + (pa.g - pb.g) ** 2 + (pa.b - pb.b) ** 2) ** 0.5
            over += d > threshold
    return over / float(width * height)


def test_a_board_renders_like_the_golden_image(tmp_path):
    view = openHeadless()
    try:
        goldenScene(view)
        view.frame(present=False)
        actual = str(tmp_path / "board-4x3.png")
        view.savePng(actual)
    finally:
        view.close()
    assert differingFraction(GOLDEN, actual) <= 0.02


def test_a_frame_mid_tick_draws_a_piece_between_its_cells():
    now = [0.0]
    view = openHeadless(clock=lambda: now[0])
    try:
        theme = Theme(pieces={"pawn": PieceStyle(SPHERE, (0.9, 0.25, 0.2))})
        view.setBoard(GridBoard(4, 3, theme))
        view.setPieces([Piece("p", 0, 1, "pawn")], tickSeconds=0.2)
        now[0] = 0.2
        view.setPieces([Piece("p", 1, 1, "pawn")], tickSeconds=0.2)
        now[0] = 0.3
        scene = view.scene()
        piece = scene.shapes[-1]
        assert piece.position[0] == pytest.approx(-1.0)  # halfway from -1.5 to -0.5
        view.frame(present=False)  # and the engine accepts it
    finally:
        view.close()
