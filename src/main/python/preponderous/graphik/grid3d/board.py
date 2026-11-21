"""A grid game's board in 3D: tiles, a frame, pieces standing on cells.

A game says *what* is on each cell with Piece objects; a Theme says *how*
everything looks (tile colours, frame, one PieceStyle per kind of piece).
GridBoard turns the two into scene shapes and lights, and fits a camera.
Pure Python: no Strata, no pygame.

Options for bigger or busier boards: `tiles` gives cells their own colour
(and a raise above the bed), `mergeTiles` draws a row's neighbouring tiles
of one look as one box (a 64 x 64 board of grass is 64 boxes, not 4096),
and `viewport` draws only a window of the board (a close-up around one
cell). `scene(highlight=...)` lights the tile under the pointer.
"""

import functools
import math
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
    reads as segments.

    `extras` draws decorations (eyes, a crown): called with
    (piece, x, z, baseY), it returns more Shapes. Their positions are
    relative to the piece: x and z measured from the given (x, z), which is
    the piece's current (possibly interpolated) world position, and y from
    `baseY` (or absolute). Moving (x, z) by some amount must move every shape
    it returns by the same amount, and nothing else about them may depend on
    where the piece stands. The browser backend (web.py) relies on this: it
    draws a piece's shapes once, sends them as offsets from the piece, and
    the page slides them along with it.
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
    # The slab GridBoard.scene(highlight=cell) lays on the tile under the
    # pointer (the 3D form of a 2D button's hover lift).
    highlight: Tuple[float, float, float] = (1.0, 0.86, 0.35)

    def style(self, name):
        try:
            return self.pieces[name]
        except KeyError:
            raise KeyError(
                "no PieceStyle named %r in the theme (known: %s)"
                % (name, ", ".join(sorted(self.pieces)) or "none")
            )


_NOT_GIVEN = object()


@dataclass(frozen=True)
class Tile:
    """One cell's own tile (GridBoard's `tiles`): a 0-1 (r, g, b) colour, and
    how far its top stands above the bed (water and grass a little proud of
    bare soil). Its bottom stays where every tile's is."""

    color: Tuple[float, float, float]
    raised: float = 0.0


@dataclass(frozen=True)
class Viewport:
    """A window of a board: `columns` x `rows` cells from (column, row), its
    top-left cell. It may reach past the board's edges; cells off the board
    are left empty."""

    column: int
    row: int
    columns: int
    rows: int

    def contains(self, column, row):
        return (self.column <= column < self.column + self.columns
                and self.row <= row < self.row + self.rows)

    @classmethod
    def around(cls, column, row, reach):
        """The (2 * reach + 1)-cell square centred on (column, row)."""
        return cls(column - reach, row - reach, 2 * reach + 1, 2 * reach + 1)


def cellCenter(column, row, columns, rows):
    """World (x, z) of the middle of cell (column, row)."""
    return (column - (columns - 1) / 2.0, row - (rows - 1) / 2.0)


# The camera's tilt below the horizon, in degrees: fitCamera's desktop
# framing looks down about 55 degrees; a portrait window (a phone held
# upright) looks down more steeply, so the board stands taller on screen and
# fills more of the tall, narrow window.
LANDSCAPE_PITCH = math.degrees(math.atan2(1.35, 0.95))
PORTRAIT_PITCH = 70.0
# Below this aspect (width / height) a window is fully "portrait"; from here
# to 1 the framing blends from portrait to the desktop's.
PORTRAIT_ASPECT = 0.8
# How much of a portrait window's height is kept free for a HUD at the top
# (and a little at the bottom) when the caller doesn't say, and the margins
# kept inside whatever area the board is fitted to.
DEFAULT_TOP, DEFAULT_BOTTOM = 0.12, 0.03
SIDE_MARGIN, END_MARGIN = 0.02, 0.02


