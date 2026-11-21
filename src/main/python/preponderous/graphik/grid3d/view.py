"""Grid3DView: draws a GridBoard and its pieces with Strata (desktop).

The Strata Python binding (`strata-engine`, installed with the
`graphik[strata]` extra) loads libstrata, a native library: a released build
is downloaded once, checked against its pinned SHA-256 and cached, or
STRATA_LIBRARY points at a local build. Strata ships Linux x64 and Windows
x64 libraries, so this view runs there; anywhere else, or when the library
can't load or no window can open, Grid3DView.open() raises Unavailable with a
reason a player can act on, and the game keeps its 2D view.

In a browser (pygbag, where sys.platform is "emscripten"), Grid3DView.open()
returns a Grid3DWebView instead (web.py): the same calls, drawn by the
page's Strata grid relay. See web.py for what the page needs.

Usage, once per game:

    view = Grid3DView.open(900, 700, "My game")       # or headless=True
    view.setBoard(GridBoard(columns, rows, theme))    # when the board changes
    view.setPieces(pieces, tickSeconds)               # once per game tick
    view.setLabels(labels, panels)                    # when the HUD changes
    view.frame()                                      # once per display frame
    view.close()

    view.pickCell(x, y)        # the (column, row) under a pointer, or None

The board and labels are kept between frames; pieces slide between their
cells over one tick (see animate.Animator).
"""

import ctypes
import os
import struct
import sys
import time

from .errors import Unavailable
from .geometry import FAR_PLANE, NEAR_PLANE, SUN_DIRECTION, ViewGeometry  # noqa: F401
from .state import ViewState

STRATA_VERSION = "0.8.0"
STRATA_PLATFORMS = ("linux", "win32")
INSTALL_HINT = "pip install 'graphik[strata]'"


# Strata's StrataRenderItem: int32 kind, float3 position, float3 scale,
# float4 colour (44 bytes)
_RENDER_ITEM = struct.Struct("<i3f3f4f")


def renderItems(strata, shapes):
    """The shapes as the binding's RenderItems: a ctypes array, which
    submit_primitives takes without a copy, packed in one pass. Building a
    RenderItem object per shape costs about eight times as much, and a board
    of a few thousand tiles is drawn every frame. A shape the fast path
    can't pack (a 3-part colour), or a binding whose RenderItem isn't the
    44-byte structure, gets a list of RenderItem objects as before."""
    shapes = list(shapes)
    item = strata.RenderItem
    if isinstance(item, type) and issubclass(item, ctypes.Structure) \
            and ctypes.sizeof(item) == _RENDER_ITEM.size:
        pack = _RENDER_ITEM.pack
        try:
            data = b"".join([pack(sh.kind, *sh.position, *sh.scale, *sh.color) for sh in shapes])
        except (struct.error, TypeError):
            pass
        else:
            return (item * len(shapes)).from_buffer_copy(data)
    return [item(sh.kind, sh.position, sh.scale, sh.color) for sh in shapes]


def labelBytes(text):
    """A label's text as Strata takes it: UTF-8 with no NUL (a C string would
    end there; the browser backend drops them too), a lone surrogate as '?'
    (what Strata draws for any character outside its font)."""
    return str(text).replace("\0", "").encode("utf-8", "replace")


def loadStrata(platform=None):
    """Import the binding and load libstrata; raise Unavailable if either fails."""
    platform = sys.platform if platform is None else platform
    if platform not in STRATA_PLATFORMS and not os.environ.get("STRATA_LIBRARY"):
        raise Unavailable("Strata has no library for this system (%s)" % platform)
    # Headless rendering without a GPU driver (CI, WSL) goes through Mesa's
    # software rasteriser; harmless where a GPU exists.
    os.environ.setdefault("GALLIUM_DRIVER", "llvmpipe")
    try:
        import strata
    except ImportError:
        raise Unavailable(
            "the strata-engine package isn't installed (%s)" % INSTALL_HINT
        )
    try:
        if os.environ.get("STRATA_LIBRARY"):
            return strata, strata.load()
        return strata, strata.load_release(STRATA_VERSION)
    except Exception as error:  # download failed, checksum mismatch, bad library
        raise Unavailable("the Strata library couldn't be loaded: %s" % error)


