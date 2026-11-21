"""grid3d in the browser: a Grid3DView for pygbag, drawn by Strata's grid relay.

Under pygbag, Python can't reach WebGL, so the page carries a small Strata
web-kit scene, the grid relay (Strata's web/kit/grid-relay, whose WIRE.md
is the format spec), and this module sends it the same scene description a
desktop Grid3DView draws, as versioned binary messages:

    BOARD   the board's shapes and lights      (setBoard: once, or on a tint)
    PIECES  this tick's pieces                 (setPieces: once per game tick)
    HUD     screen labels and panels           (setLabels: when the HUD changes)
    VIEW    camera, clear colour, sun          (setBoard, resize)

The relay slides pieces between ticks itself, so nothing is sent per display
frame. Pieces are sent as anchors (where each piece slides from and to, from
the same Animator the desktop uses) plus shapes measured from their anchor,
so a piece's extras (eyes, a crown) and the bridges of a chain move with it
as on the desktop; this is why PieceStyle.extras must place its shapes
relative to the piece. A game that builds whole Scenes itself can call
drawScene() every frame, as on the desktop: only the parts that changed
since the last frame are sent.

Input comes back the other way: pollEvents() returns Strata-style events
(EVENT_KEY_DOWN with desktop Strata's scancodes, mouse, wheel, RESIZED, and
the web's FINGER_* events), and toPygameEvents() turns them into pygame
events, so a game's 2D input handling works unchanged in 3D.

The page: TEMPLATE (templatePath()) is a pygbag page template carrying the
relay's canvas and scripts and a 3D toggle. Build with
`pygbag --template <templatePath()> ...`, then copy the relay's prebuilt
files from Strata's release next to the built page with relay.py
(`python -m preponderous.graphik.grid3d.relay --strata <version> --dest
build/web`). The page starts in 3D, loading the relay alongside pygbag,
unless the game built it with templatePath(defaultView="2d"), the address
says ?view=2d, or the player last chose 2D on the button (remembered). The
game keeps its 2D canvas, and the page says why, whenever the 3D view can't
start; a page starting in 2D fetches nothing of the 3D view until the
button is pressed. The button sits in the page's top right corner;
buttonArea() says where, so a game's HUD can stay out from under it, and
touchScreen() whether the page is on a touch screen, where a game shows its
on-screen keys (touchkeys.py).

This module is the browser view's composition root: Grid3DWebView keeps
what it shows in a ViewState (state.py) and draws on a RelayDisplay over a
GridRelay (PlatformRelay by default); the page helpers read the page
through PAGE (a PageObjects). The wire format (wire.py), the events
(events.py) and the relays (adapters/) are re-exported here under their
old names.

Pure Python (struct, base64, json); pygbag's `platform` only in a browser.
"""
import os
import sys
import tempfile
import time

from .adapters.platform_relay import PlatformRelay
from .adapters.pygbag_page_objects import PygbagPageObjects
from .adapters.recording_relay import RecordingRelay
from .adapters.relay_display import RelayDisplay

from .events import (  # noqa: F401  (re-exported: grid3d.web's public names)
    EVENT_FINGER_CANCELED,
    EVENT_FINGER_DOWN,
    EVENT_FINGER_MOTION,
    EVENT_FINGER_UP,
    EVENT_KEY_DOWN,
    EVENT_KEY_UP,
    EVENT_MOUSE_BUTTON_DOWN,
    EVENT_MOUSE_BUTTON_UP,
    EVENT_MOUSE_MOTION,
    EVENT_MOUSE_WHEEL,
    EVENT_QUIT,
    EVENT_RESIZED,
    EVENT_TEXT_INPUT,
    EVENTS,
    Event,
    _KEY_NAMES,
    _MODS,
    pygameKey,
    toPygameEvents,
)
from .geometry import FAR_PLANE, NEAR_PLANE, SUN_DIRECTION, ViewGeometry  # noqa: F401
from .scene import CLEAR_COLOR, checkLights  # noqa: F401
from .errors import Unavailable
from .state import ViewState
from .wire import (  # noqa: F401  (re-exported: grid3d.web's public names)
    ANCHOR,
    BOARD,
    BRIDGE,
    COUNTS,
    HEADER,
    HUD,
    KINDS,
    LABEL,
    LIGHT,
    MAGIC,
    MAX_ANCHORS,
    MAX_COORDINATE,
    MAX_HUD_ITEMS,
    MAX_LIGHTS,
    MAX_SHADOWED_LIGHTS,
    MAX_SHAPES,
    PANEL,
    PIECE,
    PIECES,
    PIECES_HEAD,
    SHAPE,
    STATUS,
    VIEW,
    VIEW_BODY,
    WIRE_MAJOR,
    WIRE_MINOR,
    WORLD,
    WireError,
    _FLOAT_MAX,
    _checkCounts,
    _finite,
    _hudColor,
    _labelText,
    _light,
    _rgba,
    _shape,
    _within,
    _worldShapes,
    decode,
    encodeBoard,
    encodeHud,
    encodePieces,
    encodeView,
    header,
    readHeader,
)

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "pygbag.tmpl")


