"""Grid3DView: why it can't start, and a headless render against a golden image.

The render tests need Strata's Python binding and its library; they skip when
Strata can't load here (Grid3DView.open raises Unavailable).
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

from preponderous.graphik.grid3d import (
    CAPSULE,
    SPHERE,
    GridBoard,
    Grid3DView,
    Label,
    Piece,
    PieceStyle,
    Theme,
    Unavailable,
)
from preponderous.graphik.grid3d import view as viewModule

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "board-4x3.png")


# -- why it can't start (no GPU needed)


def test_a_system_without_a_strata_library_is_unavailable(monkeypatch):
    monkeypatch.delenv("STRATA_LIBRARY", raising=False)
    with pytest.raises(Unavailable, match="no library for this system"):
        viewModule.loadStrata(platform="darwin")


def test_a_missing_binding_says_how_to_install_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "strata", None)  # makes `import strata` fail
    with pytest.raises(Unavailable, match=r"graphik\[strata\]"):
        viewModule.loadStrata(platform="linux")


# -- rendering (needs Strata)


def openHeadless(width=240, height=180, clock=None):
    try:
        if clock is None:
            return Grid3DView.open(width, height, headless=True)
        return Grid3DView.open(width, height, headless=True, clock=clock)
    except Unavailable as reason:
        pytest.skip("Strata can't run here: %s" % reason)


def goldenScene(view):
    theme = Theme(
        pieces={
            "pawn": PieceStyle(SPHERE, (0.9, 0.25, 0.2)),
            "gem": PieceStyle(CAPSULE, (0.2, 0.8, 0.95), height=0.7, size=0.4, glow=(2.0, 1.6)),
        }
    )
    view.setBoard(GridBoard(4, 3, theme))
    view.setPieces([Piece("p", 1, 1, "pawn"), Piece("g", 3, 0, "gem")])
    view.setLabels([Label("grid3d", 8, 8, 14)])


def differingFraction(expected, actual, threshold=12.0):
    """Fraction of pixels whose RGB distance exceeds `threshold` (0-255 scale).
    Uses strata-imgcmp (STRATA_IMGCMP or on PATH) when available."""
    imgcmp = os.environ.get("STRATA_IMGCMP") or shutil.which("strata-imgcmp")
    if imgcmp:
        out = subprocess.run(
            [imgcmp, expected, actual, "--json", "--threshold", "4"],
            capture_output=True,
            text=True,
        )
        report = json.loads(out.stdout)
        for key in ("fraction_over", "fractionOver", "over_fraction"):
            if key in report:
                return float(report[key])
        if "pixels_over" in report and "pixels" in report:
            return report["pixels_over"] / float(report["pixels"])
    import pygame

    a = pygame.image.load(expected)
    b = pygame.image.load(actual)
    assert a.get_size() == b.get_size()
    width, height = a.get_size()
    over = 0
    for y in range(height):
        for x in range(width):
            pa, pb = a.get_at((x, y)), b.get_at((x, y))
            d = ((pa.r - pb.r) ** 2 + (pa.g - pb.g) ** 2 + (pa.b - pb.b) ** 2) ** 0.5
            over += d > threshold
    return over / float(width * height)


def test_a_board_renders_like_the_golden_image(tmp_path):
    view = openHeadless()
    try:
        goldenScene(view)
        view.frame(present=False)
        actual = str(tmp_path / "board-4x3.png")
        view.savePng(actual)
    finally:
        view.close()
    assert differingFraction(GOLDEN, actual) <= 0.02


def test_a_frame_mid_tick_draws_a_piece_between_its_cells():
    now = [0.0]
    view = openHeadless(clock=lambda: now[0])
    try:
        theme = Theme(pieces={"pawn": PieceStyle(SPHERE, (0.9, 0.25, 0.2))})
        view.setBoard(GridBoard(4, 3, theme))
        view.setPieces([Piece("p", 0, 1, "pawn")], tickSeconds=0.2)
        now[0] = 0.2
        view.setPieces([Piece("p", 1, 1, "pawn")], tickSeconds=0.2)
        now[0] = 0.3
        scene = view.scene()
        piece = scene.shapes[-1]
        assert piece.position[0] == pytest.approx(-1.0)  # halfway from -1.5 to -0.5
        view.frame(present=False)  # and the engine accepts it
    finally:
        view.close()
