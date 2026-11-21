"""grid3d's scene description, board, pieces and animation: pure Python, no GPU."""

import importlib
import sys

import pytest

from preponderous.graphik.grid3d import (
    BED_TOP,
    CAPSULE,
    CUBE,
    MAX_POINT_LIGHTS,
    SPHERE,
    Animator,
    GridBoard,
    Light,
    Piece,
    PieceStyle,
    Scene,
    SceneLimitError,
    Shape,
    Theme,
    cellCenter,
    fitCamera,
    interpolatePosition,
)


def theme():
    return Theme(
        pieces={
            "pawn": PieceStyle(SPHERE, (0.9, 0.2, 0.2), height=0.5, size=0.8),
            "gem": PieceStyle(CAPSULE, (0.2, 0.9, 0.9), height=0.7, size=0.4, glow=(2.0, 1.5)),
            "body": PieceStyle(SPHERE, (0.4, 0.8, 0.4), height=0.5, size=0.78, tones=(0.92, 0.78)),
        }
    )


# -- importing


def test_importing_grid3d_loads_neither_strata_nor_pygame(monkeypatch):
    # monkeypatch puts the deleted modules back afterwards, so later tests
    # and the modules they imported keep one copy of each class (a second
    # copy of grid3d would raise an Unavailable their imports don't match)
    for name in list(sys.modules):
        if name == "strata" or name.startswith("strata.") or name.startswith("preponderous.graphik.grid3d"):
            monkeypatch.delitem(sys.modules, name)
    graphik = sys.modules.get("preponderous.graphik")
    if graphik is not None and hasattr(graphik, "grid3d"):
        monkeypatch.delattr(graphik, "grid3d")
    pygameLoaded = "pygame" in sys.modules
    importlib.import_module("preponderous.graphik.grid3d")
    assert "strata" not in sys.modules
    assert ("pygame" in sys.modules) == pygameLoaded


# -- the board


def test_cells_are_centred_on_the_origin():
    assert cellCenter(0, 0, 3, 3) == (-1.0, -1.0)
    assert cellCenter(1, 1, 3, 3) == (0.0, 0.0)
    assert cellCenter(3, 0, 4, 2) == (1.5, -0.5)


def test_a_board_has_one_tile_per_cell_plus_a_four_sided_frame():
    board = GridBoard(5, 3, theme())
    shapes = board.boardShapes()
    assert len(shapes) == 5 * 3 + 4
    assert all(shape.kind == CUBE for shape in shapes)


def test_tiles_are_checkered_and_a_tint_blends_every_tile():
    board = GridBoard(2, 1, theme())
    plain = board.boardShapes()
    assert plain[0].color != plain[1].color
    tinted = board.boardShapes(tint=(1.0, 0.0, 0.0))
    assert all(t.color[0] > p.color[0] for t, p in zip(tinted[:2], plain[:2]))


def test_a_theme_without_frame_or_alternate_draws_plain_tiles_only():
    board = GridBoard(2, 2, Theme(alternate=None, frame=None))
    shapes = board.boardShapes()
    assert len(shapes) == 4
    assert len({shape.color for shape in shapes}) == 1


def test_a_board_needs_a_cell():
    with pytest.raises(ValueError):
        GridBoard(0, 3)


# -- pieces


def test_a_piece_stands_on_its_cell():
    board = GridBoard(3, 3, theme())
    shapes, lights = board.pieceShapes([Piece("p", 2, 0, "pawn")])
    (shape,) = shapes
    assert (shape.position[0], shape.position[2]) == (1.0, -1.0)
    assert shape.position[1] - shape.scale[1] / 2 == pytest.approx(BED_TOP)
    assert lights == []


def test_a_glowing_style_adds_a_light_above_the_piece():
    board = GridBoard(3, 3, theme())
    _, lights = board.pieceShapes([Piece("g", 1, 1, "gem")])
    (light,) = lights
    assert (light.position[0], light.position[2]) == (0.0, 0.0)
    assert light.position[1] > BED_TOP + 0.7


def test_scale_and_colour_override_the_style():
    board = GridBoard(3, 3, theme())
    (shape,), _ = board.pieceShapes([Piece("p", 0, 0, "pawn", scale=0.5, color=(0.1, 0.2, 0.3))])
    assert shape.scale[0] == pytest.approx(0.4)
    assert shape.color[:3] == (0.1, 0.2, 0.3)


