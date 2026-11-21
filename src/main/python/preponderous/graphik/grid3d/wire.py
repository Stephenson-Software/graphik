"""The grid relay's wire format: Strata's web/kit/grid-relay/WIRE.md, format 1.0.

The messages Grid3DWebView sends to the page's relay, as pure functions:
BOARD, PIECES, HUD and VIEW encoders, and decode() / readHeader() with the
relay's own checks, for tests and tools. The encoders are held to golden
bytes (golden/wire-1.0.hex) that Strata's relay tests read with its own
parser. Pure Python (struct, math); web.py re-exports every name.
"""

import math
import struct

from .geometry import FAR_PLANE, NEAR_PLANE, SUN_DIRECTION
from .scene import CLEAR_COLOR

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

# The relay's limits and value checks (WIRE.md, "Errors"; relay.h). The
# encoders below check them too, so a message the relay would refuse raises
# WireError where the game made it, with the relay's status, whatever relay
# the page carries.
MAX_SHAPES = 1 << 16
MAX_ANCHORS = 1 << 15
MAX_LIGHTS = 32
MAX_SHADOWED_LIGHTS = 4
MAX_HUD_ITEMS = 4096
MAX_COORDINATE = 1.0e6
_FLOAT_MAX = 3.4028234663852886e38

# What the relay's send() returns for a refused message (WIRE.md, "Errors").
STATUS = {
    -1: "not a grid relay message",
    -2: "another major version of the wire format",
    -3: "truncated",
    -4: "unknown message kind",
    -5: "a bad value",
    -6: "over the relay's limits",
}

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


def _finite(values, what):
    for v in values:
        if not (abs(v) <= _FLOAT_MAX):  # also false for NaN
            raise WireError(-5, "%s has %r, not a finite number" % (what, v))


def _within(values, what):
    for v in values:
        if not (abs(v) <= MAX_COORDINATE):
            raise WireError(-5, "%s has %r, past the relay's +/-%g" % (what, v, MAX_COORDINATE))


def _shape(kind, attach, a, b, position, scale, color):
    color = _rgba(color)
    _within(position, "a shape's position")
    _within(scale, "a shape's scale")
    _finite(color, "a shape's colour")
    return SHAPE.pack(kind, attach, a, b, 0, *position, *scale, *color)


def _light(attach, a, light, offset=(0.0, 0.0)):
    x, y, z = light.position
    position = (x - offset[0], y, z - offset[1])
    _within(position, "a light's position")
    _finite(light.color, "a light's colour")
    if not (0.0 < light.radius <= MAX_COORDINATE):
        raise WireError(-5, "a light's radius is %r; the engine takes 0 < radius" % (light.radius,))
    if not (0.0 <= light.intensity <= _FLOAT_MAX) or min(light.color) < 0.0:
        raise WireError(-5, "a light's intensity and colour can't be negative")
    return LIGHT.pack(
        attach, 1 if light.castShadows else 0, a,
        *position, *light.color, light.radius, light.intensity,
    )


def _hudColor(color, what):
    color = _rgba(color)
    _finite(color, what)
    if min(color) < 0.0 or color[3] > 1.0:
        raise WireError(-5, "%s %r: the engine takes no negative part and alpha up to 1" % (what, color))
    return color


def _checkCounts(shapes=0, lights=(), anchors=0):
    if shapes > MAX_SHAPES:
        raise WireError(-6, "%d shapes; the relay takes %d" % (shapes, MAX_SHAPES))
    if anchors > MAX_ANCHORS:
        raise WireError(-6, "%d pieces; the relay takes %d" % (anchors, MAX_ANCHORS))
    if len(lights) > MAX_LIGHTS:
        raise WireError(-6, "%d lights; the relay takes %d" % (len(lights), MAX_LIGHTS))
    if sum(1 for light in lights if light.castShadows) > MAX_SHADOWED_LIGHTS:
        raise WireError(-6, "over %d shadow-casting lights" % MAX_SHADOWED_LIGHTS)


