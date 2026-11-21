"""grid3d.view and grid3d.web keep every name they had in 0.5.3, as the
same objects as their new homes: games import from them (ophidian, apex,
Tic-Tak-Toe), and some keep classes to compare with what is raised."""

import pytest

from preponderous.graphik.grid3d import adapters, errors, events, geometry, view, web, wire

VIEW_NAMES = [
    "Animator", "Grid3DView", "INSTALL_HINT", "STRATA_PLATFORMS", "STRATA_VERSION",
    "Unavailable", "ViewGeometry", "_RENDER_ITEM", "cellScreenPosition", "labelBytes",
    "loadStrata", "pickCell", "projectToScreen", "renderItems",
]

# 0.5.3's web names, less the stdlib's SimpleNamespace and the private
# _NoBoard / _NO_BOARD stand-in, which moved into RelayDisplay
WEB_NAMES = [
    "ANCHOR", "Animator", "BOARD", "BRIDGE", "CLEAR_COLOR", "COUNTS", "DEFAULT_VIEW_ATTRIBUTE",
    "EVENTS", "EVENT_FINGER_CANCELED", "EVENT_FINGER_DOWN", "EVENT_FINGER_MOTION",
    "EVENT_FINGER_UP", "EVENT_KEY_DOWN", "EVENT_KEY_UP", "EVENT_MOUSE_BUTTON_DOWN",
    "EVENT_MOUSE_BUTTON_UP", "EVENT_MOUSE_MOTION", "EVENT_MOUSE_WHEEL", "EVENT_QUIT",
    "EVENT_RESIZED", "EVENT_TEXT_INPUT", "Event", "FAR_PLANE", "Grid3DWebView", "HEADER", "HUD",
    "KINDS", "LABEL", "LIGHT", "MAGIC", "MAX_ANCHORS", "MAX_COORDINATE", "MAX_HUD_ITEMS",
    "MAX_LIGHTS", "MAX_SHADOWED_LIGHTS", "MAX_SHAPES", "NEAR_PLANE", "PANEL", "PIECE", "PIECES",
    "PIECES_HEAD", "PlatformRelay", "RecordingRelay", "SHAPE", "STATUS", "SUN_DIRECTION",
    "TEMPLATE", "Unavailable", "VIEW", "VIEWS", "VIEW_BODY", "ViewGeometry", "WIRE_MAJOR",
    "WIRE_MINOR", "WORLD", "WireError", "_FLOAT_MAX", "_KEY_NAMES", "_MODS", "_checkCounts",
    "_finite", "_hudColor", "_labelText", "_light", "_rgba", "_shape", "_within", "_worldShapes",
    "buttonArea", "checkLights", "decode", "encodeBoard", "encodeHud", "encodePieces",
    "encodeView", "header", "pageObject", "parseArea", "pygameKey", "readHeader", "set3D",
    "templatePath", "toPygameEvents", "touchScreen", "wants3D",
]


@pytest.mark.parametrize("name", VIEW_NAMES)
def test_grid3d_view_keeps_its_names(name):
    assert hasattr(view, name)


@pytest.mark.parametrize("name", WEB_NAMES)
def test_grid3d_web_keeps_its_names(name):
    assert hasattr(web, name)


def test_moved_names_are_the_same_objects_as_their_new_homes():
    for module in (view, web):
        assert module.Unavailable is errors.Unavailable
        assert module.ViewGeometry is geometry.ViewGeometry
    assert view.loadStrata is adapters.binding_strata_loader.loadStrata
    assert view.STRATA_VERSION == adapters.binding_strata_loader.STRATA_VERSION
    assert view.renderItems is adapters.strata_engine.renderItems
    assert web.PlatformRelay is adapters.PlatformRelay
    assert web.RecordingRelay is adapters.RecordingRelay
    for name in ("encodeBoard", "encodeHud", "encodePieces", "encodeView", "decode",
                 "readHeader", "WireError", "STATUS"):
        assert getattr(web, name) is getattr(wire, name)
    for name in ("Event", "EVENTS", "toPygameEvents", "pygameKey", "EVENT_QUIT"):
        assert getattr(web, name) is getattr(events, name)
