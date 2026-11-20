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

Pure Python (struct, base64, json); pygbag's `platform` only in a browser.
"""

import base64
import json
import os
import struct
import sys
import tempfile
import time
from types import SimpleNamespace

from .animate import Animator
from .scene import CLEAR_COLOR, checkLights
from .view import ViewGeometry, Unavailable

WIRE_MAJOR, WIRE_MINOR = 1, 0
MAGIC = b"G3"
BOARD, PIECES, HUD, VIEW = 1, 2, 3, 4
KINDS = (BOARD, PIECES, HUD, VIEW)
WORLD, PIECE, BRIDGE = 0, 1, 2

HEADER = struct.Struct("<2sBBBBH")  # 8 bytes
SHAPE = struct.Struct("<BBHHH3f3f4f")  # 48 bytes
LIGHT = struct.Struct("<BBH3f3fff")  # 36 bytes
ANCHOR = struct.Struct("<4f")  # 16 bytes
PANEL = struct.Struct("<4f4f")  # 32 bytes
LABEL = struct.Struct("<3f4fHH")  # 32 bytes, then the text padded to 4
VIEW_BODY = struct.Struct("<3f3f3f4f3f")  # 64 bytes
COUNTS = struct.Struct("<II")
PIECES_HEAD = struct.Struct("<fIII")

# Grid3DView's lighting and projection (view.py), sent with every VIEW so the
# relay draws what the desktop draws.
SUN_DIRECTION = (-0.45, 0.85, 0.35)
NEAR_PLANE, FAR_PLANE = 0.3, 200.0

# Strata's event types (strata.h) and the web relay's additions.
EVENT_QUIT, EVENT_KEY_DOWN, EVENT_KEY_UP = 1, 2, 3
EVENT_MOUSE_MOTION, EVENT_MOUSE_BUTTON_DOWN, EVENT_MOUSE_BUTTON_UP = 4, 5, 6
EVENT_MOUSE_WHEEL, EVENT_RESIZED, EVENT_TEXT_INPUT = 7, 8, 9
EVENT_FINGER_DOWN, EVENT_FINGER_UP, EVENT_FINGER_MOTION, EVENT_FINGER_CANCELED = 16, 17, 18, 19

# Stands in for the strata module where games read event types from it
# (view.strata.EVENT_QUIT), so the same loop reads desktop and web events.
EVENTS = SimpleNamespace(
    EVENT_QUIT=EVENT_QUIT, EVENT_KEY_DOWN=EVENT_KEY_DOWN, EVENT_KEY_UP=EVENT_KEY_UP,
    EVENT_MOUSE_MOTION=EVENT_MOUSE_MOTION, EVENT_MOUSE_BUTTON_DOWN=EVENT_MOUSE_BUTTON_DOWN,
    EVENT_MOUSE_BUTTON_UP=EVENT_MOUSE_BUTTON_UP, EVENT_MOUSE_WHEEL=EVENT_MOUSE_WHEEL,
    EVENT_RESIZED=EVENT_RESIZED, EVENT_TEXT_INPUT=EVENT_TEXT_INPUT,
    EVENT_FINGER_DOWN=EVENT_FINGER_DOWN, EVENT_FINGER_UP=EVENT_FINGER_UP,
    EVENT_FINGER_MOTION=EVENT_FINGER_MOTION, EVENT_FINGER_CANCELED=EVENT_FINGER_CANCELED,
)

# What the relay's send() returns for a refused message (WIRE.md, "Errors").
STATUS = {
    -1: "not a grid relay message",
    -2: "another major version of the wire format",
    -3: "truncated",
    -4: "unknown message kind",
    -5: "a bad value",
    -6: "over the relay's limits",
}

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


# -- the wire format (Strata's web/kit/grid-relay/WIRE.md, format 1.0)


class WireError(ValueError):
    """A message the relay would refuse. `status` is the relay's code."""

    def __init__(self, status, detail=""):
        self.status = status
        reason = STATUS.get(status, "status %d" % status)
        super().__init__(reason + (": " + detail if detail else ""))


