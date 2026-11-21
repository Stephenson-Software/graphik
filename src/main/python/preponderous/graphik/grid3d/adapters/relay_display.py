"""RelayDisplay: the page's grid relay (a GridRelay) as a SceneRenderer,
an EventSource and a Surface, plus the retained messages Grid3DWebView
sends it (BOARD, PIECES, HUD, VIEW)."""

from types import SimpleNamespace

from ..errors import Unavailable
from ..events import Event
from ..wire import BOARD, HUD, PIECES, VIEW, WireError, encodeBoard, encodeHud, encodePieces, encodeView


# what encodePieces needs to send "no pieces" for draw()
_NO_BOARD = SimpleNamespace(visible=lambda column, row: False, bridgePairs=lambda pieces: [])


class RelayDisplay:
    """What a Grid3DWebView draws on: `relay` and what it was sent."""

    def __init__(self, relay):
        self.relay = relay
        self.sent = 0
        self.lastSent = {}  # kind -> the last message of that kind (draw)

    def send(self, message, kind=None):
        """Sends one message; a refusal raises WireError with the relay's
        status. `kind` keeps it as the last of its kind, which draw()
        compares against."""
        rc = self.relay.send(message)
        if rc < 0:
            raise WireError(rc, "the grid relay refused a message")
        self.sent += 1
        if kind is not None:
            self.lastSent[kind] = message

    def draw(self, scene, aspect, present=True):
        """A complete Scene, for games that build their own each frame: its
        shapes and lights go as the board, its labels and panels as the HUD,
        its camera as the view; only what changed since the last frame is
        sent. The relay keeps its own aspect and presents on the page's own
        frames, so `aspect` and `present` change nothing."""
        messages = [
            (BOARD, encodeBoard(scene.shapes, scene.lights)),
            (PIECES, encodePieces(_NO_BOARD, (), {}, 0.0)),
            (HUD, encodeHud(scene.labels, scene.panels)),
        ]
        if scene.camera is not None:
            messages.append((VIEW, encodeView(scene.camera, scene.clearColor)))
        for kind, message in messages:
            if self.lastSent.get(kind) != message:
                self.send(message, kind)

    def poll(self):
        """Every event since the last poll (Event objects; see events.EVENTS)."""
        return [Event(e) for e in self.relay.poll()]

    def resize(self, width, height):
        """Nothing to do: the page sizes its own canvas (the view sends the
        camera for the new size)."""

    def savePng(self, path):
        raise Unavailable("screenshots of the web view are taken by the page (canvas.toBlob)")

    def close(self):
        self.relay.close()
