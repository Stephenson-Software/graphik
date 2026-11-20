"""grid3d's shared helpers: picking, text, buttons, the Graphik stand-in, and
the board's options (own tiles, merged tiles, a viewport, the hover slab,
bridge pairs). Pure Python, no GPU."""

import math

import pytest

from preponderous.graphik import Graphik
from preponderous.graphik.grid3d import (
    BED_TOP,
    CUBE,
    SPHERE,
    Button,
    GridBoard,
    Piece,
    PieceStyle,
    ScreenRecorder,
    Theme,
    Tile,
    Viewport,
    centredLabel,
    cellScreenPosition,
    fitText,
    hoverColor,
    measureText,
    pickCell,
    pickPoint,
    projectToScreen,
    wrapText,
)


def chainTheme():
    return Theme(
        pieces={
            "pawn": PieceStyle(SPHERE, (0.9, 0.2, 0.2)),
            "body": PieceStyle(SPHERE, (0.4, 0.8, 0.4), tones=(0.92, 0.78)),
        }
    )


# -- picking


@pytest.mark.parametrize("size", [(800, 600), (600, 800), (1280, 720)])
@pytest.mark.parametrize("columns,rows", [(3, 3), (8, 5), (20, 30)])
def test_projecting_a_cells_centre_and_picking_it_back_finds_that_cell(size, columns, rows):
    width, height = size
    board = GridBoard(columns, rows)
    camera = board.camera(width / float(height))
    for row in range(rows):
        for column in range(columns):
            at = cellScreenPosition(camera, board, column, row, width, height)
            assert at is not None
            assert pickCell(camera, board, at[0], at[1], width, height) == (column, row)


def test_a_point_behind_the_camera_has_no_screen_position():
    board = GridBoard(4, 4)
    camera = board.camera()
    behind = tuple(2 * e - t for e, t in zip(camera.eye, camera.target))
    assert projectToScreen(camera, behind, 800, 600) is None


def test_the_cameras_target_lands_in_the_middle_of_the_window():
    camera = GridBoard(5, 5).camera(4 / 3.0)
    x, y = projectToScreen(camera, camera.target, 800, 600)
    assert (x, y) == pytest.approx((400, 300))


def test_pixels_off_the_board_or_above_the_horizon_pick_no_cell():
    board = GridBoard(3, 3)
    camera = board.camera(800 / 600.0)
    assert pickCell(camera, board, 5, 5, 800, 600) is None
    assert pickCell(camera, board, 795, 595, 800, 600) is None
    assert pickCell(camera, board, None, None, 800, 600) is None
    # the top row of pixels of a camera tilted down still meets the plane far
    # away; one looking level never does
    level = type(camera)(eye=(0.0, 1.0, 5.0), target=(0.0, 1.0, 0.0))
    assert pickPoint(level, 400, 100, 800, 600) is None


def test_the_gap_between_two_tiles_belongs_to_a_cell():
    board = GridBoard(2, 1, Theme(tileGap=0.2))
    camera = board.camera(1.0)
    # the world point exactly between the two tiles' centres, just right of it
    at = projectToScreen(camera, (0.001, BED_TOP, 0.0), 600, 600)
    assert pickCell(camera, board, at[0], at[1], 600, 600) == (1, 0)


# -- text


def test_text_is_one_pixel_size_wide_per_character_as_strata_draws_it():
    assert measureText("Score", 10) == 50
    assert measureText("", 10) == 0
    # a non-ASCII character is still one cell (Strata draws one '?')
    assert measureText("café", 8) == 32
    # several lines: the longest one
    assert measureText("ab\nabcd\nabc", 5) == 20


def test_fit_text_cuts_with_an_ellipsis():
    assert fitText("short", 900, 10) == "short"
    cut = fitText("x" * 200, 236, 10)
    assert cut.endswith("...") and len(cut) == 20


