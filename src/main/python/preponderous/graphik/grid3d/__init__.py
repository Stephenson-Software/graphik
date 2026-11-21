"""graphik's 3D grid view: a grid game's board drawn in 3D with Strata.

A game describes its board once (GridBoard + Theme), reports what stands on
each cell every tick (Piece), and a Grid3DView draws it, sliding pieces
between cells. The scene description (scene.py, board.py, animate.py) is pure
Python and needs no GPU; only Grid3DView.open() loads Strata, through the
optional `graphik[strata]` extra, on desktop Linux and Windows. In a browser
(pygbag) Grid3DView.open() returns web.Grid3DWebView, drawn by Strata's grid
relay in the page.

Helpers shared by the 3D views of grid games: picking (pick.py: the cell
under a pointer, where a point lands on screen), text in Strata's font
(text.py: measure, fit, wrap, centre), screen buttons and a Graphik
stand-in for running 2D screens under a 3D view (ui.py), and a bar of
on-screen keys for touch screens, drawn alike in 2D and 3D (touchkeys.py).

The API reference, with an example for each part, is docs/grid3d.md.

Importing this package imports neither Strata nor pygame.
"""

from .animate import Animator, interpolatePosition
from .board import (
    BED_TOP,
    GridBoard,
    Piece,
    PieceStyle,
    Theme,
    Tile,
    Viewport,
    cellCenter,
    fitCamera,
)
from .pick import cellScreenPosition, pickCell, pickPoint, projectToScreen, screenRay
from .scene import (
    CAPSULE,
    CLEAR_COLOR,
    CUBE,
    CYLINDER,
    DIM_TEXT_COLOR,
    MAX_POINT_LIGHTS,
    MAX_SHADOWED_POINT_LIGHTS,
    SPHERE,
    TEXT_COLOR,
    Camera,
    Label,
    Light,
    Panel,
    Scene,
    SceneLimitError,
    Shape,
    fitText,
    rgb255,
    rgba,
    shade,
)
from .text import centredLabel, measureText, wrapText
from .ui import (
    Button,
    RecordedButton,
    RecordedDisplay,
    RecordedImage,
    RecordedRect,
    RecordedText,
    ScreenRecorder,
    drawButtons,
    hoverColor,
)
from .touchkeys import MIN_TARGET, MORE, KeySlot, TouchKey, TouchKeys
from .view import STRATA_VERSION, Grid3DView, Unavailable

__all__ = [
    "Animator", "interpolatePosition",
    "BED_TOP", "GridBoard", "Piece", "PieceStyle", "Theme", "Tile", "Viewport",
    "cellCenter", "fitCamera",
    "cellScreenPosition", "pickCell", "pickPoint", "projectToScreen", "screenRay",
    "CAPSULE", "CLEAR_COLOR", "CUBE", "CYLINDER", "DIM_TEXT_COLOR",
    "MAX_POINT_LIGHTS", "MAX_SHADOWED_POINT_LIGHTS", "SPHERE", "TEXT_COLOR",
    "Camera", "Label", "Light", "Panel", "Scene", "SceneLimitError", "Shape",
    "fitText", "rgb255", "rgba", "shade",
    "centredLabel", "measureText", "wrapText",
    "Button", "RecordedButton", "RecordedDisplay", "RecordedImage", "RecordedRect", "RecordedText",
    "ScreenRecorder", "drawButtons", "hoverColor",
    "MIN_TARGET", "MORE", "KeySlot", "TouchKey", "TouchKeys",
    "STRATA_VERSION", "Grid3DView", "Unavailable",
]
