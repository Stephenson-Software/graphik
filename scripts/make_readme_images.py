"""Render the README images with graphik itself.

Run from the repository root:

    SDL_VIDEODRIVER=dummy python scripts/make_readme_images.py

Writes docs/images/hero.png (a sample of every draw method) and
docs/images/hover.png (buttons with the mouse away and over them), and, when
Strata's Python binding is installed, docs/images/grid3d.png (a board drawn
headless by the 3D grid view; skipped with a note otherwise). Uses the
graphik in src/main/python, not an installed copy, so the images always show
this checkout. No window is opened.
"""

import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "main", "python"))

import pygame  # noqa: E402

from preponderous.graphik import Graphik  # noqa: E402

OUT = os.path.join(ROOT, "docs", "images")
BACKGROUND = (245, 244, 240)
INK = (30, 30, 30)
MUTED = (110, 110, 110)


def _mouseAt(position):
    """Point drawButton's hit test (and hover) at ``position``."""
    pygame.mouse.get_pos = lambda: position
    pygame.mouse.get_pressed = lambda num_buttons=3: (0, 0, 0)


def _sampleImage(path):
    """Write a small gradient tile for drawImage to load."""
    tile = pygame.Surface((32, 32))
    for x in range(32):
        for y in range(32):
            tile.set_at((x, y), (40 + x * 6, 90 + y * 4, 200 - x * 3))
    pygame.image.save(tile, path)


def makeHero(path):
    width, height = 760, 260
    display = pygame.display.set_mode((width, height))
    graphik = Graphik(display)
    display.fill(BACKGROUND)

    graphik.drawText("graphik", width // 2, 34, 34, INK)
    graphik.drawText("drawRectangle, drawText, drawButton and drawImage on a pygame surface",
                     width // 2, 70, 16, MUTED)

    graphik.drawRectangle(40, 110, 120, 80, Graphik.red)
    graphik.drawRectangle(80, 140, 120, 80, Graphik.blue)
    graphik.drawText("drawRectangle", 120, 240, 15, MUTED)

    graphik.drawText("Hello, world!", 330, 150, 26, INK)
    graphik.drawText("drawText (centred)", 330, 240, 15, MUTED)

    _mouseAt((-100, -100))
    graphik.drawButton(450, 120, 130, 56, Graphik.green, Graphik.black, 22, "Play", lambda: None)
    graphik.drawText("drawButton", 515, 240, 15, MUTED)

    with tempfile.TemporaryDirectory() as tmp:
        tilePath = os.path.join(tmp, "tile.png")
        _sampleImage(tilePath)
        graphik.drawImage(tilePath, 620, 110, 100, 100)
    graphik.drawText("drawImage", 670, 240, 15, MUTED)

    pygame.image.save(display, path)


def makeHover(path):
    width, height = 760, 300
    display = pygame.display.set_mode((width, height))
    graphik = Graphik(display)
    display.fill(BACKGROUND)

    graphik.drawText("Button hover (on by default)", width // 2, 30, 24, INK)
    buttons = [
        ("Dark box", (40, 60, 140), Graphik.white),
        ("Light box", (225, 225, 225), INK),
        ("Graphik.green", Graphik.green, Graphik.black),
    ]
    for i, (name, box, text) in enumerate(buttons):
        x = 40 + i * 240
        graphik.drawText(name, x + 90, 72, 17, MUTED)
        _mouseAt((-100, -100))
        graphik.drawButton(x, 92, 180, 60, box, text, 22, "Play", lambda: None)
        graphik.drawText("mouse away", x + 90, 166, 14, MUTED)
        _mouseAt((x + 20, 212))
        graphik.drawButton(x, 192, 180, 60, box, text, 22, "Play", lambda: None)
        graphik.drawText("mouse over", x + 90, 266, 14, MUTED)

    pygame.image.save(display, path)


def makeGrid3D(path):
    """A board drawn by grid3d, headless: a chained snake with eyes, a glowing
    pickup, a few other piece kinds and a HUD label. Returns False when Strata
    can't run here."""
    from preponderous.graphik.grid3d import (
        CAPSULE, CUBE, CYLINDER, SPHERE, Grid3DView, GridBoard, Label, Piece,
        PieceStyle, Shape, Theme, Unavailable,
    )

    def eyes(piece, x, z, baseY):
        dx, dz = piece.facing
        sx, sz = -dz * 0.18, dx * 0.18
        return [Shape(SPHERE, (x + dx * 0.32 + sx * side, baseY + 0.55, z + dz * 0.32 + sz * side),
                      (0.14, 0.14, 0.14), (0.05, 0.05, 0.05, 1.0)) for side in (-1, 1)]

    theme = Theme(pieces={
        "head": PieceStyle(SPHERE, (0.55, 0.9, 0.7), height=0.75, size=0.75, extras=eyes),
        "body": PieceStyle(SPHERE, (0.85, 0.12, 0.12), height=0.6, size=0.6, tones=(1.0, 0.85)),
        "food": PieceStyle(SPHERE, (0.95, 0.2, 0.15), height=0.45, size=0.45, glow=(2.5, 1.2)),
        "crate": PieceStyle(CUBE, (0.75, 0.55, 0.3), height=0.55, size=0.7),
        "post": PieceStyle(CYLINDER, (0.35, 0.45, 0.85), height=0.9, size=0.4),
        "token": PieceStyle(CAPSULE, (0.95, 0.85, 0.2), height=0.8, size=0.35),
    })
    try:
        view = Grid3DView.open(960, 540, "graphik grid3d", headless=True)
    except Unavailable as reason:
        print("skipped docs/images/grid3d.png:", reason)
        return False
    try:
        view.setBoard(GridBoard(9, 7, theme))
        body = [(4, 2), (4, 3), (4, 4), (5, 4), (6, 4), (6, 5), (6, 6)]
        pieces = [Piece("head", 3, 2, "head", chain="snake", link=0, facing=(-1, 0))]
        pieces += [Piece(f"s{i}", c, r, "body", chain="snake", link=i + 1, scale=1.0 - i * 0.05)
                   for i, (c, r) in enumerate(body)]
        pieces += [Piece("food", 1, 2, "food"), Piece("crate", 7, 1, "crate"),
                   Piece("post", 1, 5, "post"), Piece("token", 2, 5, "token")]
        view.setPieces(pieces, snap=True)
        view.setLabels([Label("Score 120", 18, 14, 26)])
        view.frame(present=False)
        view.savePng(path)
    finally:
        view.close()
    return True


def main():
    os.makedirs(OUT, exist_ok=True)
    pygame.init()
    try:
        makeHero(os.path.join(OUT, "hero.png"))
        makeHover(os.path.join(OUT, "hover.png"))
    finally:
        pygame.quit()
    print("wrote docs/images/hero.png and docs/images/hover.png")
    if makeGrid3D(os.path.join(OUT, "grid3d.png")):
        print("wrote docs/images/grid3d.png")


if __name__ == "__main__":
    main()