def header(kind):
    return HEADER.pack(MAGIC, WIRE_MAJOR, WIRE_MINOR, kind, 0, 0)


def _rgba(color):
    color = tuple(color)
    return (color + (1.0,) * (4 - len(color)))[:4]


def _shape(kind, attach, a, b, position, scale, color):
    return SHAPE.pack(kind, attach, a, b, 0, *position, *scale, *_rgba(color))


def _light(attach, a, light, offset=(0.0, 0.0)):
    x, y, z = light.position
    return LIGHT.pack(
        attach, 1 if light.castShadows else 0, a,
        x - offset[0], y, z - offset[1], *light.color, light.radius, light.intensity,
    )


def encodeBoard(shapes, lights=()):
    """BOARD: world shapes and lights."""
    out = [header(BOARD), COUNTS.pack(len(shapes), len(lights))]
    out += [_shape(s.kind, WORLD, 0, 0, s.position, s.scale, s.color) for s in shapes]
    out += [_light(WORLD, 0, light) for light in lights]
    return b"".join(out)


def _labelText(text):
    data = str(text).replace("\0", "").encode("utf-8")
    if len(data) > 65535:
        data = data[:65535].decode("utf-8", "ignore").encode("utf-8")
    return data


def encodeHud(labels=(), panels=()):
    """HUD: screen panels (drawn first) and labels, in CSS pixels."""
    out = [header(HUD), COUNTS.pack(len(panels), len(labels))]
    for p in panels:
        out.append(PANEL.pack(p.x, p.y, p.width, p.height, *_rgba(p.color)))
    for label in labels:
        text = _labelText(label.text)
        out.append(LABEL.pack(label.x, label.y, label.pixelSize, *_rgba(label.color), len(text), 0))
        out.append(text + b"\0" * (-len(text) % 4))
    return b"".join(out)


def encodeView(camera, clearColor=CLEAR_COLOR, sun=SUN_DIRECTION, near=NEAR_PLANE, far=FAR_PLANE):
    """VIEW: the camera, clear colour and direction to the sun."""
    return header(VIEW) + VIEW_BODY.pack(
        *camera.eye, *camera.target, camera.fovDegrees, near, far, *_rgba(clearColor), *sun
    )


def encodePieces(board, pieces, tracks, tickSeconds):
    """PIECES for this tick. `tracks` maps a piece id to ((x0, z0), (x1, z1)),
    from an Animator; a piece without one stands still on its cell. With a
    viewport, only the pieces in it are sent."""
    pieces = [p for p in pieces if board.visible(p.column, p.row)]
    index = {}
    anchors, shapes, lights = [], [], []
    for i, piece in enumerate(pieces):
        end = board.cellCenter(piece.column, piece.row)
        start, end = tracks.get(piece.id, (end, end))
        index[piece.id] = i
        anchors.append(ANCHOR.pack(start[0], start[1], end[0], end[1]))
        # The piece's own shapes and glow, drawn at its end cell and sent as
        # offsets from it. A lone piece has no bridges; they come below.
        alone, glow = board.pieceShapes([piece], positions={piece.id: end})
        for s in alone:
            x, y, z = s.position
            shapes.append(_shape(s.kind, PIECE, i, 0, (x - end[0], y, z - end[1]), s.scale, s.color))
        lights += [_light(PIECE, i, light, end) for light in glow]
    # Chain bridges, in pieceShapes' order. Each is drawn with both ends at
    # the origin, which gives its size across; the relay spans the anchors.
    for a, b in board.bridgePairs(pieces):
        s = board.bridgeShape(a, b, (0.0, 0.0), (0.0, 0.0))
        shapes.append(_shape(s.kind, BRIDGE, index[a.id], index[b.id], s.position, s.scale, s.color))
    head = header(PIECES) + PIECES_HEAD.pack(tickSeconds, len(anchors), len(shapes), len(lights))
    return head + b"".join(anchors) + b"".join(shapes) + b"".join(lights)