def fitCamera(columns, rows, aspect=1.0, fovDegrees=42.0, top=None, bottom=None):
    """A camera south of the board, looking down at it, far enough back that
    the whole board and its frame fit.

    A landscape (or square) window with nothing reserved keeps the desktop
    framing: tilted down about 55 degrees, aiming a little beyond the centre
    so the board sits low in the window and leaves the top rows of the screen
    for a HUD.

    A portrait window (aspect below 1, a phone held upright) is framed for its
    shape instead: the camera looks down more steeply and the board fills the
    window's width and stands in the middle of the space left between `top`
    and `bottom`. Between PORTRAIT_ASPECT and 1 the two framings blend, so
    resizing a window across square doesn't make the board jump.

    `top` and `bottom` are the fractions (0-1) of the window's height kept
    clear of the board: a HUD across the top, a bar of touch keys at the
    bottom. Given either (in any window shape), the board is fitted inside
    the space between them. Left out, a portrait window keeps DEFAULT_TOP and
    DEFAULT_BOTTOM clear and a landscape one is framed as on the desktop."""
    aspect = max(float(aspect), 0.05)
    reserved = top is not None or bottom is not None
    if not reserved and aspect >= 1.0:
        return _desktopCamera(columns, rows, aspect, fovDegrees)
    portrait = _portraitWeight(aspect)
    pitch = LANDSCAPE_PITCH + (PORTRAIT_PITCH - LANDSCAPE_PITCH) * portrait
    top = DEFAULT_TOP if top is None else top
    bottom = DEFAULT_BOTTOM if bottom is None else bottom
    fitted = _fittedCamera(columns, rows, aspect, fovDegrees, pitch, top, bottom)
    if reserved or portrait >= 1.0:
        return fitted
    # a nearly square window: part way from the desktop framing to this one
    return _blendCameras(_desktopCamera(columns, rows, aspect, fovDegrees), fitted, portrait)


def _desktopCamera(columns, rows, aspect, fovDegrees):
    # graphik 0.5.1's framing, unchanged for landscape windows
    size = max(columns, rows) + 1.0  # the frame adds about half a cell a side
    size *= max(1.0, 1.0 / max(aspect, 0.5))
    distance = 0.86 * size + 0.9
    return Camera(
        eye=(0.0, 1.35 * distance, 0.95 * distance),
        target=(0.0, -0.3, -0.04 * size),
        fovDegrees=fovDegrees,
    )


def _portraitWeight(aspect):
    """0 for a landscape or square window, 1 at PORTRAIT_ASPECT and below."""
    if aspect >= 1.0:
        return 0.0
    if aspect <= PORTRAIT_ASPECT:
        return 1.0
    return (1.0 - aspect) / (1.0 - PORTRAIT_ASPECT)


def _blendCameras(a, b, weight):
    mix = lambda p, q: tuple(x + (y - x) * weight for x, y in zip(p, q))  # noqa: E731
    return Camera(eye=mix(a.eye, b.eye), target=mix(a.target, b.target),
                  fovDegrees=a.fovDegrees + (b.fovDegrees - a.fovDegrees) * weight)


# what fitCamera keeps in view: the board's tiles and frame (half a cell
# past its edge, less a little), from under the tiles to the height of a
# typical piece
_EDGE, _LOW, _HIGH = 0.35, -0.18, 0.5


def _boardExtent(columns, rows, eye, forward, right, up, focal, aspect):
    """The board's bounding box on screen, in normalised device
    coordinates: (left, bottom, right, top)."""
    xs, ys = [], []
    for x in (-columns / 2.0 - _EDGE, columns / 2.0 + _EDGE):
        for z in (-rows / 2.0 - _EDGE, rows / 2.0 + _EDGE):
            for y in (_LOW, _HIGH):
                d = (x - eye[0], y - eye[1], z - eye[2])
                depth = d[0] * forward[0] + d[1] * forward[1] + d[2] * forward[2]
                if depth <= 1e-6:
                    return None
                xs.append(focal / aspect * (d[0] * right[0] + d[1] * right[1] + d[2] * right[2]) / depth)
                ys.append(focal * (d[0] * up[0] + d[1] * up[1] + d[2] * up[2]) / depth)
    return min(xs), min(ys), max(xs), max(ys)


