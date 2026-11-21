"""What a 3D grid view shows, kept between frames: the board, its tint and
lights, the tick's pieces sliding on an Animator, and the HUD. The half of
Grid3DView and Grid3DWebView that doesn't depend on how they draw: each
view calls these steps in its own order and adds its own drawing. Pure
Python: no Strata, no pygame.
"""

import time

from .animate import Animator
from .geometry import ViewGeometry


class ViewState(ViewGeometry):
    """A view's board, pieces and HUD at a window size, on a clock."""

    def __init__(self, width, height, reducedMotion=False, clock=time.monotonic):
        self.width, self.height = width, height
        self.reducedMotion = reducedMotion
        self.clock = clock
        self.board = None
        self.boardTint = None
        self.boardLights = []
        self.pieces = []
        self.labels, self.panels = [], []
        self.animator = None

    def placeBoard(self, board, tint=None, lights=()):
        """The static part, kept: setBoard's first step."""
        self.board = board
        self.boardTint = tint
        self.boardLights = list(lights)

    def restartAnimator(self):
        """A new Animator for the board, the current pieces on their cells."""
        self.animator = Animator(self.board.cellCenter, reducedMotion=self.reducedMotion)
        self.animator.update(self.pieces, self.clock(), 0.0)

    def checkedPieces(self, pieces):
        """`pieces` as a list, once the board is set and they all fit on it."""
        if self.board is None:
            raise RuntimeError("setBoard() must come before setPieces()")
        pieces = list(pieces)
        self.board.checkPieces(pieces)
        return pieces

    def movePieces(self, pieces, tickSeconds=0.0, snap=False):
        """Keeps this tick's (checked) pieces and starts their slides now."""
        self.pieces = pieces
        self.animator.update(pieces, self.clock(), tickSeconds, snap=snap)

    def placeLabels(self, labels=(), panels=()):
        """Screen text and the panels behind it, kept."""
        self.labels, self.panels = list(labels), list(panels)

    def scene(self, now=None):
        """The Scene a frame at `now` would draw (for tests and tools)."""
        if self.board is None:
            raise RuntimeError("setBoard() must come before drawing")
        now = self.clock() if now is None else now
        top, bottom = self.insetFractions()
        return self.board.scene(self.pieces, positions=self.animator.positions(now),
                                labels=self.labels, panels=self.panels, lights=self.boardLights,
                                aspect=self.width / float(self.height), tint=self.boardTint,
                                top=top, bottom=bottom)
