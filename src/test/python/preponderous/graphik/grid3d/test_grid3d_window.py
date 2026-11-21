"""Grid3DView.setFullscreen / setTitle: the window calls games used to make
on view.engine themselves (apex, ophidian), now the view's own."""

import sys

import pytest

from preponderous.graphik.grid3d import Grid3DView
from preponderous.graphik.grid3d import web

from test_grid3d_view import fakeStrata


@pytest.fixture
def opened(monkeypatch):
    def make(calls=("strata_set_fullscreen", "strata_set_title"), headless=False):
        module = fakeStrata()
        module.lib.has = lambda name: name in calls
        monkeypatch.setitem(sys.modules, "strata", module)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("STRATA_LIBRARY", raising=False)
        return Grid3DView.open(320, 200, "Game", headless=headless)

    return make


def test_fullscreen_and_title_reach_the_engine(opened):
    view = opened()
    assert view.setFullscreen(1) is True and view.setFullscreen(0) is True
    assert view.setTitle("Level 2") is True
    calls = [(n, a) for n, a, _ in view.engine.calls if n in ("set_fullscreen", "set_title")]
    assert calls == [("set_fullscreen", (True,)), ("set_fullscreen", (False,)),
                     ("set_title", ("Level 2",))]


def test_a_strata_without_the_calls_says_no_and_calls_nothing(opened):
    view = opened(calls=())
    assert view.setFullscreen(True) is False and view.setTitle("x") is False
    assert [n for n, _, _ in view.engine.calls if n.startswith("set_") and n != "set_lighting"
            and n != "set_sun_direction"] == []


def test_a_closed_view_says_no(opened):
    view = opened()
    view.close()
    assert view.setFullscreen(True) is False and view.setTitle("x") is False


def test_the_browser_view_owns_neither_its_window_nor_its_title():
    view = web.Grid3DWebView(web.RecordingRelay(), 320, 200)
    assert view.setFullscreen(True) is False and view.setTitle("x") is False


def test_a_headless_view_has_no_fullscreen(opened):
    # Strata raises for fullscreen on a headless surface; the view says no
    view = opened(headless=True)
    assert view.setFullscreen(True) is False
    assert "set_fullscreen" not in view.engine.names()