def readHeader(message):
    """(major, minor, kind) of a message, or WireError as the relay would
    refuse it: not a relay message, another major version, truncated."""
    if len(message) < 2 or bytes(message[:2]) != MAGIC:
        raise WireError(-1)
    if len(message) < 3:
        raise WireError(-3, "no version")
    if message[2] != WIRE_MAJOR:
        major = message[2]
        minor = message[3] if len(message) > 3 else 0
        raise WireError(-2, "wire format %d.%d; this reads %d.x" % (major, minor, WIRE_MAJOR))
    if len(message) < HEADER.size:
        raise WireError(-3, "header")
    _, major, minor, kind, _, _ = HEADER.unpack_from(message)
    if kind not in KINDS:
        raise WireError(-4, "kind %d" % kind)
    return major, minor, kind


def decode(message):
    """A message read back as (kind, contents): for tests and tools, with
    the relay's checks (version, kind, counts against the length). A minor
    version above 0 may carry fields after the ones 1.0 knows; they are
    ignored, as the relay ignores them."""
    _, _, kind = readHeader(message)
    body = memoryview(message)[HEADER.size:]

    def take(fmt, offset, count=1):
        end = offset + fmt.size * count
        if end > len(body):
            raise WireError(-3, "kind %d" % kind)
        return [fmt.unpack_from(body, offset + fmt.size * i) for i in range(count)], end

    def shape(r):
        return {"kind": r[0], "attach": r[1], "a": r[2], "b": r[3],
                "position": r[5:8], "scale": r[8:11], "color": r[11:15]}

    def light(r):
        return {"attach": r[0], "castShadows": bool(r[1] & 1), "a": r[2],
                "position": r[3:6], "color": r[6:9], "radius": r[9], "intensity": r[10]}

    if kind == BOARD:
        (counts,), at = take(COUNTS, 0)
        shapes, at = take(SHAPE, at, counts[0])
        lights, at = take(LIGHT, at, counts[1])
        return kind, {"shapes": [shape(r) for r in shapes], "lights": [light(r) for r in lights]}
    if kind == PIECES:
        (head,), at = take(PIECES_HEAD, 0)
        anchors, at = take(ANCHOR, at, head[1])
        shapes, at = take(SHAPE, at, head[2])
        lights, at = take(LIGHT, at, head[3])
        return kind, {"tickSeconds": head[0], "anchors": [tuple(a) for a in anchors],
                      "shapes": [shape(r) for r in shapes], "lights": [light(r) for r in lights]}
    if kind == HUD:
        (counts,), at = take(COUNTS, 0)
        panels, at = take(PANEL, at, counts[0])
        labels = []
        for _ in range(counts[1]):
            (r,), at = take(LABEL, at)
            length = r[7]
            if at + length > len(body):
                raise WireError(-3, "label text")
            text = bytes(body[at:at + length]).decode("utf-8")
            at += length + (-length % 4)
            labels.append({"x": r[0], "y": r[1], "pixelSize": r[2], "color": r[3:7], "text": text})
        return kind, {"panels": [{"rect": p[:4], "color": p[4:8]} for p in panels], "labels": labels}
    (r,), _ = take(VIEW_BODY, 0)
    return kind, {"eye": r[0:3], "target": r[3:6], "fovDegrees": r[6], "near": r[7], "far": r[8],
                  "clearColor": r[9:13], "sun": r[13:16]}


# -- transports


class PlatformRelay:
    """The page's window.StrataGridRelay, through pygbag's platform.window."""

    def __init__(self, relay=None):
        if relay is None:
            relay = pageObject("StrataGridRelay")
            if relay is None:
                raise Unavailable(
                    "this page has no 3D view (grid-relay.js isn't loaded; on graphik's "
                    "template it loads once the 3D toggle is on, when wants3D() turns true)"
                )
        self.js = relay

    def request(self, options):
        return str(self.js.request(json.dumps(options)))

    def state(self):
        return str(self.js.state())

    def send(self, message):
        return int(self.js.send(base64.b64encode(message).decode("ascii")))

    def poll(self):
        return json.loads(str(self.js.poll()))

    def reducedMotion(self):
        return bool(int(self.js.reducedMotion()))

    def close(self):
        self.js.close()


