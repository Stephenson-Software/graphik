"""Picking at board edges and from extreme cameras, and Animator timing at
its edges. Pure Python."""

import math

import pytest

from preponderous.graphik.grid3d import (
    Animator,
    Camera,
    GridBoard,
    Piece,
    Viewport,
    cellScreenPosition,
    pickCell,
    pickPoint,
    projectToScreen,
)

W, H = 800, 600


def orbit(yawDegrees, pitchDegrees, distance=12.0, target=(0.0, 0.0, 0.0), fov=42.0):
    yaw, pitch = math.radians(yawDegrees), math.radians(pitchDegrees)
    eye = (target[0] + distance * math.cos(pitch) * math.sin(yaw),
           target[1] + distance * math.sin(pitch),
           target[2] + distance * math.cos(pitch) * math.cos(yaw))
    return Camera(eye, target, fov)


# -- picking


@pytest.mark.parametrize("yaw,pitch", [(0, 55), (90, 30), (200, 75), (315, 12), (45, 89.5), (0, 3)])
def test_every_cells_inner_corners_pick_that_cell_from_any_camera(yaw, pitch):
    board = GridBoard(7, 5)
    camera = orbit(yaw, pitch, distance=30.0)
    for column in range(7):
        for row in range(5):
            cx, cz = board.cellCenter(column, row)
            for dx in (-0.49, 0.49):
                for dz in (-0.49, 0.49):
                    at = projectToScreen(camera, (cx + dx, 0.0, cz + dz), W, H)
                    assert at is not None
                    assert pickCell(camera, board, at[0], at[1], W, H) == (column, row)


def test_a_boards_edges_are_half_open_like_its_cells():
    board = GridBoard(4, 3)
    assert board.cellAt(-2.0, -1.5) == (0, 0)  # the west and north edges are in
    assert board.cellAt(1.999, 1.499) == (3, 2)
    assert board.cellAt(2.0, 0.0) is None  # the east and south edges are out
    assert board.cellAt(0.0, 1.5) is None
    assert board.cellAt(-2.0001, 0.0) is None


def test_a_viewport_picks_only_its_own_cells_even_at_the_boards_edge():
    board = GridBoard(10, 10, viewport=Viewport.around(0, 0, 1))  # reaches off the board
    assert board.cellAt(0.0, 0.0) == (0, 0)
    assert board.cellAt(-1.0, -1.0) is None  # cell (-1, -1): in the window, off the board


def test_a_pixel_on_the_horizon_or_with_no_pointer_picks_nothing():
    board = GridBoard(4, 4)
    level = Camera((0.0, 0.0, 10.0), (0.0, 0.0, 0.0))  # looking along the plane
    assert pickPoint(level, W / 2, H / 2, W, H) is None
    assert pickCell(orbit(0, 55), board, None, 10, W, H) is None


@pytest.mark.parametrize("camera", [
    Camera((0.0, 10.0, 0.0), (0.0, 0.0, 0.0)),   # straight down
    Camera((1.0, -5.0, 2.0), (1.0, 5.0, 2.0)),    # straight up
    Camera((1.0, 2.0, 3.0), (1.0, 2.0, 3.0)),     # eye on the target
])
def test_a_camera_strata_cant_aim_is_refused_in_words(camera):
    with pytest.raises(ValueError, match="camera"):
        pickCell(camera, GridBoard(3, 3), W / 2, H / 2, W, H)


def test_a_cell_behind_the_camera_has_no_screen_position():
    board = GridBoard(9, 9)
    inside = Camera((0.0, 0.5, 0.0), (0.0, 0.4, -10.0))  # standing on the board, looking north
    assert cellScreenPosition(inside, board, 4, 8, W, H) is None  # the south edge, behind
    assert cellScreenPosition(inside, board, 4, 0, W, H) is not None


# -- Animator


def animator():
    board = GridBoard(5, 5)
    return Animator(board.cellCenter), board


def test_a_tick_of_zero_or_less_or_nan_places_pieces_at_once():
    for tick in (0.0, -1.0, float("nan")):
        a, board = animator()
        a.update([Piece(1, 0, 0, "x")], 0.0, 0.5)
        a.update([Piece(1, 1, 0, "x")], 1.0, tick)
        assert a.settled(1.0)
        assert a.positions(1.0)[1] == board.cellCenter(1, 0)


def test_a_time_before_the_tick_began_is_its_start_not_beyond():
    a, board = animator()
    a.update([Piece(1, 0, 0, "x")], 0.0, 0.5)
    a.update([Piece(1, 1, 0, "x")], 10.0, 0.5)
    assert a.positions(9.0)[1] == board.cellCenter(0, 0)  # a clock read before the update
    assert a.positions(99.0)[1] == board.cellCenter(1, 0)


def test_a_diagonal_step_jumps_and_a_straight_one_slides():
    a, board = animator()
    a.update([Piece(1, 2, 2, "x"), Piece(2, 0, 0, "x")], 0.0, 0.5)
    a.update([Piece(1, 3, 3, "x"), Piece(2, 1, 0, "x")], 1.0, 0.5)
    at = a.positions(1.0)
    assert at[1] == board.cellCenter(3, 3)  # two cells' worth of travel: over maxSlideCells
    assert at[2] == board.cellCenter(0, 0)  # one cell: slides from where it was


def test_pieces_with_any_hashable_id_are_tracked():
    a, board = animator()
    ids = [("snake", 0), "food", 7, frozenset({1})]
    a.update([Piece(i, n, 0, "x") for n, i in enumerate(ids)], 0.0, 0.0)
    assert set(a.positions(0.0)) == set(ids)