def test_wrapping_packs_words_greedily_and_keeps_empty_lines_and_long_words():
    assert wrapText("the quick brown fox", 90, 10) == ["the quick", "brown fox"]
    assert wrapText(["one two", "", "three"], 30, 10) == ["one", "two", "", "three"]
    assert wrapText("a supercalifragilistic word", 60, 10) == ["a", "supercalifragilistic", "word"]
    assert wrapText("line one\nline two", 1000, 10) == ["line one", "line two"]
    assert wrapText("", 100, 10) == [""]


def test_a_centred_label_is_centred_on_its_point():
    label = centredLabel("Hello", 400, 300, 20)
    assert label.x + measureText("Hello", 20) / 2 == 400
    assert label.y == 290
    assert centredLabel("Hello", 400, 300, 20, rise=0.45).y == pytest.approx(291)
    assert centredLabel("Hello", 400, 300, 20, rise=0).y == 300


# -- buttons


@pytest.mark.parametrize("color", [(0, 0, 0), (255, 255, 255), (127, 128, 129), (200, 30, 30), (10, 250, 10)])
def test_the_hover_lift_is_graphiks(color):
    assert hoverColor(color) == Graphik._hoverColor(color)


def test_a_button_has_the_2d_buttons_edges():
    button = Button(100, 50, 80, 40, "Go")
    assert button.contains((100, 50)) and button.contains((179, 89))
    assert not button.contains((180, 60)) and not button.contains((120, 90))
    assert not button.contains(None)


def test_a_button_draws_a_panel_and_a_centred_label_and_lifts_under_the_pointer():
    button = Button(100, 50, 80, 40, "Go", color=(40, 40, 40), textColor=(255, 255, 255),
                    pixelSize=12, alpha=0.9)
    panel, label = button.draw()
    assert (panel.x, panel.y, panel.width, panel.height) == (100, 50, 80, 40)
    assert panel.color == pytest.approx((40 / 255.0, 40 / 255.0, 40 / 255.0, 0.9))
    assert label.text == "Go" and label.pixelSize == 12
    assert label.x + measureText("Go", 12) / 2 == 140 and label.y + 6 == 70
    assert label.color == (1.0, 1.0, 1.0, 1.0)
    hovered, _ = button.draw(pointer=(120, 60))
    assert hovered.color == pytest.approx((75 / 255.0, 75 / 255.0, 75 / 255.0, 0.9))


def test_padding_widens_a_button_about_its_centre_to_fit_its_label():
    button = Button(100, 0, 40, 30, "Play again", pixelSize=10, padding=5)
    x, y, width, height = button.rect()
    assert width == 110 and x + width / 2 == 120 and (y, height) == (0, 30)
    assert button.contains((65, 10)) and not button.contains((64, 10))
    roomy = Button(100, 0, 200, 30, "Go", pixelSize=10, padding=5)
    assert roomy.rect() == (100, 0, 200, 30)


def test_a_click_on_a_button_runs_its_function():
    pressed = []
    button = Button(0, 0, 10, 10, "x", function=lambda: pressed.append(1))
    assert button.click((5, 5)) and pressed == [1]
    assert not button.click((15, 5)) and pressed == [1]
    assert not Button(0, 0, 10, 10, "x").click((5, 5))


def test_the_recorder_keeps_what_a_screen_draws_and_clicks_its_buttons():
    recorder = ScreenRecorder(800, 600)
    pressed = []
    recorder.drawText("Title", 400, 100, 40, (0, 0, 0, 255))
    recorder.drawRectangle(0, 0, 10, 10, (1, 2, 3))
    recorder.drawButton(300, 400, 200, 50, (90, 90, 90), (255, 255, 255), 30, "Start",
                        lambda: pressed.append("start"))
    assert recorder.texts() == ["Title"]
    assert recorder.items[0].color == (0, 0, 0)
    assert [b.text for b in recorder.buttons()] == ["Start"]
    assert not recorder.click((299, 410)) and pressed == []
    assert recorder.click((300, 400)) and pressed == ["start"]
    assert recorder.getGameDisplay().get_size() == (800, 600)
    recorder.resize(1024, 768)
    assert recorder.getGameDisplay().get_width() == 1024
    recorder.reset()
    assert recorder.items == []


