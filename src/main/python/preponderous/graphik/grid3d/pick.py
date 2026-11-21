"""Screen <-> world: where a world point lands in the window, and which cell
is under a pointer.

The same right-handed look-at and OpenGL perspective a Grid3DView asks
Strata for (up is +y, Camera.fovDegrees vertical), so a press lands on the
tile the player sees, on the desktop and in the browser alike. Pure Python:
no Strata, no pygame.
"""

import math

from .board import BED_TOP


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _unit(a):
    length = math.sqrt(_dot(a, a))
    return (a[0] / length, a[1] / length, a[2] / length)


def cameraBasis(camera):
    """(forward, right, up) unit vectors of a Camera. ValueError for a
    camera that looks nowhere (its eye on its target) or straight up or
    down: Strata's look-at, with +y up, has no right or up for those either,
    so they draw nothing on the desktop; tilt the camera a little instead."""
    view = _sub(camera.target, camera.eye)
    if _dot(view, view) == 0.0:
        raise ValueError("the camera's eye is on its target, so it looks nowhere")
    forward = _unit(view)
    side = _cross(forward, (0.0, 1.0, 0.0))
    if _dot(side, side) < 1e-12:
        raise ValueError("the camera looks straight %s; tilt it a little (Strata's look-at "
                         "has +y up)" % ("down" if forward[1] < 0 else "up"))
    right = _unit(side)
    return forward, right, _cross(right, forward)


def projectToScreen(camera, point, width, height):
    """Where world point (x, y, z) lands in a width x height window, in
    pixels from the top-left, or None when it is behind the camera."""
    forward, right, up = cameraBasis(camera)
    offset = _sub(point, camera.eye)
    depth = _dot(offset, forward)
    if depth <= 0:
        return None
    focal = 1.0 / math.tan(math.radians(camera.fovDegrees) / 2.0)
    aspect = width / float(height)
    ndcX = focal / aspect * _dot(offset, right) / depth
    ndcY = focal * _dot(offset, up) / depth
    return ((ndcX + 1.0) / 2.0 * width, (1.0 - ndcY) / 2.0 * height)


def screenRay(camera, x, y, width, height):
    """The direction (not normalised) from the camera's eye through window
    pixel (x, y)."""
    forward, right, up = cameraBasis(camera)
    focal = 1.0 / math.tan(math.radians(camera.fovDegrees) / 2.0)
    aspect = width / float(height)
    ndcX = x / float(width) * 2.0 - 1.0
    ndcY = 1.0 - y / float(height) * 2.0
    return tuple(
        forward[i] + right[i] * ndcX * aspect / focal + up[i] * ndcY / focal
        for i in range(3)
    )


def pickPoint(camera, x, y, width, height, planeY=BED_TOP):
    """World (x, z) where the ray through window pixel (x, y) meets the
    horizontal plane at height `planeY` (the tiles' top), or None when the
    pixel looks above the horizon."""
    direction = screenRay(camera, x, y, width, height)
    if direction[1] >= 0:
        return None
    t = (planeY - camera.eye[1]) / direction[1]
    if t <= 0:
        return None  # the plane is behind the camera
    return (camera.eye[0] + direction[0] * t, camera.eye[2] + direction[2] * t)


def pickCell(camera, board, x, y, width, height):
    """The (column, row) of the board cell under window pixel (x, y), or
    None (off the board, out of its viewport, or above the horizon). The
    whole cell counts, gaps between tiles included, so no press between two
    tiles is lost. The 3D form of a 2D grid's pixel-to-cell division."""
    if x is None or y is None:
        return None
    point = pickPoint(camera, x, y, width, height)
    if point is None:
        return None
    return board.cellAt(*point)


def cellScreenPosition(camera, board, column, row, width, height, y=BED_TOP):
    """Where the middle of cell (column, row), `y` above the bed, lands in
    the window (pixels from the top-left), or None behind the camera: for
    aiming a tap at a piece, or putting a note beside a tile."""
    cx, cz = board.cellCenter(column, row)
    return projectToScreen(camera, (cx, y, cz), width, height)
