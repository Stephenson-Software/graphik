"""A grid game's board in 3D: tiles, a frame, pieces standing on cells.

A game says *what* is on each cell with Piece objects; a Theme says *how*
everything looks (tile colours, frame, one PieceStyle per kind of piece).
GridBoard turns the two into scene shapes and lights, and fits a camera.
Pure Python: no Strata, no pygame.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Hashable, List, Optional, Tuple

from .scene import (
    CUBE,
    SPHERE,
    Camera,
    Light,
    Scene,
    Shape,
    checkLights,
    rgba,
    shade,
)

BED_TOP = 0.0  # y of the tiles' top face; pieces stand on it


@dataclass
class PieceStyle:
    """How one kind of piece looks.

    kind, color, height (y size) and size (x/z footprint, in cells) make the
    piece's main shape, standing on the board with its base `lift` above the
    tiles. `glow` adds a point light above it: (radius, intensity). `tones`
    (odd, even) shades chained pieces alternately by link, so a long body
    reads as segments. `extras`
    draws decorations (eyes, a crown): called with (piece, x, z, baseY), it
    returns more Shapes, positioned from the piece's current (possibly
    interpolated) world position.
    """

    kind: int = CUBE
    color: Tuple[float, float, float] = (0.8, 0.8, 0.8)
    height: float = 0.5
    size: float = 0.8
    lift: float = 0.0
    glow: Optional[Tuple[float, float]] = None
    tones: Optional[Tuple[float, float]] = None
    extras: Optional[Callable] = None


@dataclass
class Piece:
    """Something standing on cell (column, row).

    `id` must stay the same from tick to tick for the same thing, so a view
    can animate it from its old cell to its new one. `style` names a
    PieceStyle in the Theme. `scale` multiplies the style's footprint and
    height (a tapering tail), `color` overrides the style's colour.

    Pieces with the same `chain` and consecutive `link` numbers (a snake's
    segments, head first) are joined by a bridge when their cells are
    orthogonal neighbours. `facing` is a unit (dx, dz) step for extras that
    look somewhere. `interpolate=False` makes the piece jump to its new cell
    instead of sliding (teleports, wrap-around).
    """

    id: Hashable
    column: int
    row: int
    style: str
    scale: float = 1.0
    color: Optional[Tuple[float, float, float]] = None
    chain: Optional[Hashable] = None
    link: int = 0
    facing: Tuple[int, int] = (0, 1)
    interpolate: bool = True


@dataclass
class Theme:
    """The look of a board and its pieces. Colours are 0-1 (r, g, b)."""

    tile: Tuple[float, float, float] = (0.22, 0.38, 0.17)
    alternate: Optional[Tuple[float, float, float]] = (0.18, 0.32, 0.14)
    tileHeight: float = 0.18
    tileGap: float = 0.03
    frame: Optional[Tuple[float, float, float]] = (0.36, 0.22, 0.12)
    frameWidth: float = 0.35
    pieces: Dict[str, PieceStyle] = field(default_factory=dict)
    # How chained pieces are bridged: footprint across the bridge (a fraction
    # of a cell, before the pieces' scale), height as a fraction of the
    # pieces' height, and colour shade relative to the piece.
    bridgeAcross: float = 0.6
    bridgeHeight: float = 0.8
    bridgeShade: float = 0.85

    def style(self, name):
        try:
            return self.pieces[name]
        except KeyError:
            raise KeyError(
                "no PieceStyle named %r in the theme (known: %s)"
                % (name, ", ".join(sorted(self.pieces)) or "none")
            )


def cellCenter(column, row, columns, rows):
    """World (x, z) of the middle of cell (column, row)."""
    return (column - (columns - 1) / 2.0, row - (rows - 1) / 2.0)


def fitCamera(columns, rows, aspect=1.0, fovDegrees=42.0):
    """A camera south of the board, tilted down about 55 degrees, far enough
    back that the whole board and its frame fit, aiming a little beyond the
    centre so the board sits low in the window and leaves the top rows of the
    screen for a HUD. A tall window backs the camera off further."""
    size = max(columns, rows) + 1.0  # the frame adds about half a cell a side
    size *= max(1.0, 1.0 / max(aspect, 0.5))
    distance = 0.86 * size + 0.9
    return Camera(
        eye=(0.0, 1.35 * distance, 0.95 * distance),
        target=(0.0, -0.3, -0.04 * size),
        fovDegrees=fovDegrees,
    )


class GridBoard:
    """A columns x rows board drawn with a Theme."""

    def __init__(self, columns, rows, theme=None):
        if columns < 1 or rows < 1:
            raise ValueError("a board needs at least one column and one row")
        self.columns = columns
        self.rows = rows
        self.theme = theme or Theme()

    def cellCenter(self, column, row):
        return cellCenter(column, row, self.columns, self.rows)

    def contains(self, column, row):
        return 0 <= column < self.columns and 0 <= row < self.rows

    def camera(self, aspect=1.0):
        return fitCamera(self.columns, self.rows, aspect)

    # -- the static part

    def boardShapes(self, tint=None, tintAmount=0.55):
        """Tiles (checkered when the theme has an alternate colour) and a
        frame. `tint` blends every tile towards a colour (a red flash on a
        collision)."""
        t = self.theme
        shapes = []
        edge = 1.0 - t.tileGap
        for row in range(self.rows):
            for column in range(self.columns):
                cx, cz = self.cellCenter(column, row)
                color = t.tile
                if t.alternate is not None and (column + row) % 2:
                    color = t.alternate
                if tint is not None:
                    color = tuple(
                        (1 - tintAmount) * c + tintAmount * k
                        for c, k in zip(color, tint)
                    )
                shapes.append(
                    Shape(
                        CUBE,
                        (cx, BED_TOP - t.tileHeight / 2, cz),
                        (edge, t.tileHeight, edge),
                        rgba(color),
                    )
                )
        if t.frame is not None:
            halfW, halfD = self.columns / 2.0, self.rows / 2.0
            rim, height = t.frameWidth, t.tileHeight + 0.12
            yMid = BED_TOP - t.tileHeight + height / 2
            frame = rgba(t.frame)
            wide = self.columns + 2 * rim
            shapes += [
                Shape(CUBE, (0.0, yMid, -halfD - rim / 2), (wide, height, rim), frame),
                Shape(CUBE, (0.0, yMid, halfD + rim / 2), (wide, height, rim), frame),
                Shape(CUBE, (-halfW - rim / 2, yMid, 0.0), (rim, height, self.rows), frame),
                Shape(CUBE, (halfW + rim / 2, yMid, 0.0), (rim, height, self.rows), frame),
            ]
        return shapes

    # -- the dynamic part

    def checkPieces(self, pieces):
        """Raise ValueError for a piece off the board or a duplicate id, and
        KeyError for an unknown style."""
        seen = set()
        for piece in pieces:
            if piece.id in seen:
                raise ValueError("two pieces share the id %r" % (piece.id,))
            seen.add(piece.id)
            if not self.contains(piece.column, piece.row):
                raise ValueError(
                    "piece %r is off the %dx%d board at (%d, %d)"
                    % (piece.id, self.columns, self.rows, piece.column, piece.row)
                )
            self.theme.style(piece.style)

    def pieceShapes(self, pieces, positions=None):
        """Shapes and lights for `pieces`. `positions` maps a piece id to its
        world (x, z) for this frame (from an Animator); pieces without one
        stand in the middle of their cell."""
        shapes, lights = [], []
        where = {}
        for piece in pieces:
            x, z = (positions or {}).get(piece.id) or self.cellCenter(
                piece.column, piece.row
            )
            where[piece.id] = (x, z)
            style = self.theme.style(piece.style)
            color = piece.color if piece.color is not None else style.color
            if style.tones is not None and piece.chain is not None:
                color = shade(color, style.tones[0] if piece.link % 2 else style.tones[1])
            size = style.size * piece.scale
            height = style.height * (0.75 + 0.25 * piece.scale)
            baseY = BED_TOP + style.lift
            shapes.append(
                Shape(
                    style.kind,
                    (x, baseY + height / 2, z),
                    (size, height, size),
                    rgba(color),
                )
            )
            if style.glow is not None:
                radius, intensity = style.glow
                lights.append(
                    Light((x, baseY + height + 0.4, z), tuple(color), radius, intensity)
                )
            if style.extras is not None:
                shapes.extend(style.extras(piece, x, z, baseY) or [])
        shapes.extend(self._bridges(pieces, where))
        return shapes, lights

    def _bridges(self, pieces, where):
        t = self.theme
        chains = {}
        for piece in pieces:
            if piece.chain is not None:
                chains.setdefault(piece.chain, []).append(piece)
        shapes = []
        for members in chains.values():
            members.sort(key=lambda p: p.link)
            for a, b in zip(members, members[1:]):
                if b.link != a.link + 1:
                    continue
                # only orthogonal neighbours (on their target cells) are joined
                if abs(a.column - b.column) + abs(a.row - b.row) != 1:
                    continue
                (ax, az), (bx, bz) = where[a.id], where[b.id]
                style = t.style(b.style)
                scale = (a.scale + b.scale) / 2
                across = t.bridgeAcross * scale
                height = style.height * t.bridgeHeight * (0.75 + 0.25 * scale)
                color = b.color if b.color is not None else style.color
                shapes.append(
                    Shape(
                        SPHERE,
                        ((ax + bx) / 2, BED_TOP + style.lift + height / 2, (az + bz) / 2),
                        (max(across, abs(ax - bx)), height, max(across, abs(az - bz))),
                        rgba(shade(color, t.bridgeShade)),
                    )
                )
        return shapes

    # -- everything

    def scene(self, pieces=(), positions=None, labels=(), panels=(), lights=(),
              aspect=1.0, tint=None, clearColor=None):
        """A complete Scene, checked against the engine limits."""
        pieceShapes, pieceLights = self.pieceShapes(pieces, positions)
        scene = Scene(camera=self.camera(aspect))
        scene.shapes = self.boardShapes(tint) + pieceShapes
        scene.lights = list(lights) + pieceLights
        scene.labels = list(labels)
        scene.panels = list(panels)
        if clearColor is not None:
            scene.clearColor = clearColor
        checkLights(scene.lights)
        return scene