# -- the board's options


def test_a_boards_own_tiles_colour_and_raise_their_cells():
    soil, grass = (0.5, 0.3, 0.1), (0.2, 0.7, 0.2)
    board = GridBoard(2, 1, Theme(frame=None), tiles={(0, 0): Tile(soil), (1, 0): Tile(grass, 0.06)})
    low, high = board.boardShapes()
    assert low.color[:3] == soil and high.color[:3] == grass
    t = board.theme
    assert low.position[1] == BED_TOP - t.tileHeight / 2 and low.scale[1] == t.tileHeight
    # a raised tile keeps its bottom where the others' is
    assert high.position[1] + high.scale[1] / 2 == pytest.approx(BED_TOP + 0.06)
    assert high.position[1] - high.scale[1] / 2 == pytest.approx(BED_TOP - t.tileHeight)
    # a plain colour works as a tile too; cells left out keep the checker
    mixed = GridBoard(2, 1, Theme(frame=None), tiles={(1, 0): (1.0, 0.0, 0.0)})
    assert [s.color[:3] for s in mixed.boardShapes()] == [Theme().tile, (1.0, 0.0, 0.0)]


def test_without_options_a_board_draws_as_in_0_4_0():
    board = GridBoard(3, 2)
    shapes = board.boardShapes()
    assert len(shapes) == 3 * 2 + 4
    edge = 1.0 - board.theme.tileGap
    for shape, (column, row) in zip(shapes, [(c, r) for r in range(2) for c in range(3)]):
        cx, cz = board.cellCenter(column, row)
        assert shape.position == (cx, BED_TOP - board.theme.tileHeight / 2, cz)
        assert shape.scale == (edge, board.theme.tileHeight, edge)


def test_merging_draws_a_64_by_64_board_of_one_colour_as_one_box_a_row():
    theme = Theme(alternate=None)
    plain = GridBoard(64, 64, theme)
    merged = GridBoard(64, 64, theme, mergeTiles=True)
    assert len(plain.boardShapes()) == 64 * 64 + 4
    shapes = merged.boardShapes()
    assert len(shapes) == 64 + 4
    row = shapes[0]
    assert row.position[0] == pytest.approx(0.0)
    assert row.scale[0] == pytest.approx(64 - theme.tileGap)


def test_merging_joins_only_neighbours_that_look_the_same():
    a, b = (0.2, 0.6, 0.2), (0.1, 0.3, 0.8)
    # per row: a a b a / b b b b, and one raised tile breaks a run
    tiles = {(0, 0): a, (1, 0): a, (2, 0): b, (3, 0): a}
    tiles.update({(c, 1): b for c in range(4)})
    tiles[(2, 1)] = Tile(b, 0.06)
    board = GridBoard(4, 2, Theme(frame=None), tiles=tiles, mergeTiles=True)
    shapes = board.boardShapes()
    widths = [round(s.scale[0] + board.theme.tileGap, 6) for s in shapes]
    assert widths == [2, 1, 1, 2, 1, 1]
    assert shapes[0].position[0] == pytest.approx(-1.0)  # the middle of columns 0 and 1


def test_a_64_by_64_checkered_board_has_nothing_to_merge():
    merged = GridBoard(64, 64, mergeTiles=True)
    assert len(merged.boardShapes()) == 64 * 64 + 4


def test_merging_respects_the_tint():
    board = GridBoard(8, 8, Theme(alternate=None), mergeTiles=True)
    shapes = board.boardShapes(tint=(1.0, 0.0, 0.0))
    assert len(shapes) == 8 + 4
    assert shapes[0].color[0] > board.theme.tile[0]


