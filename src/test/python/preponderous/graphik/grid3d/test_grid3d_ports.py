"""grid3d's ports: each one's contract, run against a fake and against the
production adapters, so a fake can't drift from what the views really get.

No GPU, browser or network: the desktop adapters run over the stand-in
binding of test_grid3d_view, the browser ones over a stand-in page.
"""

import base64
import json
import sys
import types

import pytest

from preponderous.graphik.grid3d import CUBE, Camera, Label, Panel, Scene, Shape, Unavailable
from preponderous.graphik.grid3d import wire
from preponderous.graphik.grid3d.ports import (
    EventSource,
    GridRelay,
    PageObjects,
    SceneRenderer,
    StrataLoader,
    Surface,
)

from test_grid3d_view import fakeStrata


def aScene(camera=True):
    return Scene(shapes=[Shape(CUBE, (0, 0, 0), (1, 1, 1), (1, 1, 1, 1))],
                 labels=[Label("hi", 2, 2, 8)], panels=[Panel(0, 0, 10, 10)],
                 camera=Camera((0, 5, 5), (0, 0, 0)) if camera else None)


# -- fakes, one per port


class FakeDisplay:
    """SceneRenderer, EventSource and Surface for a view under test."""

    def __init__(self, events=()):
        self.drawn, self.events, self.sizes = [], list(events), []
        self.closed = 0
        self.strata = self.lib = self.engine = None

    def draw(self, scene, aspect, present=True):
        self.drawn.append((scene, aspect, present))

    def poll(self):
        events, self.events = self.events, []
        return events

    def resize(self, width, height):
        self.sizes.append((width, height))

    def savePng(self, path):
        raise Unavailable("a fake has no pixels")

    def close(self):
        self.closed += 1


class FakeStrataLoader:
    def __init__(self, display=None, reason=None):
        self.display, self.reason, self.opened = display or FakeDisplay(), reason, []

    def open(self, width, height, title, headless):
        if self.reason is not None:
            raise Unavailable(self.reason)
        self.opened.append((width, height, title, headless))
        return self.display


class FakePage:
    def __init__(self, **objects):
        self.objects = objects

    def get(self, name):
        return self.objects.get(name)


# -- the production adapters, over stand-ins


def adapters():
    # the adapters arrive in the next step; until then their cases skip
    return pytest.importorskip("preponderous.graphik.grid3d.adapters")


@pytest.fixture
def strataModule(monkeypatch):
    module = fakeStrata()
    monkeypatch.setitem(sys.modules, "strata", module)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    monkeypatch.setenv("GALLIUM_DRIVER", "llvmpipe")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    return module


class PageRelayStandIn:
    """window.StrataGridRelay through pygbag's bridge: strings in and out,
    refusing what the relay refuses."""

    def __init__(self):
        self.events, self.status = [], "ready"

    def request(self, options):
        json.loads(options)
        return self.status

    def state(self):
        return self.status

    def send(self, b64):
        try:
            wire.readHeader(base64.b64decode(b64))
        except wire.WireError as error:
            return error.status
        return 0

    def poll(self):
        events, self.events = self.events, []
        return json.dumps(events)

    def reducedMotion(self):
        return 0

    def close(self):
        self.status = "closed"


def productionDisplays(strataModule):
    module = adapters()
    BindingStrataLoader, RecordingRelay, RelayDisplay = (
        module.BindingStrataLoader, module.RecordingRelay, module.RelayDisplay)

    return [BindingStrataLoader().open(320, 200, "t", headless=True),
            RelayDisplay(RecordingRelay())]


def displays(request, strataModule):
    if request.param == "fake":
        return FakeDisplay()
    return productionDisplays(strataModule)[["desktop", "web"].index(request.param)]


@pytest.fixture(params=["fake", "desktop", "web"])
def display(request, strataModule):
    return displays(request, strataModule)


# -- SceneRenderer, EventSource, Surface