def _worldShapes(shapes):
    """The shapes' records for BOARD in one pass, the relay's checks made on
    all of them at once (a board is a few thousand shapes, encoded whenever
    the game builds its scene); None when one fails, or has a 3-part colour,
    so _shape() finds it and says what is wrong."""
    places = [v for s in shapes for v in (*s.position, *s.scale)]
    colors = [v for s in shapes for v in s.color]
    if len(colors) != 4 * len(shapes):
        return None
    # sum() is NaN or infinite when any value is
    if places and not (max(map(abs, places)) <= MAX_COORDINATE and math.isfinite(sum(places))):
        return None
    if colors and not (max(map(abs, colors)) <= _FLOAT_MAX and math.isfinite(sum(colors))):
        return None
    pack = SHAPE.pack
    try:
        return [pack(s.kind, WORLD, 0, 0, 0, *s.position, *s.scale, *s.color) for s in shapes]
    except struct.error:
        return None


def encodeBoard(shapes, lights=()):
    """BOARD: world shapes and lights."""
    _checkCounts(len(shapes), lights)
    out = [header(BOARD), COUNTS.pack(len(shapes), len(lights))]
    fast = _worldShapes(shapes)
    out += fast if fast is not None else [
        _shape(s.kind, WORLD, 0, 0, s.position, s.scale, s.color) for s in shapes]
    out += [_light(WORLD, 0, light) for light in lights]
    return b"".join(out)


def _labelText(text):
    # a lone surrogate (text read from a file name, say) is sent as "?", which
    # is what Strata draws for any character outside its font anyway
    data = str(text).replace("\0", "").encode("utf-8", "replace")
    if len(data) > 65535:
        data = data[:65535].decode("utf-8", "ignore").encode("utf-8")
    return data


def encodeHud(labels=(), panels=()):
    """HUD: screen panels (drawn first) and labels, in CSS pixels."""
    if len(panels) > MAX_HUD_ITEMS or len(labels) > MAX_HUD_ITEMS:
        raise WireError(-6, "%d panels and %d labels; the relay takes %d of each"
                        % (len(panels), len(labels), MAX_HUD_ITEMS))
    out = [header(HUD), COUNTS.pack(len(panels), len(labels))]
    for p in panels:
        _finite((p.x, p.y, p.width, p.height), "a panel")
        out.append(PANEL.pack(p.x, p.y, p.width, p.height, *_hudColor(p.color, "a panel's colour")))
    for label in labels:
        text = _labelText(label.text)
        _finite((label.x, label.y, label.pixelSize), "a label")
        out.append(LABEL.pack(label.x, label.y, label.pixelSize, *_hudColor(label.color, "a label's colour"),
                              len(text), 0))
        out.append(text + b"\0" * (-len(text) % 4))
    return b"".join(out)


def encodeView(camera, clearColor=CLEAR_COLOR, sun=SUN_DIRECTION, near=NEAR_PLANE, far=FAR_PLANE):
    """VIEW: the camera, clear colour and direction to the sun."""
    _within(camera.eye, "the camera's eye")
    _within(camera.target, "the camera's target")
    _finite(tuple(_rgba(clearColor)) + tuple(sun), "the view")
    if tuple(camera.eye) == tuple(camera.target):
        raise WireError(-5, "the camera's eye is on its target")
    if not (0.0 < camera.fovDegrees < 180.0 and 0.0 < near < far <= _FLOAT_MAX):
        raise WireError(-5, "the view needs 0 < fov < 180 and 0 < near < far")
    return header(VIEW) + VIEW_BODY.pack(
        *camera.eye, *camera.target, camera.fovDegrees, near, far, *_rgba(clearColor), *sun
    )


def encodePieces(board, pieces, tracks, tickSeconds):
    """PIECES for this tick. `tracks` maps a piece id to ((x0, z0), (x1, z1)),
    from an Animator; a piece without one stands still on its cell. With a
    viewport, only the pieces in it are sent."""
    pieces = [p for p in pieces if board.visible(p.column, p.row)]
    _checkCounts(anchors=len(pieces))
    index = {}
    anchors, shapes, lights = [], [], []
    for i, piece in enumerate(pieces):
        end = board.cellCenter(piece.column, piece.row)
        start, end = tracks.get(piece.id, (end, end))
        index[piece.id] = i
        _within(tuple(start) + tuple(end), "piece %r's slide" % (piece.id,))
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
    if len(shapes) > MAX_SHAPES or len(lights) > MAX_LIGHTS:
        raise WireError(-6, "%d piece shapes and %d piece lights; the relay takes %d and %d"
                        % (len(shapes), len(lights), MAX_SHAPES, MAX_LIGHTS))
    if not (0.0 <= tickSeconds <= _FLOAT_MAX):
        raise WireError(-5, "tickSeconds is %r" % (tickSeconds,))
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