def test_a_viewport_draws_only_its_window_centred_and_framed():
    board = GridBoard(10, 10, Theme(alternate=None), viewport=Viewport.around(5, 5, 1))
    assert board.shownSize() == (3, 3)
    shapes = board.boardShapes()
    assert len(shapes) == 9 + 4
    assert board.cellCenter(5, 5) == (0.0, 0.0)
    assert board.cellCenter(4, 4) == (-1.0, -1.0)
    # the frame goes round the window
    assert shapes[9].scale[0] == pytest.approx(3 + 2 * board.theme.frameWidth)
    # the camera fits the window, not the board
    assert board.camera(1.0) == GridBoard(3, 3).camera(1.0)


def test_a_viewport_past_the_edge_leaves_off_board_cells_empty():
    board = GridBoard(10, 10, Theme(alternate=None), viewport=Viewport.around(0, 0, 2))
    tiles = [s for s in board.boardShapes()][:-4]
    assert len(tiles) == 3 * 3  # only cells (0..2, 0..2) are on the board
    assert not board.visible(-1, 0) and board.visible(2, 2) and not board.visible(3, 0)


def test_a_viewport_leaves_out_pieces_outside_it_and_picks_board_cells():
    board = GridBoard(10, 10, chainTheme(), viewport=Viewport(4, 4, 3, 3))
    inside, outside = Piece("in", 5, 6, "pawn"), Piece("out", 0, 0, "pawn")
    board.checkPieces([inside, outside])
    shapes, _ = board.pieceShapes([inside, outside])
    assert len(shapes) == 1
    assert (shapes[0].position[0], shapes[0].position[2]) == board.cellCenter(5, 6)
    camera = board.camera(1.0)
    at = cellScreenPosition(camera, board, 5, 6, 600, 600)
    assert pickCell(camera, board, at[0], at[1], 600, 600) == (5, 6)


def test_a_highlight_lays_a_slab_on_the_tile_last():
    board = GridBoard(3, 3, Theme(tileGap=0.12))
    plain = board.scene()
    lit = board.scene(highlight=(2, 0))
    assert len(lit.shapes) == len(plain.shapes) + 1
    slab = lit.shapes[-1]
    assert slab.kind == CUBE
    assert (slab.position[0], slab.position[2]) == (1.0, -1.0)
    assert slab.position[1] == pytest.approx(BED_TOP + 0.005)
    assert slab.scale == pytest.approx((0.88, 0.01, 0.88))
    assert slab.color == (1.0, 0.86, 0.35, 1.0)
    other = board.scene(highlight=(0, 0), highlightColor=(0.0, 1.0, 0.0))
    assert other.shapes[-1].color == (0.0, 1.0, 0.0, 1.0)
    assert board.highlightShapes((5, 5)) == [] and board.highlightShapes(None) == []


def test_a_highlight_sits_on_a_raised_tile():
    board = GridBoard(1, 1, tiles={(0, 0): Tile((0.2, 0.6, 0.2), 0.06)})
    assert board.highlightShapes((0, 0))[0].position[1] == pytest.approx(BED_TOP + 0.065)


def test_bridge_pairs_name_the_joined_pieces_in_drawing_order():
    board = GridBoard(6, 6, chainTheme())
    snake = [Piece(("s", i), 2 + i, 2, "body", chain="s", link=i) for i in range(3)]
    loose = Piece("x", 0, 0, "body", chain="s", link=5)  # not the next link
    pairs = board.bridgePairs(snake + [loose])
    assert [(a.id, b.id) for a, b in pairs] == [(("s", 0), ("s", 1)), (("s", 1), ("s", 2))]
    shapes, _ = board.pieceShapes(snake)
    where = {p.id: board.cellCenter(p.column, p.row) for p in snake}
    bridges = [board.bridgeShape(a, b, where[a.id], where[b.id]) for a, b in pairs]
    assert shapes[-2:] == bridges
    assert board._bridges(snake, where) == bridges  # the 0.4.0 name still works