class RecordingRelay:
    """A relay that keeps what it is sent: for tests, and for recording a
    game to play into the relay's test page (index.html?wire=...)."""

    def __init__(self, reducedMotion=False, state="ready"):
        self.messages, self.events, self.motion = [], [], reducedMotion
        self.status = state
        self.closed = False

    def request(self, options):
        self.options = options
        return self.status

    def state(self):
        return self.status

    def send(self, message):
        try:
            readHeader(message)
        except WireError as error:
            return error.status
        self.messages.append(bytes(message))
        return 0

    def poll(self):
        events, self.events = self.events, []
        return events

    def reducedMotion(self):
        return self.motion

    def close(self):
        self.closed = True

    def wireJson(self):
        return json.dumps([base64.b64encode(m).decode("ascii") for m in self.messages])


def pageObject(name):
    """window.<name> under pygbag, or None (not in a browser, or no such
    object on the page)."""
    if sys.platform != "emscripten":
        return None
    import platform  # pygbag's, not the standard library's

    return getattr(platform.window, name, None)


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


class Event:
    """A Strata-style event (the fields of strata.h's StrataEvent, plus the
    web's pointer, id, nx, ny for touch and the browser's key)."""

    __slots__ = ("type", "scancode", "modifiers", "repeat", "button", "width", "height",
                 "x", "y", "dx", "dy", "text", "pointer", "id", "nx", "ny", "key", "pressure")

    def __init__(self, d):
        for name in self.__slots__:
            setattr(self, name, d.get(name, "" if name in ("text", "pointer", "key") else 0))

    def __repr__(self):
        return "Event(%s)" % ", ".join(
            "%s=%r" % (n, getattr(self, n)) for n in self.__slots__ if getattr(self, n))


