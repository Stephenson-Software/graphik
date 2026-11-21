"""What a frame costs in Python: the desktop view packs a scene's shapes
into the binding's RenderItems in one pass, the web view encodes a board's
shapes in one pass, and setBoard doesn't send the relay a board it already
has. Each fast path must give exactly what the slow one did, and fall back
to it for anything it can't take."""

import ctypes
import math
import types

import pytest

from preponderous.graphik.grid3d import CUBE, SPHERE, GridBoard, Piece, PieceStyle, Shape, Theme
from preponderous.graphik.grid3d import web, wire
from preponderous.graphik.grid3d.adapters.strata_engine import renderItems


class float3(ctypes.Array):
    _type_, _length_ = ctypes.c_float, 3


class float4(ctypes.Array):
    _type_, _length_ = ctypes.c_float, 4


class RenderItem(ctypes.Structure):
    """StrataRenderItem as the binding declares it (44 bytes)."""

    _fields_ = [("kind", ctypes.c_int32), ("position", float3), ("scale", float3), ("color", float4)]


def binding(item=RenderItem):
    return types.SimpleNamespace(RenderItem=item)


def shapes(count=50):
    return [Shape(CUBE if i % 2 else SPHERE, (i * 0.5, 0.1, -i * 0.25), (1.0, 0.2 + i / 100.0, 1.0),
                  (i / 50.0, 0.5, 1 - i / 50.0, 1.0)) for i in range(count)]


def asBytes(items):
    return b"".join(bytes(item) for item in items)


def test_render_items_are_packed_in_one_pass_byte_for_byte_as_one_by_one():
    scene = shapes()
    packed = renderItems(binding(), scene)
    assert isinstance(packed, ctypes.Array) and len(packed) == len(scene)
    oneByOne = [RenderItem(s.kind, s.position, s.scale, s.color) for s in scene]
    assert asBytes(packed) == asBytes(oneByOne)


def test_render_items_fall_back_for_a_three_part_colour_and_a_stand_in_binding():
    scene = shapes(3) + [Shape(CUBE, (0, 0, 0), (1, 1, 1), (0.5, 0.5, 0.5))]
    items = renderItems(binding(), scene)
    assert isinstance(items, list) and len(items) == 4  # RenderItem objects, as before
    assert asBytes(items[:3]) == asBytes(renderItems(binding(), scene[:3]))
    fake = renderItems(binding(lambda *fields: fields), scene[:2])
    assert fake == [(s.kind, s.position, s.scale, s.color) for s in scene[:2]]
    assert len(renderItems(binding(), [])) == 0


def test_render_items_match_the_real_binding():
    strata = pytest.importorskip("strata")
    scene = shapes()
    assert asBytes(renderItems(strata, scene)) == asBytes(
        [strata.RenderItem(s.kind, s.position, s.scale, s.color) for s in scene])


def slowBoard(scene, lights=()):
    out = [wire.header(wire.BOARD), wire.COUNTS.pack(len(scene), len(lights))]
    out += [wire._shape(s.kind, wire.WORLD, 0, 0, s.position, s.scale, s.color) for s in scene]
    out += [wire._light(wire.WORLD, 0, light) for light in lights]
    return b"".join(out)


def test_a_board_is_encoded_in_one_pass_byte_for_byte_as_shape_by_shape():
    scene = shapes(200)
    assert wire.encodeBoard(scene) == slowBoard(scene)
    # a 3-part colour goes the slow way, padded with alpha 1
    mixed = scene[:3] + [Shape(CUBE, (0, 0, 0), (1, 1, 1), (0.5, 0.5, 0.5))]
    assert wire.encodeBoard(mixed) == slowBoard(mixed)
    assert wire.encodeBoard([]) == slowBoard([])


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 2.0e6])
def test_the_one_pass_board_refuses_what_the_shape_by_shape_one_did(bad):
    for where in ("position", "scale"):
        scene = shapes(20)
        broken = scene[7]
        values = list(getattr(broken, where))
        values[1] = bad
        setattr(broken, where, tuple(values))
        with pytest.raises(wire.WireError) as error:
            wire.encodeBoard(scene)
        assert error.value.status == -5
    scene = shapes(20)
    scene[3].color = (0.5, bad if bad != 2.0e6 else math.nan, 0.5, 1.0)
    with pytest.raises(wire.WireError):
        wire.encodeBoard(scene)


def theme():
    return Theme(pieces={"pawn": PieceStyle(CUBE, (0.9, 0.9, 0.9))})


def test_set_board_does_not_resend_a_board_the_relay_already_has():
    relay = web.RecordingRelay()
    view = web.Grid3DWebView(relay, 900, 700)
    view.setBoard(GridBoard(8, 8, theme()))
    view.setPieces([Piece(1, 2, 2, "pawn")])
    kinds = lambda: [m[4] for m in relay.messages]  # noqa: E731
    first = kinds().count(wire.BOARD)
    view.setBoard(GridBoard(8, 8, theme()))  # the same board again, a new object
    assert kinds().count(wire.BOARD) == first == 1
    # the view and the pieces still go, as before
    assert kinds()[-2:] == [wire.VIEW, wire.PIECES]
    view.setBoard(GridBoard(8, 8, theme()), tint=(1.0, 0.0, 0.0))  # changed: sent
    assert kinds().count(wire.BOARD) == 2
