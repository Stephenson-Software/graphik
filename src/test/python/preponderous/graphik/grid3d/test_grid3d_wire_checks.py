"""Text the font can't draw, and the wire encoders refusing what Strata's
grid relay would refuse (WIRE.md, "Errors"), with the relay's status."""

import pytest

from preponderous.graphik.grid3d import (
    CUBE,
    Camera,
    GridBoard,
    Label,
    Light,
    Panel,
    Piece,
    PieceStyle,
    Shape,
    Theme,
    measureText,
    wrapText,
)
from preponderous.graphik.grid3d import web
from preponderous.graphik.grid3d.view import labelBytes

# -- text the font can't draw


def test_text_is_measured_in_characters_as_strata_draws_them_not_bytes():
    # one '?' a character outside the font, a multi-byte UTF-8 sequence included
    assert measureText("été", 10) == 30
    assert measureText("\U0001F40D!", 10) == 20  # an astral-plane snake is one cell
    assert measureText("a\0b", 10) == 20  # a NUL draws nothing on either backend
    assert wrapText("ééé éé", 40, 10) == ["ééé", "éé"]


def test_label_bytes_are_utf8_without_nuls_and_with_lone_surrogates_as_question_marks():
    assert labelBytes("a\0bé") == b"ab\xc3\xa9"
    assert labelBytes("x\ud800y") == b"x?y"
    assert web._labelText("x\ud800y") == b"x?y"


def test_a_very_long_label_is_cut_on_a_character_boundary():
    data = web._labelText("é" * 40000)  # 80000 bytes of two-byte characters
    assert len(data) <= 65535
    data.decode("utf-8")  # no half character at the end


# -- the encoders refuse what the relay refuses (WIRE.md, "Errors")


def board():
    return GridBoard(3, 3, Theme(pieces={"p": PieceStyle(CUBE, (0.5, 0.5, 0.5), glow=(2.0, 1.0))}))


@pytest.mark.parametrize("make,status", [
    (lambda: web.encodeBoard([], [Light((0, 1, 0), (1, 1, 1), 0.0, 1.0)]), -5),           # no range
    (lambda: web.encodeBoard([], [Light((0, 1, 0), (1, -1, 1), 2.0, 1.0)]), -5),          # negative colour
    (lambda: web.encodeBoard([], [Light((0, 1, 0), (1, 1, 1), 2.0, -1.0)]), -5),          # negative intensity
    (lambda: web.encodeBoard([], [Light((0, 1, 0), (1, 1, 1), 2.0, 1.0, True)] * 5), -6),  # five shadows
    (lambda: web.encodeBoard([], [Light((0, 1, 0), (1, 1, 1), 2.0, 1.0)] * 33), -6),
    (lambda: web.encodeBoard([Shape(CUBE, (float("nan"), 0, 0), (1, 1, 1), (1, 1, 1, 1))]), -5),
    (lambda: web.encodeBoard([Shape(CUBE, (2e6, 0, 0), (1, 1, 1), (1, 1, 1, 1))]), -5),
    (lambda: web.encodeHud([], [Panel(0, 0, 10, 10, (0, 0, 0, 1.5))]), -5),                # alpha over 1
    (lambda: web.encodeHud([Label("x", 0, 0, 16, (-0.1, 1, 1, 1))]), -5),
    (lambda: web.encodeHud([Label("x", float("inf"), 0, 16)]), -5),
    (lambda: web.encodeHud([Label("x", 0, 0, 16)] * 4097), -6),
    (lambda: web.encodeView(Camera((1, 2, 3), (1, 2, 3))), -5),
    (lambda: web.encodeView(Camera((0, 5, 5), (0, 0, 0), 180.0)), -5),
    (lambda: web.encodePieces(board(), [Piece(1, 0, 0, "p")], {}, -0.5), -5),
    (lambda: web.encodePieces(board(), [Piece(1, 0, 0, "p")], {1: ((3e6, 0.0), (0.0, 0.0))}, 0.5), -5),
])
def test_the_encoders_refuse_what_the_relay_would_with_its_status(make, status):
    with pytest.raises(web.WireError) as error:
        make()
    assert error.value.status == status


def test_the_relays_limits_are_reached_but_not_passed_by_a_real_board():
    big = GridBoard(64, 64, mergeTiles=False)
    message = web.encodeBoard(big.boardShapes(), [Light((0, 3, 0), (1, 1, 1), 5.0, 1.0, True)] * 4)
    kind, contents = web.decode(message)
    assert len(contents["shapes"]) == 64 * 64 + 4


def test_a_web_view_refuses_a_bad_hud_before_sending_it():
    relay = web.RecordingRelay()
    view = web.Grid3DWebView.open(400, 300, relay=relay)
    view.setBoard(board())
    sent = len(relay.messages)
    with pytest.raises(web.WireError):
        view.setLabels([], [Panel(0, 0, 10, 10, (0, 0, 0, 2.0))])
    assert len(relay.messages) == sent