class Grid3DWebView(ViewGeometry):
    """Grid3DView's calls (setBoard, setPieces, setLabels, frame, drawScene,
    pollEvents, resize, close, pickCell), drawn by the page's grid relay."""

    EVENT_QUIT, EVENT_KEY_DOWN, EVENT_KEY_UP, EVENT_RESIZED = (
        EVENT_QUIT, EVENT_KEY_DOWN, EVENT_KEY_UP, EVENT_RESIZED)

    def __init__(self, relay, width, height, reducedMotion=False, clock=time.monotonic):
        self.relay = relay
        self.strata = EVENTS
        self.width, self.height = width, height
        self.isWindow = True
        self.reducedMotion = reducedMotion
        self.clock = clock
        self.board = None
        self.boardTint = None
        self.boardLights = []
        self.pieces = []
        self.labels, self.panels = [], []
        self.animator = None
        self.sent = 0
        self.lastSent = {}  # kind -> the last message of that kind (drawScene)

    @classmethod
    def open(cls, width=900, height=700, title="graphik", relay=None, maxBytes=4000000,
             reducedMotion=None, clock=time.monotonic, canvas="relay"):
        """Ask the page for its 3D view (it is downloaded only now, and only
        under maxBytes); raise Unavailable when there is none. `ready` says
        when it has loaded; what is sent before then waits in the page."""
        relay = relay or PlatformRelay()
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

    def _send(self, message, kind=None):
        rc = self.relay.send(message)
        if rc < 0:
            raise WireError(rc, "the grid relay refused a message")
        self.sent += 1
        if kind is not None:
            self.lastSent[kind] = message

    # -- what to draw (as Grid3DView)

    def setBoard(self, board, tint=None, lights=()):
        """The static part: call when the board, its theme or its tint changes."""
        self.board = board
        self.boardTint = tint
        self.boardLights = list(lights)
        checkLights(self.boardLights)
        self.animator = Animator(board.cellCenter, reducedMotion=self.reducedMotion)
        self.animator.update(self.pieces, self.clock(), 0.0)
        self._send(encodeBoard(board.boardShapes(tint), self.boardLights), BOARD)
        self._sendView()
        self._send(encodePieces(board, self.pieces, self.animator.tracks, 0.0), PIECES)

    def setPieces(self, pieces, tickSeconds=0.0, snap=False):
        """The dynamic part: call once per game tick (see Grid3DView)."""
        if self.board is None:
            raise RuntimeError("setBoard() must come before setPieces()")
        pieces = list(pieces)
        self.board.checkPieces(pieces)
        _, lights = self.board.pieceShapes(pieces)
        checkLights(self.boardLights + lights)
        self.pieces = pieces
        self.animator.update(pieces, self.clock(), tickSeconds, snap=snap)
        tick = 0.0 if snap else self.animator.tickSeconds
        self._send(encodePieces(self.board, pieces, self.animator.tracks, tick), PIECES)

    def setLabels(self, labels=(), panels=()):
        """Screen text and the panels behind it."""
        self.labels, self.panels = list(labels), list(panels)
        self._send(encodeHud(self.labels, self.panels), HUD)

    def scene(self, now=None):
        """The Scene a desktop view would draw at `now` (for tests and tools)."""
        if self.board is None:
            raise RuntimeError("setBoard() must come before drawing")
        now = self.clock() if now is None else now
        top, bottom = self.insetFractions()
        return self.board.scene(self.pieces, positions=self.animator.positions(now),
                                labels=self.labels, panels=self.panels, lights=self.boardLights,
                                aspect=self.width / float(self.height), tint=self.boardTint,
                                top=top, bottom=bottom)

    def frame(self, now=None, present=True):
        """Nothing to do per frame: the relay draws on the page's own frames."""

    def drawScene(self, scene, present=True):
        """Draw a complete Scene, for games that build their own each frame:
        its shapes and lights go as the board, its labels and panels as the
        HUD, its camera as the view; only what changed since the last frame
        is sent."""
        scene.checkLimits()
        messages = [
            (BOARD, encodeBoard(scene.shapes, scene.lights)),
            (PIECES, encodePieces(_NO_BOARD, (), {}, 0.0)),
            (HUD, encodeHud(scene.labels, scene.panels)),
        ]
        if scene.camera is not None:
            messages.append((VIEW, encodeView(scene.camera, scene.clearColor)))
        for kind, message in messages:
            if self.lastSent.get(kind) != message:
                self._send(message, kind)

    def _sendView(self):
        if self.board is not None:
            self._send(encodeView(self.camera()), VIEW)

    # -- the window

    def pollEvents(self):
        """Every event since the last poll (Event objects; see EVENTS)."""
        return [Event(e) for e in self.relay.poll()]

    def resize(self, width, height):
        self.width, self.height = width, height
        self._sendView()

    def setInsets(self, top=None, bottom=None):
        """As Grid3DView's (ViewGeometry.setInsets); the page is sent the
        new camera at once."""
        changed = super().setInsets(top, bottom)
        if changed:
            self._sendView()
        return changed

    def savePng(self, path):
        raise Unavailable("screenshots of the web view are taken by the page (canvas.toBlob)")

    def close(self):
        self.relay.close()


class _NoBoard:
    # what encodePieces needs to send "no pieces" for drawScene
    @staticmethod
    def visible(column, row):
        return False

    @staticmethod
    def bridgePairs(pieces):
        return []


_NO_BOARD = _NoBoard()


# -- pygame events, so a game's 2D handlers work in 3D

# USB HID usage id -> pygame key name (pygame.key.key_code takes these).
_KEY_NAMES = {40: "return", 41: "escape", 42: "backspace", 43: "tab", 44: "space", 45: "-", 46: "=",
              47: "[", 48: "]", 49: "\\", 51: ";", 52: "'", 53: "`", 54: ",", 55: ".", 56: "/",
              74: "home", 75: "page up", 76: "delete", 77: "end", 78: "page down",
              79: "right", 80: "left", 81: "down", 82: "up",
              224: "left ctrl", 225: "left shift", 226: "left alt", 227: "left meta",
              228: "right ctrl", 229: "right shift", 230: "right alt", 231: "right meta"}