@functools.lru_cache(maxsize=256)
def _fittedCamera(columns, rows, aspect, fovDegrees, pitch, top, bottom):
    """The camera at `pitch` degrees below the horizon that shows the board
    as big as it fits, with SIDE_MARGIN at the sides and END_MARGIN above
    and below, in the window's height between `top` and `bottom` (fractions
    of it), centred in that space."""
    top = min(max(float(top), 0.0), 0.9)
    bottom = min(max(float(bottom), 0.0), 0.9 - top)
    # the space the board may fill, in normalised device coordinates (y up)
    ndcTop = 1.0 - 2.0 * (top + END_MARGIN)
    ndcBottom = -1.0 + 2.0 * (bottom + END_MARGIN)
    if ndcTop - ndcBottom < 0.1:
        ndcTop, ndcBottom = 0.05, -0.05
    ndcWidth = 2.0 * (1.0 - 2.0 * SIDE_MARGIN)
    middle = (ndcTop + ndcBottom) / 2.0
    tilt = math.radians(pitch)
    back = (0.0, math.sin(tilt), math.cos(tilt))  # from the target to the eye
    forward = (0.0, -back[1], -back[2])
    right = (1.0, 0.0, 0.0)
    up = (0.0, back[2], -back[1])  # right x forward
    focal = 1.0 / math.tan(math.radians(fovDegrees) / 2.0)

    def extent(distance, shift):
        # the target slides along the board's depth (z) by `shift`
        eye = (0.0, distance * back[1], shift + distance * back[2])
        return _boardExtent(columns, rows, eye, forward, right, up, focal, aspect)

    def centred(distance):
        # the shift that puts the board's middle in the middle of the space
        low, high = -4.0 * (rows + columns) - 10.0, 4.0 * (rows + columns) + 10.0
        for _ in range(36):
            shift = (low + high) / 2.0
            box = extent(distance, shift)
            if box is not None and (box[1] + box[3]) / 2.0 < middle:
                # the camera moving south (larger z) raises the board on screen
                low = shift
            else:
                high = shift
        return (low + high) / 2.0

    def fits(distance):
        shift = centred(distance)
        box = extent(distance, shift)
        return box is not None and box[2] - box[0] <= ndcWidth and box[3] - box[1] <= ndcTop - ndcBottom

    near, far = 0.5, 10.0 * (columns + rows) + 20.0
    for _ in range(36):
        distance = (near + far) / 2.0
        if fits(distance):
            far = distance
        else:
            near = distance
    shift = centred(far)
    target = (0.0, 0.0, shift)
    eye = (0.0, far * back[1], shift + far * back[2])
    return Camera(eye=eye, target=target, fovDegrees=fovDegrees)


