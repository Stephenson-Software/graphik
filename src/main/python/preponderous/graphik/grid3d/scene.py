"""A 3D scene as plain data: shapes, screen text and panels, lights, a camera.

Nothing here imports Strata or pygame, so a game's state-to-scene code can be
built and tested without a GPU. A Grid3DView (view.py) draws a Scene.

World axes: x runs along a grid's columns, z along its rows (row 0 is the far
edge, away from a camera south of the board), y is up. One cell is one world
unit, and a board is centred on the origin.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Shape kinds. The values match Strata's PRIMITIVE_* constants.
CUBE, CAPSULE, CYLINDER, SPHERE = 0, 1, 2, 3
SHAPE_KINDS = (CUBE, CAPSULE, CYLINDER, SPHERE)

# Engine limits (strata.h). A Scene over them is rejected with SceneLimitError
# rather than left for the engine to refuse or truncate.
MAX_POINT_LIGHTS = 32
MAX_SHADOWED_POINT_LIGHTS = 4

TEXT_COLOR = (0.97, 0.96, 0.92, 1.0)
DIM_TEXT_COLOR = (0.82, 0.80, 0.74, 1.0)
CLEAR_COLOR = (0.10, 0.12, 0.16, 1.0)

Color3 = Tuple[float, float, float]
Color4 = Tuple[float, float, float, float]
Vec3 = Tuple[float, float, float]


class SceneLimitError(ValueError):
    """A scene asks for more than the engine can draw (see MAX_* above)."""


@dataclass
class Shape:
    """One of Strata's primitives. Strata 0.7.0 can't rotate primitives, so a
    shape is axis-aligned; `scale` is its size along x, y and z."""

    kind: int
    position: Vec3
    scale: Vec3
    color: Color4


@dataclass
class Label:
    """Screen text: x/y in pixels from the top-left of the window."""

    text: str
    x: float
    y: float
    pixelSize: float
    color: Color4 = TEXT_COLOR


@dataclass
class Panel:
    """A filled screen rectangle, in pixels from the top-left, drawn under text."""

    x: float
    y: float
    width: float
    height: float
    color: Color4 = (0.0, 0.0, 0.0, 0.6)


@dataclass
class Light:
    """A point light. At most MAX_SHADOWED_POINT_LIGHTS may cast shadows."""

    position: Vec3
    color: Color3
    radius: float
    intensity: float
    castShadows: bool = False


@dataclass
class Camera:
    eye: Vec3
    target: Vec3
    fovDegrees: float = 42.0


@dataclass
class Scene:
    shapes: List[Shape] = field(default_factory=list)
    labels: List[Label] = field(default_factory=list)
    panels: List[Panel] = field(default_factory=list)
    lights: List[Light] = field(default_factory=list)
    camera: Optional[Camera] = None
    clearColor: Color4 = CLEAR_COLOR

    def checkLimits(self):
        """Raise SceneLimitError if the scene is over an engine limit."""
        checkLights(self.lights)
        for shape in self.shapes:
            if shape.kind not in SHAPE_KINDS:
                raise SceneLimitError("unknown shape kind %r" % (shape.kind,))


def checkLights(lights):
    if len(lights) > MAX_POINT_LIGHTS:
        raise SceneLimitError(
            "%d point lights; Strata draws at most %d"
            % (len(lights), MAX_POINT_LIGHTS)
        )
    shadowed = sum(1 for light in lights if light.castShadows)
    if shadowed > MAX_SHADOWED_POINT_LIGHTS:
        raise SceneLimitError(
            "%d shadow-casting lights; Strata allows at most %d"
            % (shadowed, MAX_SHADOWED_POINT_LIGHTS)
        )


def rgb255(color):
    """A 0-255 (r, g, b[, a]) colour as 0-1 floats (r, g, b)."""
    return (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)


def rgba(color, alpha=1.0):
    """(r, g, b) as (r, g, b, alpha)."""
    return (color[0], color[1], color[2], alpha)


def shade(color, factor):
    """Scale a 0-1 colour's r, g, b by `factor`, clamped to 0-1."""
    return tuple(max(0.0, min(1.0, c * factor)) for c in color[:3])


def fitText(text, width, pixelSize, margin=18):
    """Cut text to what fits across `width` pixels. Strata's built-in font is
    monospaced, about one pixel size wide per character."""
    room = max(4, int((width - 2 * margin) / pixelSize))
    return text if len(text) <= room else text[: room - 3] + "..."