_KEY_NAMES.update({4 + i: chr(97 + i) for i in range(26)})
_KEY_NAMES.update({30 + i: str((i + 1) % 10) for i in range(10)})
_KEY_NAMES.update({58 + i: "f%d" % (i + 1) for i in range(12)})
# SDL3 modifier bits; pygame's KMOD_* (SDL2's) use the same bits for these.
_MODS = (0x1, 0x2, 0x40, 0x80, 0x100, 0x200, 0x400, 0x800, 0x1000, 0x2000)


def pygameKey(scancode, pygame):
    """The pygame key constant for a Strata (USB HID) scancode, or 0."""
    name = _KEY_NAMES.get(scancode)
    try:
        return pygame.key.key_code(name) if name else 0
    except (ValueError, AttributeError):
        return 0


def toPygameEvents(events, pygame, keys=False, pointer=True, fingers=True):
    """pygame events for relay (or desktop Strata) events: KEYDOWN, KEYUP and
    TEXTINPUT; MOUSEBUTTONDOWN/UP, MOUSEMOTION and MOUSEWHEEL; FINGERDOWN,
    FINGERUP and FINGERMOTION (a cancelled finger is a FINGERUP); and
    VIDEORESIZE. Keys are off by default: under pygbag, pygame's own SDL
    already gets them (it listens on the whole page), so posting them too
    would double every key. The pointer is on: the relay's canvas covers
    pygame's, so its mouse and touch never reach SDL."""
    out = []
    for e in events:
        t = e.type
        kind = getattr(e, "pointer", "") or ""
        if keys and t in (EVENT_KEY_DOWN, EVENT_KEY_UP):
            mod = 0
            for bit in _MODS:
                if getattr(e, "modifiers", 0) & bit:
                    mod |= bit
            key = getattr(e, "key", "") or ""
            out.append(pygame.event.Event(
                pygame.KEYDOWN if t == EVENT_KEY_DOWN else pygame.KEYUP,
                key=pygameKey(e.scancode, pygame), scancode=e.scancode, mod=mod,
                unicode=key if len(key) == 1 else ""))
        elif keys and t == EVENT_TEXT_INPUT:
            out.append(pygame.event.Event(pygame.TEXTINPUT, text=e.text))
        elif pointer and t in (EVENT_MOUSE_BUTTON_DOWN, EVENT_MOUSE_BUTTON_UP):
            out.append(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN if t == EVENT_MOUSE_BUTTON_DOWN else pygame.MOUSEBUTTONUP,
                pos=(int(e.x), int(e.y)), button=e.button, touch=kind == "touch"))
        elif pointer and t == EVENT_MOUSE_MOTION:
            out.append(pygame.event.Event(
                pygame.MOUSEMOTION, pos=(int(e.x), int(e.y)),
                rel=(int(getattr(e, "dx", 0)), int(getattr(e, "dy", 0))),
                buttons=(0, 0, 0), touch=kind == "touch"))
        elif pointer and t == EVENT_MOUSE_WHEEL:
            out.append(pygame.event.Event(pygame.MOUSEWHEEL, x=e.x, y=e.y, flipped=False))
        elif fingers and t in (EVENT_FINGER_DOWN, EVENT_FINGER_UP, EVENT_FINGER_MOTION,
                               EVENT_FINGER_CANCELED):
            fingerKind = {EVENT_FINGER_DOWN: pygame.FINGERDOWN,
                          EVENT_FINGER_MOTION: pygame.FINGERMOTION}.get(t, pygame.FINGERUP)
            out.append(pygame.event.Event(
                fingerKind, x=e.nx, y=e.ny, dx=getattr(e, "dx", 0), dy=getattr(e, "dy", 0),
                finger_id=e.id, touch_id=0, pressure=getattr(e, "pressure", 0) or 1.0))
        elif t == EVENT_RESIZED:
            out.append(pygame.event.Event(pygame.VIDEORESIZE, size=(e.width, e.height),
                                          w=e.width, h=e.height))
    return out