def test_extras_are_drawn_from_the_pieces_current_position():
    def eyes(piece, x, z, baseY):
        return [Shape(SPHERE, (x + piece.facing[0] * 0.3, baseY + 0.4, z), (0.2, 0.2, 0.2), (1, 1, 1, 1))]

    t = theme()
    t.pieces["head"] = PieceStyle(SPHERE, (0.5, 0.9, 0.5), extras=eyes)
    board = GridBoard(3, 3, t)
    shapes, _ = board.pieceShapes([Piece("h", 1, 1, "head", facing=(1, 0))], positions={"h": (0.5, 0.0)})
    assert shapes[1].position[0] == pytest.approx(0.8)


def test_chained_neighbours_are_bridged_and_gaps_are_not():
    board = GridBoard(5, 1, theme())
    pieces = [
        Piece("a", 0, 0, "body", chain="snake", link=0),
        Piece("b", 1, 0, "body", chain="snake", link=1),
        Piece("c", 3, 0, "body", chain="snake", link=2),  # not next to b
    ]
    shapes, _ = board.pieceShapes(pieces)
    bridges = shapes[3:]
    assert len(bridges) == 1
    assert bridges[0].position[0] == pytest.approx(-1.5)  # between cells 0 and 1
    assert bridges[0].scale[0] == pytest.approx(1.0)  # spans the gap along x


def test_chained_pieces_alternate_tones():
    board = GridBoard(3, 1, theme())
    pieces = [Piece(i, i, 0, "body", chain="s", link=i) for i in range(2)]
    shapes, _ = board.pieceShapes(pieces)
    assert shapes[0].color != shapes[1].color


def test_bad_pieces_are_rejected_with_their_id():
    board = GridBoard(3, 3, theme())
    with pytest.raises(ValueError, match="off the 3x3 board"):
        board.checkPieces([Piece("x", 3, 0, "pawn")])
    with pytest.raises(ValueError, match="share the id"):
        board.checkPieces([Piece("x", 0, 0, "pawn"), Piece("x", 1, 0, "pawn")])
    with pytest.raises(KeyError, match="no PieceStyle named 'ghost'"):
        board.checkPieces([Piece("x", 0, 0, "ghost")])


# -- the camera


@pytest.mark.parametrize("columns, rows", [(3, 3), (5, 5), (16, 16), (20, 8), (8, 20)])
def test_the_camera_sees_every_corner_of_the_board(columns, rows):
    camera = fitCamera(columns, rows, aspect=900 / 700)
    ex, ey, ez = camera.eye
    tx, ty, tz = camera.target
    forward = (tx - ex, ty - ey, tz - ez)
    import math

    norm = math.sqrt(sum(c * c for c in forward))
    forward = tuple(c / norm for c in forward)
    half = math.radians(camera.fovDegrees) / 2
    for cx in (-columns / 2 - 0.4, columns / 2 + 0.4):
        for cz in (-rows / 2 - 0.4, rows / 2 + 0.4):
            to = (cx - ex, 0.0 - ey, cz - ez)
            dist = math.sqrt(sum(c * c for c in to))
            cosAngle = sum(a * b for a, b in zip(forward, to)) / dist
            # inside the vertical field of view (the horizontal one is wider)
            assert math.acos(min(1.0, cosAngle)) < half * 1.35


def test_the_camera_looks_down_from_the_south():
    camera = fitCamera(5, 5)
    assert camera.eye[1] > camera.target[1]
    assert camera.eye[2] > camera.target[2]


# -- limits


def test_too_many_lights_are_rejected():
    board = GridBoard(1, 1)
    lights = [Light((0, 1, 0), (1, 1, 1), 1, 1)] * (MAX_POINT_LIGHTS + 1)
    with pytest.raises(SceneLimitError, match="at most 32"):
        board.scene(lights=lights)


def test_too_many_shadow_casting_lights_are_rejected():
    lights = [Light((0, 1, 0), (1, 1, 1), 1, 1, castShadows=True)] * 5
    with pytest.raises(SceneLimitError, match="shadow"):
        Scene(lights=lights).checkLimits()