DEFAULT_VIEW_ATTRIBUTE = 'data-default-view="3d"'
VIEWS = ("2d", "3d")


def templatePath(defaultView="3d"):
    """The pygbag page template with the relay's canvas and the 2D/3D
    button (`pygbag --template <this> ...`). The page starts in
    `defaultView` ("3d", the default, or "2d") unless the address asks
    for a view (?view=2d or ?view=3d) or the player chose one on the
    button before (kept in the browser's localStorage). For "2d" a copy
    of the template saying so is written to the temporary folder and its
    path returned."""
    view = str(defaultView).lower()
    if view not in VIEWS:
        raise ValueError("defaultView is '2d' or '3d', not %r" % (defaultView,))
    if view == "3d":
        return TEMPLATE
    with open(TEMPLATE, encoding="utf-8") as handle:
        page = handle.read()
    if page.count(DEFAULT_VIEW_ATTRIBUTE) != 1:
        raise RuntimeError("graphik's page template has no single default view to change")
    page = page.replace(DEFAULT_VIEW_ATTRIBUTE, 'data-default-view="%s"' % view)
    path = os.path.join(tempfile.gettempdir(), "graphik-pygbag-%s.tmpl" % view)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)
    return path

# -- transports: adapters/platform_relay.py and adapters/recording_relay.py


# The page's JS objects (a PageObjects port): window.<name> under pygbag.
PAGE = PygbagPageObjects()


def pageObject(name):
    """window.<name> under pygbag, or None (not in a browser, or no such
    object on the page)."""
    return PAGE.get(name)


def wants3D():
    """True while the page's 3D toggle (the template's window.Graphik3D) is
    on and the relay's scripts, fetched only once it is pressed, have
    loaded, so Grid3DWebView.open() can begin. False outside a browser or
    on a page without the toggle."""
    toggle = pageObject("Graphik3D")
    return bool(toggle is not None and int(toggle.wanted()))


def parseArea(text):
    """(x, y, width, height) from the template's "x,y,width,height", or
    None for "" or anything else."""
    try:
        area = tuple(int(float(part)) for part in str(text).split(","))
    except ValueError:
        return None
    return area if len(area) == 4 and area[2] > 0 and area[3] > 0 else None


def buttonArea():
    """Where the page's 2D/3D button sits, as (x, y, width, height) in CSS
    pixels from the top left of the page (the units of Grid3DWebView's
    labels and panels), for keeping HUD text out from under it; None
    outside a browser, on a page without the button, or while it is
    hidden. The template keeps it in the top right corner."""
    toggle = pageObject("Graphik3D")
    if toggle is None:
        return None
    try:
        return parseArea(toggle.area())
    except Exception:  # an older template, without area()
        return None


def touchScreen():
    """True when the page is on a touch screen (a phone, a tablet), where
    a game shows its on-screen keys (touchkeys.TouchKeys): the template's
    Graphik3D.touch() says so for a coarse pointer, once the page has seen
    a touch, or when the address says ?touch=1 (?touch=0 says not). False
    outside a browser, unless the GRAPHIK_TOUCH environment variable is 1
    (for trying the keys on a desktop), and on a page without the button."""
    toggle = pageObject("Graphik3D")
    if toggle is None:
        return sys.platform != "emscripten" and os.environ.get("GRAPHIK_TOUCH") == "1"
    try:
        return bool(int(toggle.touch()))
    except Exception:  # an older template, without touch()
        return False


def set3D(on, reason=""):
    """Turns the page's 3D toggle on or off (off with a `reason` marks it
    unavailable, e.g. after Unavailable). Does nothing outside a browser."""
    toggle = pageObject("Graphik3D")
    if toggle is not None:
        toggle.set(1 if on else 0, str(reason))


# -- the view


