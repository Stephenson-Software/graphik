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

import sys
import time

from .adapters.binding_strata_loader import (  # noqa: F401  (re-exported)
    INSTALL_HINT,
    STRATA_PLATFORMS,
    STRATA_VERSION,
    BindingStrataLoader,
    loadStrata,
)
from .adapters.strata_engine import _RENDER_ITEM, StrataEngine, labelBytes, renderItems  # noqa: F401
from .errors import Unavailable
from .geometry import FAR_PLANE, NEAR_PLANE, SUN_DIRECTION, ViewGeometry  # noqa: F401
from .state import ViewState

class Grid3DView(ViewState):
    """One Strata engine (a window, or headless for screenshots and tests)."""

    def __init__(self, strata, lib, engine, width, height, isWindow,
                 reducedMotion=False, clock=time.monotonic):
        ViewState.__init__(self, width, height, reducedMotion=reducedMotion, clock=clock)
        self.display = StrataEngine(strata, lib, engine)
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
        display = BindingStrataLoader().open(width, height, title, headless)
        return cls(display.strata, display.lib, display.engine, width, height, not headless,
                   reducedMotion=reducedMotion, clock=clock)

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

    # -- the binding, which games reach too

    @property
    def strata(self):
        return self.display.strata

    @property
    def lib(self):
        return self.display.lib

    @property
    def engine(self):
        return self.display.engine

    # -- drawing a Scene

    def drawScene(self, scene, present=True):
        """Draw a complete Scene, for callers that build their own."""
        scene.checkLimits()
        self.display.draw(scene, self.width / float(self.height), present)

    # -- the window

    def pollEvents(self):
        """Every pending Strata event (EVENT_QUIT, EVENT_KEY_DOWN, ...)."""
        return self.display.poll()

    def resize(self, width, height):
        self.width, self.height = width, height
        self.display.resize(width, height)

    def savePng(self, path):
        """The last frame as a PNG (headless or windowed)."""
        self.display.savePng(path)

    def close(self):
        self.display.close()