class Grid3DView(ViewState):
    """One Strata engine (a window, or headless for screenshots and tests)."""

    def __init__(self, strata, lib, engine, width, height, isWindow,
                 reducedMotion=False, clock=time.monotonic):
        ViewState.__init__(self, width, height, reducedMotion=reducedMotion, clock=clock)
        self.strata, self.lib, self.engine = strata, lib, engine
        self.isWindow = isWindow
        self.EVENT_QUIT = strata.EVENT_QUIT
        self.EVENT_KEY_DOWN = strata.EVENT_KEY_DOWN
        self.EVENT_KEY_UP = strata.EVENT_KEY_UP
        self.EVENT_RESIZED = strata.EVENT_RESIZED

    @classmethod
    def open(cls, width=900, height=700, title="graphik", headless=False,
             reducedMotion=False, clock=time.monotonic):
        """Open a window (or a headless surface); raise Unavailable if Strata
        can't run here. In a browser this is a Grid3DWebView (web.py), which
        has no headless form."""
        if sys.platform == "emscripten":
            if headless:
                raise Unavailable("a browser has no headless 3D view")
            from .web import Grid3DWebView

            return Grid3DWebView.open(width, height, title,
                                      reducedMotion=reducedMotion or None, clock=clock)
        if headless and sys.platform.startswith("linux"):
            # Linux renders headless through EGL with no window. On Windows the
            # headless engine is a hidden SDL window, which the dummy driver
            # can't create, so it is only forced here.
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        strata, lib = loadStrata()
        surface = strata.SURFACE_HEADLESS if headless else strata.SURFACE_WINDOW
        try:
            engine = strata.Engine(
                lib, width, height, surface=surface, title=None if headless else title
            )
        except Exception as error:  # no display, no GPU driver
            raise Unavailable("no Strata window could be opened: %s" % error)
        view = cls(strata, lib, engine, width, height, not headless,
                   reducedMotion=reducedMotion, clock=clock)
        lighting = lib.lighting_defaults(strata.LIGHTING_SUN)
        lighting.shadow_distance = 40.0
        lighting.fog = 0
        engine.set_lighting(lighting)
        engine.set_sun_direction((-0.45, 0.85, 0.35))
        return view

    # -- what to draw

    def setBoard(self, board, tint=None, lights=()):
        """The static part: call when the board, its theme or its tint changes."""
        self.placeBoard(board, tint, lights)
        self.restartAnimator()

    def setPieces(self, pieces, tickSeconds=0.0, snap=False):
        """The dynamic part: call once per game tick. Pieces slide from where
        they were drawn to their new cells over `tickSeconds`; `snap=True`
        (a restart, a new level) puts them all straight on their cells."""
        self.movePieces(self.checkedPieces(pieces), tickSeconds, snap)

    def setLabels(self, labels=(), panels=()):
        """Screen text and the panels behind it."""
        self.placeLabels(labels, panels)

    def frame(self, now=None, present=True):
        """Draw one frame (pieces at their positions for `now`)."""
        self.drawScene(self.scene(now), present=present)

    # -- drawing a Scene

    def drawScene(self, scene, present=True):
        """Draw a complete Scene, for callers that build their own."""
        scene.checkLimits()
        s, engine = self.strata, self.engine
        camera = scene.camera
        if camera is not None:
            engine.set_camera(
                self.lib.look_at(
                    camera.eye,
                    camera.target,
                    fov_y_degrees=camera.fovDegrees,
                    aspect=self.width / float(self.height),
                    near_plane=0.3,
                    far_plane=200.0,
                )
            )
        lights = []
        for light in scene.lights:
            point = s.PointLight()
            point.position = light.position
            point.color = light.color
            point.range = light.radius
            point.intensity = light.intensity
            point.flags = s.POINT_LIGHT_CAST_SHADOWS if light.castShadows else 0
            lights.append(point)
        engine.set_point_lights(lights)
        engine.begin_frame(clear_color=scene.clearColor)
        engine.submit_primitives(renderItems(s, scene.shapes))
        if scene.panels:
            engine.submit_rects(
                [s.Rect(p.x, p.y, p.width, p.height, p.color) for p in scene.panels]
            )
        if scene.labels:
            engine.submit_text(
                [
                    s.Text(l.x, l.y, l.pixelSize, s.TEXT_SHADOW, l.color, labelBytes(l.text))
                    for l in scene.labels
                ]
            )
        engine.end_frame()
        if present:
            engine.present()

    # -- the window

    def pollEvents(self):
        """Every pending Strata event (EVENT_QUIT, EVENT_KEY_DOWN, ...)."""
        events = []
        while True:
            event = self.engine.poll_event()
            if event is None:
                return events
            events.append(event)

    def resize(self, width, height):
        self.width, self.height = width, height
        self.engine.resize(width, height)

    def savePng(self, path):
        """The last frame as a PNG (headless or windowed)."""
        self.engine.save_screenshot_png(path)

    def close(self):
        if self.engine is not None:
            self.engine.close()
            self.engine = None