def test_the_largest_real_board_stays_inside_the_limits():
    # ophidian's level 6: a 16x16 board, a long snake and some pickups
    t = theme()
    board = GridBoard(16, 16, t)
    snake = [Piece(("s", i), i % 16, i // 16, "body", chain="s", link=i) for i in range(60)]
    pickups = [Piece(("g", i), i, 10, "gem") for i in range(8)]
    scene = board.scene(snake + pickups)
    scene.checkLimits()
    assert len(scene.lights) == 8


# -- animation


def test_interpolation_is_clamped():
    assert interpolatePosition((0, 0), (1, 2), 0.5) == (0.5, 1.0)
    assert interpolatePosition((0, 0), (1, 2), -1) == (0, 0)
    assert interpolatePosition((0, 0), (1, 2), 3) == (1, 2)


def animator(**kwargs):
    return Animator(lambda c, r: cellCenter(c, r, 5, 5), **kwargs)


def test_a_piece_slides_to_its_new_cell_over_one_tick():
    a = animator()
    a.update([Piece("p", 0, 0, "pawn")], now=0.0, tickSeconds=0.2)
    a.update([Piece("p", 1, 0, "pawn")], now=0.2, tickSeconds=0.2)
    assert a.positions(0.2)["p"] == (-2.0, -2.0)
    assert a.positions(0.3)["p"] == pytest.approx((-1.5, -2.0))
    assert a.positions(0.5)["p"] == (-1.0, -2.0)
    assert a.settled(0.4)


def test_a_new_piece_appears_on_its_cell():
    a = animator()
    a.update([Piece("p", 2, 2, "pawn")], now=0.0, tickSeconds=0.2)
    assert a.positions(0.0)["p"] == (0.0, 0.0)


def test_a_teleport_or_an_opted_out_piece_jumps():
    a = animator()
    a.update([Piece("p", 0, 0, "pawn"), Piece("q", 0, 1, "pawn")], now=0.0, tickSeconds=0.2)
    a.update(
        [Piece("p", 4, 0, "pawn"), Piece("q", 1, 1, "pawn", interpolate=False)],
        now=0.2,
        tickSeconds=0.2,
    )
    positions = a.positions(0.25)
    assert positions["p"] == (2.0, -2.0)  # wrapped across the board: no slide
    assert positions["q"] == (-1.0, -1.0)


def test_reduced_motion_snaps_every_piece():
    a = animator(reducedMotion=True)
    a.update([Piece("p", 0, 0, "pawn")], now=0.0, tickSeconds=0.2)
    a.update([Piece("p", 1, 0, "pawn")], now=0.2, tickSeconds=0.2)
    assert a.positions(0.25)["p"] == (-1.0, -2.0)


def test_a_slide_interrupted_by_the_next_tick_continues_from_where_it_was_drawn():
    a = animator()
    a.update([Piece("p", 0, 0, "pawn")], now=0.0, tickSeconds=0.2)
    a.update([Piece("p", 1, 0, "pawn")], now=0.2, tickSeconds=0.2)
    a.update([Piece("p", 2, 0, "pawn")], now=0.3, tickSeconds=0.2)  # halfway
    assert a.positions(0.3)["p"] == pytest.approx((-1.5, -2.0))


def test_removed_pieces_are_forgotten():
    a = animator()
    a.update([Piece("p", 0, 0, "pawn")], now=0.0, tickSeconds=0.2)
    a.update([], now=0.2, tickSeconds=0.2)
    assert a.positions(0.3) == {}


def test_a_snapped_tick_puts_every_piece_on_its_cell():
    # a restart or a new level: nothing slides over from the old board
    a = animator()
    a.update([Piece("p", 0, 0, "pawn")], now=0.0, tickSeconds=0.2)
    a.update([Piece("p", 1, 0, "pawn")], now=0.2, tickSeconds=0.2, snap=True)
    assert a.positions(0.25)["p"] == (-1.0, -2.0)
    a.update([Piece("p", 2, 0, "pawn")], now=0.4, tickSeconds=0.2)
    assert a.positions(0.5)["p"] == pytest.approx((-0.5, -2.0))  # slides again


def test_a_tick_before_the_last_slide_finished_still_slides_a_one_cell_step():
    # ticks that come back to back (a busy frame, a speed-up): the step is
    # measured from cell to cell, so a turn isn't mistaken for a teleport
    a = animator()
    a.update([Piece("p", 0, 0, "pawn")], now=0.0, tickSeconds=0.2)
    a.update([Piece("p", 0, 1, "pawn")], now=0.2, tickSeconds=0.2)
    a.update([Piece("p", 1, 1, "pawn")], now=0.2, tickSeconds=0.2)  # no time passed
    assert a.positions(0.2)["p"] == (-2.0, -2.0)  # still drawn where it was
    assert a.positions(0.3)["p"] == pytest.approx((-1.5, -1.5))
    assert a.positions(0.4)["p"] == (-1.0, -1.0)
