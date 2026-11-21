"""The grid relay's wire format 1.0, held to golden bytes shared with Strata.

golden/wire-1.0.hex holds one message of each kind, encoded by grid3d.web
from the scene below. Strata's tests/unit/test_grid_relay.cpp reads the same
bytes (tests/unit/grid_relay_wire_1_0.inc, made from this file) with the
relay's own parser, so the encoder here and the reader there are checked
against one fixture: a change to either side that the other doesn't make
fails one of the two suites.

To rewrite the fixture after a deliberate format change (a new minor, a new
major): GRAPHIK_WRITE_WIRE_GOLDEN=1 python -m pytest -k wire_golden, then
regenerate Strata's .inc from it (its header says how).
"""

import os

import pytest

from preponderous.graphik.grid3d import (
    CAPSULE,
    CUBE,
    SPHERE,
    GridBoard,
    Label,
    Light,
    Panel,
    Piece,
    PieceStyle,
    Shape,
    Theme,
)
from preponderous.graphik.grid3d import web

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "wire-1.0.hex")
ORDER = ("board", "view", "pieces", "hud")


def eyes(piece, x, z, baseY):
    return [Shape(SPHERE, (x + 0.15, baseY + 0.5, z + 0.3), (0.12, 0.12, 0.12), (1.0, 1.0, 1.0, 1.0))]


THEME = Theme(pieces={
    "head": PieceStyle(SPHERE, (0.2, 0.8, 0.3), height=0.5, size=0.8, extras=eyes),
    "body": PieceStyle(CUBE, (0.1, 0.6, 0.2), height=0.4, size=0.7, tones=(0.9, 1.0)),
    "gem": PieceStyle(CAPSULE, (0.95, 0.8, 0.2), height=0.6, size=0.4, glow=(2.0, 1.5)),
})
BOARD = GridBoard(3, 2, THEME)
PIECES = [
    Piece("h", 1, 0, "head", chain="s", link=0),
    Piece("b", 1, 1, "body", chain="s", link=1, scale=0.8),
    Piece("g", 2, 1, "gem"),
]
# the head and body slide one cell east; the gem stands still
TRACKS = {"h": ((-1.0, -0.5), (0.0, -0.5)), "b": ((-1.0, 0.5), (0.0, 0.5))}


def messages():
    return {
        "board": web.encodeBoard(BOARD.boardShapes(),
                                 [Light((0.0, 3.0, 0.0), (1.0, 0.9, 0.8), 6.0, 1.2, True)]),
        "view": web.encodeView(BOARD.camera(4 / 3.0)),
        "pieces": web.encodePieces(BOARD, PIECES, TRACKS, 0.25),
        # non-ASCII text: an em dash and two accented letters, 17 bytes of UTF-8
        "hud": web.encodeHud([Label("Score 3 — été", 12.0, 8.0, 16.0)],
                             [Panel(4.0, 4.0, 200.0, 32.0, (0.0, 0.0, 0.0, 0.6))]),
    }


def readGolden():
    golden = {}
    with open(GOLDEN, encoding="ascii") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                name, data = line.split()
                golden[name] = bytes.fromhex(data)
    return golden


def writeGolden(encoded):
    with open(GOLDEN, "w", encoding="ascii") as handle:
        handle.write("# Grid relay wire format 1.0: one message of each kind, encoded by graphik's\n")
        handle.write("# grid3d.web (test_grid3d_wire_golden.py). Strata's relay reads the same bytes\n")
        handle.write("# (tests/unit/grid_relay_wire_1_0.inc). <kind> <hex>, one message a line.\n")
        for name in ORDER:
            handle.write("%s %s\n" % (name, encoded[name].hex()))


def test_the_encoder_writes_the_golden_bytes():
    encoded = messages()
    if os.environ.get("GRAPHIK_WRITE_WIRE_GOLDEN"):
        writeGolden(encoded)
    golden = readGolden()
    assert sorted(golden) == sorted(ORDER)
    for name in ORDER:
        assert encoded[name] == golden[name], "%s differs from golden/wire-1.0.hex" % name


def test_the_golden_bytes_read_back_as_the_scene():
    golden = readGolden()
    kind, board = web.decode(golden["board"])
    assert kind == web.BOARD
    assert len(board["shapes"]) == 6 + 4  # six tiles, four frame sides
    assert board["lights"][0]["castShadows"] and board["lights"][0]["radius"] == pytest.approx(6.0)

    kind, view = web.decode(golden["view"])
    assert kind == web.VIEW
    camera = BOARD.camera(4 / 3.0)
    assert view["eye"] == pytest.approx(camera.eye)
    assert view["target"] == pytest.approx(camera.target)
    assert view["sun"] == pytest.approx(web.SUN_DIRECTION)

    kind, pieces = web.decode(golden["pieces"])
    assert kind == web.PIECES
    assert pieces["tickSeconds"] == 0.25
    assert pieces["anchors"] == [(-1.0, -0.5, 0.0, -0.5), (-1.0, 0.5, 0.0, 0.5), (1.0, 0.5, 1.0, 0.5)]
    attach = [(s["attach"], s["a"], s["b"]) for s in pieces["shapes"]]
    # head and its eye on anchor 0, the body on 1, the gem on 2, then the bridge from 0 to 1
    assert attach == [(web.PIECE, 0, 0), (web.PIECE, 0, 0), (web.PIECE, 1, 0), (web.PIECE, 2, 0),
                      (web.BRIDGE, 0, 1)]
    assert pieces["shapes"][1]["position"] == pytest.approx((0.15, 0.5, 0.3))  # the eye, from its piece
    assert [(l["attach"], l["a"]) for l in pieces["lights"]] == [(web.PIECE, 2)]

    kind, hud = web.decode(golden["hud"])
    assert kind == web.HUD
    assert hud["labels"][0]["text"] == "Score 3 — été"
    assert hud["panels"][0]["rect"] == (4.0, 4.0, 200.0, 32.0)
    # 8 header + 8 counts + 32 panel + 32 label + 17 text bytes padded to 20
    assert len(golden["hud"]) == 100
