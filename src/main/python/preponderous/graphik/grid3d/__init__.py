"""graphik's 3D grid view: a grid game's board drawn in 3D with Strata.

A game describes its board once (GridBoard + Theme), reports what stands on
each cell every tick (Piece), and a Grid3DView draws it, sliding pieces
between cells. The scene description (scene.py, board.py, animate.py) is pure
Python and needs no GPU; only Grid3DView.open() loads Strata, through the
optional `graphik[strata]` extra. Desktop Linux and Windows only for now.

Importing this package imports neither Strata nor pygame.
"""

from .animate import Animator, interpolatePosition
from .board import BED_TOP, GridBoard, Piece, PieceStyle, Theme, cellCenter, fitCamera
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
from .view import STRATA_VERSION, Grid3DView, Unavailable

__all__ = [
    "Animator", "interpolatePosition",
    "BED_TOP", "GridBoard", "Piece", "PieceStyle", "Theme", "cellCenter", "fitCamera",
    "CAPSULE", "CLEAR_COLOR", "CUBE", "CYLINDER", "DIM_TEXT_COLOR",
    "MAX_POINT_LIGHTS", "MAX_SHADOWED_POINT_LIGHTS", "SPHERE", "TEXT_COLOR",
    "Camera", "Label", "Light", "Panel", "Scene", "SceneLimitError", "Shape",
    "fitText", "rgb255", "rgba", "shade",
    "STRATA_VERSION", "Grid3DView", "Unavailable",
]
