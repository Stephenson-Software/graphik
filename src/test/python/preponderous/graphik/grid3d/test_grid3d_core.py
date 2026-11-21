"""The views over fakes of their ports: no stand-in strata module, no
patched sys.platform, no stand-in pygbag."""

import types

import pytest

from preponderous.graphik.grid3d import (
    CUBE,
    GridBoard,
    Grid3DView,
    Label,
    Piece,
    PieceStyle,
    Scene,
    SceneLimitError,
    Shape,
    Theme,
    Unavailable,
)
from preponderous.graphik.grid3d import web

from test_grid3d_ports import FakeDisplay, FakePage

EVENT_NAMES = types.SimpleNamespace(EVENT_QUIT="quit", EVENT_KEY_DOWN="down",
                                    EVENT_KEY_UP="up", EVENT_RESIZED="resized")


def fakeView(events=(), clock=lambda: 3.0):
    display = FakeDisplay(events)
    display.strata = EVENT_NAMES
    return Grid3DView.using(display, 400, 200, clock=clock), display


def theme():
    return Theme(pieces={"pawn": PieceStyle(CUBE, (0.9, 0.9, 0.9))})


def test_a_frame_draws_the_views_scene_at_the_windows_aspect():
    view, display = fakeView()
    view.setBoard(GridBoard(4, 3, theme()))
    view.setPieces([Piece("p", 1, 1, "pawn")])
    view.setLabels([Label("hi", 0, 0, 8)])
    view.frame(present=False)
    ((scene, aspect, present),) = display.drawn
    assert scene == view.scene() and aspect == 2.0 and present is False
    assert view.EVENT_QUIT == "quit" and view.isWindow


def test_a_scene_over_the_limits_never_reaches_the_display():
    view, display = fakeView()
    with pytest.raises(SceneLimitError):
        view.drawScene(Scene(shapes=[Shape(99, (0, 0, 0), (1, 1, 1), (1, 1, 1, 1))]))
    assert display.drawn == []


def test_the_window_calls_reach_the_display():
    view, display = fakeView(events=["quit"])
    assert view.pollEvents() == ["quit"] and view.pollEvents() == []
    view.resize(300, 300)
    assert display.sizes == [(300, 300)] and (view.width, view.height) == (300, 300)
    with pytest.raises(Unavailable, match="no pixels"):
        view.savePng("x.png")
    view.close()
    assert display.closed == 1


def test_the_page_helpers_read_the_page_through_its_port(monkeypatch):
    calls = []

    class Toggle:
        def wanted(self):
            return 1

        def area(self):
            return "10,8,56,36"

        def touch(self):
            return "1"

        def set(self, value, reason):
            calls.append((value, reason))

    monkeypatch.setattr(web, "PAGE", FakePage(Graphik3D=Toggle()))
    assert web.wants3D() is True
    assert web.buttonArea() == (10, 8, 56, 36)
    assert web.touchScreen() is True
    web.set3D(False, "slow")
    assert calls == [(0, "slow")]
    monkeypatch.setattr(web, "PAGE", FakePage())
    assert web.wants3D() is False and web.buttonArea() is None


def test_the_web_view_asks_its_page_for_the_relay(monkeypatch):
    monkeypatch.setattr(web, "PAGE", FakePage())
    with pytest.raises(Unavailable, match="no 3D view"):
        web.Grid3DWebView.open()


def test_open_on_the_desktop_uses_the_composition_roots_loader(monkeypatch):
    from preponderous.graphik.grid3d import view as viewModule
    from test_grid3d_ports import FakeStrataLoader

    display = FakeDisplay()
    display.strata = EVENT_NAMES
    loader = FakeStrataLoader(display)
    monkeypatch.setattr(viewModule.sys, "platform", "linux")
    monkeypatch.setattr(viewModule, "STRATA_LOADER", loader)
    view = Grid3DView.open(320, 200, "Game", headless=True, clock=lambda: 1.0)
    assert loader.opened == [(320, 200, "Game", True)]
    assert view.display is display and not view.isWindow and view.clock() == 1.0
    monkeypatch.setattr(viewModule, "STRATA_LOADER", FakeStrataLoader(reason="no GPU here"))
    with pytest.raises(Unavailable, match="no GPU here"):
        Grid3DView.open(320, 200)