class GridBoard:
    """A columns x rows board drawn with a Theme.

    `tiles` maps (column, row) to a Tile (or a 0-1 colour) for cells whose
    tile isn't the theme's checker; the others keep it, and a cell mapped
    to None has no tile at all. `mergeTiles` draws
    each run of neighbouring tiles in a row that look the same (colour and
    raise, after any tint) as one stretched box, so a big board costs a
    shape per run, not per cell. `viewport` (a Viewport) draws only that
    window of the board: the window is centred on the origin, framed and
    fitted by the camera as if it were the whole board, pieces outside it
    aren't drawn, and cells past the board's edge stay empty. Pieces and
    picking still use the whole board's (column, row).
    """

    def __init__(self, columns, rows, theme=None, tiles=None, mergeTiles=False,
                 viewport=None):
        if columns < 1 or rows < 1:
            raise ValueError("a board needs at least one column and one row")
        if viewport is not None and (viewport.columns < 1 or viewport.rows < 1):
            raise ValueError("a viewport needs at least one column and one row")
        self.columns = columns
        self.rows = rows
        self.theme = theme or Theme()
        self.tiles = tiles
        self.mergeTiles = mergeTiles
        self.viewport = viewport

    # -- what is on show

    def shownSize(self):
        """(columns, rows) of what is drawn: the viewport's, or the board's."""
        if self.viewport is None:
            return self.columns, self.rows
        return self.viewport.columns, self.viewport.rows

    def shownOrigin(self):
        """The board cell drawn at the top-left of what is on show."""
        if self.viewport is None:
            return 0, 0
        return self.viewport.column, self.viewport.row

    def visible(self, column, row):
        """True for a board cell that is drawn (on the board and in view)."""
        return self.contains(column, row) and (
            self.viewport is None or self.viewport.contains(column, row)
        )

    def cellCenter(self, column, row):
        if self.viewport is None:
            return cellCenter(column, row, self.columns, self.rows)
        v = self.viewport
        return cellCenter(column - v.column, row - v.row, v.columns, v.rows)

    def contains(self, column, row):
        return 0 <= column < self.columns and 0 <= row < self.rows

    def camera(self, aspect=1.0, top=None, bottom=None):
        """fitCamera for what is on show; `top` and `bottom` are the
        fractions of the window's height kept clear of the board."""
        columns, rows = self.shownSize()
        return fitCamera(columns, rows, aspect, top=top, bottom=bottom)

    def cellAt(self, x, z):
        """The visible board cell under world point (x, z), or None."""
        columns, rows = self.shownSize()
        originColumn, originRow = self.shownOrigin()
        column = int(math.floor(x + columns / 2.0)) + originColumn
        row = int(math.floor(z + rows / 2.0)) + originRow
        return (column, row) if self.visible(column, row) else None

    # -- the static part

    def tileAt(self, column, row):
        """The Tile drawn on a visible cell (before any tint), or None when
        the board's `tiles` leave the cell bare."""
        t = self.theme
        own = _NOT_GIVEN if self.tiles is None else self.tiles.get((column, row), _NOT_GIVEN)
        if own is None:
            return None
        if own is not _NOT_GIVEN:
            return own if isinstance(own, Tile) else Tile(tuple(own))
        if t.alternate is not None and (column + row) % 2:
            return Tile(t.alternate)
        return Tile(t.tile)

    def tileRaise(self, column, row):
        """How far the tile on a visible cell stands above the bed."""
        own = None if self.tiles is None else self.tiles.get((column, row))
        return own.raised if isinstance(own, Tile) else 0.0

    def boardShapes(self, tint=None, tintAmount=0.55):
        """Tiles (checkered when the theme has an alternate colour, or the
        board's own `tiles`) and a frame. `tint` blends every tile towards a
        colour (a red flash on a collision)."""
        t = self.theme
        shapes = []
        edge = 1.0 - t.tileGap
        columns, rows = self.shownSize()
        originColumn, originRow = self.shownOrigin()
        for shownRow in range(rows):
            row = originRow + shownRow
            run = None  # [first column, last column, color, raised]
            for shownColumn in range(columns):
                column = originColumn + shownColumn
                tile = self.tileAt(column, row) if self.contains(column, row) else None
                if tile is None:
                    if run is not None:
                        shapes.append(self._tileShape(run, row, edge))
                        run = None
                    continue
                color = tile.color
                if tint is not None:
                    color = tuple(
                        (1 - tintAmount) * c + tintAmount * k
                        for c, k in zip(color, tint)
                    )
                if (self.mergeTiles and run is not None
                        and run[2] == color and run[3] == tile.raised):
                    run[1] = column
                    continue
                if run is not None:
                    shapes.append(self._tileShape(run, row, edge))
                run = [column, column, color, tile.raised]
            if run is not None:
                shapes.append(self._tileShape(run, row, edge))
        if t.frame is not None:
            halfW, halfD = columns / 2.0, rows / 2.0
            rim, height = t.frameWidth, t.tileHeight + 0.12
            yMid = BED_TOP - t.tileHeight + height / 2
            frame = rgba(t.frame)
            wide = columns + 2 * rim
            shapes += [
                Shape(CUBE, (0.0, yMid, -halfD - rim / 2), (wide, height, rim), frame),
                Shape(CUBE, (0.0, yMid, halfD + rim / 2), (wide, height, rim), frame),
                Shape(CUBE, (-halfW - rim / 2, yMid, 0.0), (rim, height, rows), frame),
                Shape(CUBE, (halfW + rim / 2, yMid, 0.0), (rim, height, rows), frame),
            ]
        return shapes

    def _tileShape(self, run, row, edge):
        first, last, color, raised = run
        t = self.theme
        firstX, z = self.cellCenter(first, row)
        if first == last:
            x, width = firstX, edge
        else:
            lastX, _ = self.cellCenter(last, row)
            x, width = (firstX + lastX) / 2.0, last - first + 1 - t.tileGap
        if raised:
            height = t.tileHeight + raised
            y = BED_TOP - t.tileHeight + height / 2
        else:
            height, y = t.tileHeight, BED_TOP - t.tileHeight / 2
        return Shape(CUBE, (x, y, z), (width, height, edge), rgba(color))

    def highlightShapes(self, cell, color=None):
        """A thin slab on a visible cell's tile, in the theme's highlight
        colour (or `color`): the tile under the pointer. None for no cell."""
        if cell is None or not self.visible(*cell):
            return []
        x, z = self.cellCenter(*cell)
        edge = 1.0 - self.theme.tileGap
        top = BED_TOP + self.tileRaise(*cell)
        color = self.theme.highlight if color is None else color
        return [Shape(CUBE, (x, top + 0.005, z), (edge, 0.01, edge), rgba(color))]

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
        stand in the middle of their cell. With a viewport, pieces outside
        it are left out."""
        if self.viewport is not None:
            pieces = [p for p in pieces if self.viewport.contains(p.column, p.row)]
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
        for a, b in self.bridgePairs(pieces):
            shapes.append(self.bridgeShape(a, b, where[a.id], where[b.id]))
        return shapes, lights

    def bridgePairs(self, pieces):
        """(a, b) for every pair of pieces joined by a bridge: the same chain,
        consecutive links (a's link + 1 == b's) and orthogonal neighbours on
        their cells. Chains come in the order their first piece does, each
        pair in link order: the order pieceShapes draws the bridges in."""
        chains = {}
        for piece in pieces:
            if piece.chain is not None:
                chains.setdefault(piece.chain, []).append(piece)
        pairs = []
        for members in chains.values():
            members = sorted(members, key=lambda p: p.link)
            for a, b in zip(members, members[1:]):
                if b.link != a.link + 1:
                    continue
                # only orthogonal neighbours (on their target cells) are joined
                if abs(a.column - b.column) + abs(a.row - b.row) != 1:
                    continue
                pairs.append((a, b))
        return pairs

    def bridgeShape(self, a, b, aAt, bAt):
        """The bridge between joined pieces a and b drawn at world (x, z)
        `aAt` and `bAt`: in the middle, stretched to reach both (and never
        thinner across than the theme's bridgeAcross)."""
        t = self.theme
        (ax, az), (bx, bz) = aAt, bAt
        style = t.style(b.style)
        scale = (a.scale + b.scale) / 2
        across = t.bridgeAcross * scale
        height = style.height * t.bridgeHeight * (0.75 + 0.25 * scale)
        color = b.color if b.color is not None else style.color
        return Shape(
            SPHERE,
            ((ax + bx) / 2, BED_TOP + style.lift + height / 2, (az + bz) / 2),
            (max(across, abs(ax - bx)), height, max(across, abs(az - bz))),
            rgba(shade(color, t.bridgeShade)),
        )

    def _bridges(self, pieces, where):
        # kept for code written against 0.4.0; bridgePairs and bridgeShape
        # are the public form
        return [self.bridgeShape(a, b, where[a.id], where[b.id])
                for a, b in self.bridgePairs(pieces)]

    # -- everything

    def scene(self, pieces=(), positions=None, labels=(), panels=(), lights=(),
              aspect=1.0, tint=None, clearColor=None, highlight=None,
              highlightColor=None, top=None, bottom=None):
        """A complete Scene, checked against the engine limits. `highlight`
        is a (column, row) whose tile gets the hover slab, drawn last.
        `top` and `bottom` are the fractions of the window's height the
        camera keeps clear of the board (see fitCamera)."""
        pieceShapes, pieceLights = self.pieceShapes(pieces, positions)
        scene = Scene(camera=self.camera(aspect, top=top, bottom=bottom))
        scene.shapes = (self.boardShapes(tint) + pieceShapes
                        + self.highlightShapes(highlight, highlightColor))
        scene.lights = list(lights) + pieceLights
        scene.labels = list(labels)
        scene.panels = list(panels)
        if clearColor is not None:
            scene.clearColor = clearColor
        checkLights(scene.lights)
        return scene