def test_a_display_is_a_renderer_an_event_source_and_a_surface(display):
    assert isinstance(display, SceneRenderer)
    assert isinstance(display, EventSource)
    assert isinstance(display, Surface)


def test_a_renderer_draws_a_checked_scene_with_or_without_a_camera(display):
    for scene in (aScene(), aScene(camera=False)):
        scene.checkLimits()
        assert display.draw(scene, 1.6) is None
        assert display.draw(scene, 1.6, present=False) is None


def test_an_event_source_hands_each_event_over_once(display):
    first = display.poll()
    assert isinstance(first, list)
    assert display.poll() == []


def test_a_surface_resizes_snapshots_or_refuses_in_words_and_closes(display, tmp_path):
    assert display.resize(400, 300) is None
    try:
        display.savePng(str(tmp_path / "shot.png"))
    except Unavailable as reason:
        assert str(reason)
    assert display.close() is None


# -- StrataLoader


@pytest.fixture(params=["fake", "binding"])
def loader(request, strataModule):
    if request.param == "fake":
        return FakeStrataLoader()
    BindingStrataLoader = adapters().BindingStrataLoader

    return BindingStrataLoader()


def test_a_loader_opens_a_display_that_shows_its_binding(loader):
    assert isinstance(loader, StrataLoader)
    opened = loader.open(320, 200, "Game", False)
    assert isinstance(opened, SceneRenderer) and isinstance(opened, EventSource)
    assert isinstance(opened, Surface)
    for name in ("strata", "lib", "engine"):
        assert hasattr(opened, name)


@pytest.mark.parametrize("which", ["fake", "binding"])
def test_a_loader_that_cant_open_says_why(which, monkeypatch):
    if which == "fake":
        loader = FakeStrataLoader(reason="no GPU")
    else:
        BindingStrataLoader = adapters().BindingStrataLoader

        monkeypatch.setitem(sys.modules, "strata", fakeStrata(engineError=RuntimeError("no GPU")))
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("STRATA_LIBRARY", raising=False)
        loader = BindingStrataLoader()
    with pytest.raises(Unavailable, match="no GPU"):
        loader.open(320, 200, "Game", False)


# -- GridRelay


@pytest.fixture(params=["recording", "platform"])
def relay(request):
    module = adapters()
    PlatformRelay, RecordingRelay = module.PlatformRelay, module.RecordingRelay

    if request.param == "recording":
        return RecordingRelay()
    return PlatformRelay(PageRelayStandIn())


def test_a_relay_answers_with_its_state_and_takes_messages(relay):
    assert isinstance(relay, GridRelay)
    state = relay.request({"canvas": "relay", "maxBytes": 10, "title": "t"})
    assert state == relay.state() == "ready"
    assert relay.send(wire.encodeHud([Label("x", 0, 0, 8)])) == 0
    assert relay.send(b"nope") == -1
    assert relay.poll() == [] and relay.reducedMotion() is False
    assert relay.close() is None


# -- PageObjects


@pytest.fixture(params=["fake", "pygbag"])
def page(request, monkeypatch):
    marker = types.SimpleNamespace(name="toggle")
    monkeypatch.setattr(sys, "platform", "emscripten")
    fake = types.ModuleType("platform")
    fake.window = types.SimpleNamespace(Graphik3D=marker)
    monkeypatch.setitem(sys.modules, "platform", fake)
    if request.param == "fake":
        return FakePage(Graphik3D=marker), marker
    PygbagPageObjects = adapters().PygbagPageObjects

    return PygbagPageObjects(), marker


def test_page_objects_are_found_by_name_and_missing_ones_are_none(page):
    objects, marker = page
    assert isinstance(objects, PageObjects)
    assert objects.get("Graphik3D") is marker
    assert objects.get("StrataGridRelay") is None


def test_outside_a_browser_there_are_no_page_objects(monkeypatch):
    PygbagPageObjects = adapters().PygbagPageObjects

    monkeypatch.setattr(sys, "platform", "linux")
    assert PygbagPageObjects().get("Graphik3D") is None
    assert FakePage().get("Graphik3D") is None