class Grid3DWebView(ViewState):
    """Grid3DView's calls (setBoard, setPieces, setLabels, frame, drawScene,
    pollEvents, resize, close, pickCell), drawn by the page's grid relay."""

    EVENT_QUIT, EVENT_KEY_DOWN, EVENT_KEY_UP, EVENT_RESIZED = (
        EVENT_QUIT, EVENT_KEY_DOWN, EVENT_KEY_UP, EVENT_RESIZED)

    def __init__(self, relay, width, height, reducedMotion=False, clock=time.monotonic):
        ViewState.__init__(self, width, height, reducedMotion=reducedMotion, clock=clock)
        self.display = RelayDisplay(relay)
        self.strata = EVENTS
        self.isWindow = True

    @classmethod
    def open(cls, width=900, height=700, title="graphik", relay=None, maxBytes=4000000,
             reducedMotion=None, clock=time.monotonic, canvas="relay"):
        """Ask the page for its 3D view (it is downloaded only now, and only
        under maxBytes); raise Unavailable when there is none. `ready` says
        when it has loaded; what is sent before then waits in the page."""
        relay = relay or PlatformRelay(page=PAGE)
        state = relay.request({"canvas": canvas, "maxBytes": maxBytes, "title": title})
        if state.startswith("failed:"):
            raise Unavailable(state[len("failed:"):])
        if reducedMotion is None:
            reducedMotion = relay.reducedMotion()
        return cls(relay, width, height, reducedMotion=reducedMotion, clock=clock)

    @property
    def ready(self):
        return self.relay.state() == "ready"

    def failure(self):
        """Why the page's 3D view failed to load, or None."""
        state = self.relay.state()
        return state[len("failed:"):] if state.startswith("failed:") else None

    @property
    def relay(self):
        return self.display.relay

    @property
    def sent(self):
        """How many messages the relay has taken."""
        return self.display.sent

    @property
    def lastSent(self):
        """kind -> the last message of that kind sent (drawScene's check)."""
        return self.display.lastSent

    def _send(self, message, kind=None):
        self.display.send(message, kind)

    # -- what to draw (as Grid3DView)

    def setBoard(self, board, tint=None, lights=()):
        """The static part: call when the board, its theme or its tint changes."""
        self.placeBoard(board, tint, lights)
        checkLights(self.boardLights)
        self.restartAnimator()
        message = encodeBoard(board.boardShapes(tint), self.boardLights)
        if self.lastSent.get(BOARD) != message:  # the relay has it already
            self._send(message, BOARD)
        self._sendView()
        self._send(encodePieces(board, self.pieces, self.animator.tracks, 0.0), PIECES)

    def setPieces(self, pieces, tickSeconds=0.0, snap=False):
        """The dynamic part: call once per game tick (see Grid3DView)."""
        pieces = self.checkedPieces(pieces)
        _, lights = self.board.pieceShapes(pieces)
        checkLights(self.boardLights + lights)
        self.movePieces(pieces, tickSeconds, snap)
        tick = 0.0 if snap else self.animator.tickSeconds
        self._send(encodePieces(self.board, pieces, self.animator.tracks, tick), PIECES)

    def setLabels(self, labels=(), panels=()):
        """Screen text and the panels behind it."""
        self.placeLabels(labels, panels)
        self._send(encodeHud(self.labels, self.panels), HUD)

    def frame(self, now=None, present=True):
        """Nothing to do per frame: the relay draws on the page's own frames."""

    def drawScene(self, scene, present=True):
        """Draw a complete Scene, for games that build their own each frame:
        its shapes and lights go as the board, its labels and panels as the
        HUD, its camera as the view; only what changed since the last frame
        is sent."""
        scene.checkLimits()
        self.display.draw(scene, self.width / float(self.height), present)

    def _sendView(self):
        if self.board is not None:
            self._send(encodeView(self.camera()), VIEW)

    # -- the window

    def pollEvents(self):
        """Every event since the last poll (Event objects; see EVENTS)."""
        return self.display.poll()

    def resize(self, width, height):
        self.width, self.height = width, height
        self.display.resize(width, height)
        self._sendView()

    def setInsets(self, top=None, bottom=None):
        """As Grid3DView's (ViewGeometry.setInsets); the page is sent the
        new camera at once."""
        changed = super().setInsets(top, bottom)
        if changed:
            self._sendView()
        return changed

    def savePng(self, path):
        self.display.savePng(path)

    def close(self):
        self.display.close()
